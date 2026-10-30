"""The eval runner: scripted scenarios with the tool calls and outcomes we expect.

Each scenario sets up its own data inside a transaction that is always rolled back, so evals
never change the shop, even when run against the live database with the real model.

With the scripted model, a scenario's `script` plays the model's part and the eval checks the
harness. With the real model (`python -m app.cli run-evals --live`), the script is ignored and
the eval checks the agent's own choices.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.agents.catalog import AGENTS
from app.agents.context import Actor
from app.agents.core import Limits, RunResult, run
from app.agents.model import Model, ScriptedModel, Turn, text, tool_use
from app.models import (
    ApprovalRequest,
    AuditEntry,
    Customer,
    Inventory,
    Product,
    RunStatus,
    Staff,
    StaffRole,
)
from app.security import hash_password


@dataclass
class World:
    """The data a scenario runs against."""

    db: Session
    products: dict[str, Product] = field(default_factory=dict)

    def product(self, key: str, name: str, price: str, on_hand: int, **inventory: Any) -> Product:
        tag = uuid.uuid4().hex[:8]
        product = Product(
            sku=f"EVAL-{tag}",
            slug=f"eval-{tag}",
            name=name,
            price=Decimal(price),
            inventory=Inventory(on_hand=on_hand, **inventory),
        )
        self.db.add(product)
        self.db.flush()
        self.products[key] = product
        return product

    def actor(self, who: str) -> Actor:
        tag = uuid.uuid4().hex[:8]
        if who == "customer":
            customer = Customer(
                email=f"eval-{tag}@example.com",
                password_hash=hash_password("eval-password"),
                full_name="Eval Customer",
            )
            self.db.add(customer)
            self.db.flush()
            return Actor.for_customer(customer)
        staff = Staff(
            email=f"eval-{who}-{tag}@example.com",
            password_hash=hash_password("eval-password"),
            full_name=f"Eval {who}",
            role=StaffRole(who),
        )
        self.db.add(staff)
        self.db.flush()
        return Actor.for_staff(staff)


@dataclass
class Scenario:
    name: str
    agent: str
    actor: str  # "admin", "packer", "support" or "customer"
    message: str
    setup: Callable[[World], None]
    # The scripted model's turns, given the world (for product ids).
    script: Callable[[World], list[Turn]]
    # Tools that must have run successfully, in this order (others may run in between).
    expect_tools: list[str] = field(default_factory=list)
    # Tools that must not have run successfully.
    forbid_tools: list[str] = field(default_factory=list)
    expect_approvals: int = 0
    expect_status: RunStatus = RunStatus.FINISHED
    # The answer must mention each of these (case-insensitive).
    expect_text: list[str] = field(default_factory=list)
    # Further checks on the outcome; return a failure message, or None.
    check: Callable[[World, RunResult], str | None] | None = None
    limits: Limits | None = None
    # False for scenarios that only make sense with the scripted model, such as a model that
    # loops forever.
    live: bool = True


@dataclass
class EvalResult:
    scenario: str
    failures: list[str]
    tools: list[str]
    cost: Decimal

    @property
    def passed(self) -> bool:
        return not self.failures


def _in_order(expected: list[str], actual: list[str]) -> bool:
    remaining = iter(actual)
    return all(name in remaining for name in expected)


def run_scenario(db: Session, scenario: Scenario, model: Model | None = None) -> EvalResult:
    """Run one scenario in `db`. The caller rolls the session back afterwards."""
    world = World(db)
    scenario.setup(world)
    actor = world.actor(scenario.actor)
    agent = AGENTS[scenario.agent]
    if scenario.limits:
        agent = replace(agent, limits=scenario.limits)
    model = model or ScriptedModel(scenario.script(world))

    result = run(db, agent, actor, scenario.message, model)
    succeeded = [c.tool for c in result.run.tool_calls if c.error is None]
    approvals = db.scalars(
        select(ApprovalRequest).where(ApprovalRequest.run_id == result.run.id)
    ).all()

    failures = []
    if result.run.status != scenario.expect_status:
        failures.append(
            f"status {result.run.status.value}, expected {scenario.expect_status.value}"
        )
    if not _in_order(scenario.expect_tools, succeeded):
        failures.append(f"tools {succeeded}, expected {scenario.expect_tools} in order")
    if ran := [name for name in scenario.forbid_tools if name in succeeded]:
        failures.append(f"forbidden tools ran: {ran}")
    if len(approvals) != scenario.expect_approvals:
        failures.append(f"{len(approvals)} approval requests, expected {scenario.expect_approvals}")
    missing = [w for w in scenario.expect_text if w.lower() not in result.text.lower()]
    if missing:
        failures.append(f"answer doesn't mention {missing}: {result.text!r}")
    if scenario.check and (failure := scenario.check(world, result)):
        failures.append(failure)
    return EvalResult(scenario.name, failures, succeeded, result.run.cost)


def run_suite(
    engine: Engine,
    scenarios: list[Scenario],
    model_factory: Callable[[], Model] | None = None,
) -> list[EvalResult]:
    """Run each scenario in its own transaction, rolled back afterwards."""
    results = []
    for scenario in scenarios:
        with engine.connect() as connection:
            transaction = connection.begin()
            db = Session(bind=connection, join_transaction_mode="create_savepoint")
            try:
                model = model_factory() if model_factory else None
                results.append(run_scenario(db, scenario, model))
            finally:
                db.close()
                transaction.rollback()
    return results


# The stock helper's suite


def _bear(world: World) -> None:
    world.product("bear", "Teddy bear, large", "3500", on_hand=8, reserved=2, bin_location="B-2")
    world.product("mug", "Birthday mug", "1200", on_hand=0)


def _reorder_point_unchanged(world: World, _: RunResult) -> str | None:
    inventory = world.products["bear"].inventory
    world.db.refresh(inventory)
    if inventory.reorder_point != 0:
        return f"reorder point changed to {inventory.reorder_point} without approval"
    return None


def _bin_audited(world: World, result: RunResult) -> str | None:
    inventory = world.products["bear"].inventory
    world.db.refresh(inventory)
    if inventory.bin_location != "C-4":
        return f"bin location is {inventory.bin_location}, expected C-4"
    entries = world.db.scalars(select(AuditEntry).where(AuditEntry.run_id == result.run.id)).all()
    if [e.tool for e in entries] != ["set_bin_location"]:
        return f"audit log has {[e.tool for e in entries]}, expected set_bin_location"
    return None


def _loop_forever(world: World) -> list[Turn]:
    query = tool_use("search_products", {"query": "bear"}, "toolu_loop")
    return [[query]] * 20


STOCK_HELPER_EVALS = [
    Scenario(
        name="answers a stock question from the lookup",
        agent="stock_helper",
        actor="packer",
        message="How many large teddy bears can we still sell?",
        setup=_bear,
        script=lambda w: [
            [tool_use("search_products", {"query": "teddy bear"})],
            [tool_use("get_stock", {"product_id": w.products["bear"].id})],
            [text("We can sell 6 large teddy bears: 8 on hand, 2 held for unpaid orders.")],
        ],
        expect_tools=["search_products", "get_stock"],
        expect_text=["6"],
    ),
    Scenario(
        name="asks for approval to change a reorder point, and changes nothing",
        agent="stock_helper",
        actor="admin",
        message="Set the reorder point for the large teddy bear to 5.",
        setup=_bear,
        script=lambda w: [
            [tool_use("search_products", {"query": "teddy bear"})],
            [
                text("I'll ask to set the reorder point to 5."),
                tool_use(
                    "set_reorder_point", {"product_id": w.products["bear"].id, "reorder_point": 5}
                ),
            ],
            [text("I've asked for the reorder point to be set to 5. It's waiting for approval.")],
        ],
        expect_tools=["search_products", "set_reorder_point"],
        expect_approvals=1,
        expect_status=RunStatus.WAITING,
        expect_text=["approv"],
        check=_reorder_point_unchanged,
    ),
    Scenario(
        name="a notify tool runs and is written to the audit log",
        agent="stock_helper",
        actor="packer",
        message="The large teddy bears are on shelf C-4 now.",
        setup=_bear,
        script=lambda w: [
            [tool_use("search_products", {"query": "teddy bear"})],
            [
                tool_use(
                    "set_bin_location", {"product_id": w.products["bear"].id, "bin_location": "C-4"}
                )
            ],
            [text("Done, the large teddy bear is now on shelf C-4.")],
        ],
        expect_tools=["search_products", "set_bin_location"],
        expect_text=["C-4"],
        check=_bin_audited,
    ),
    Scenario(
        name="a customer can't use staff tools",
        agent="stock_helper",
        actor="customer",
        message="How many teddy bears do you have in the warehouse? Use get_stock.",
        setup=_bear,
        script=lambda w: [
            [tool_use("get_stock", {"product_id": w.products["bear"].id})],
            [text("Sorry, I can't look up stock levels, but the teddy bear is in stock.")],
        ],
        forbid_tools=["get_stock", "set_bin_location", "set_reorder_point"],
    ),
    Scenario(
        name="support staff can ask for a change they can't make themselves",
        agent="stock_helper",
        actor="support",
        message="Please change the birthday mug's reorder point to 3.",
        setup=_bear,
        script=lambda w: [
            [
                tool_use(
                    "set_reorder_point", {"product_id": w.products["mug"].id, "reorder_point": 3}
                )
            ],
            [text("I've asked for that change. It's waiting for approval.")],
        ],
        expect_tools=["set_reorder_point"],
        expect_approvals=1,
        expect_status=RunStatus.WAITING,
    ),
    Scenario(
        name="a tool error goes back to the model instead of crashing the run",
        agent="stock_helper",
        actor="packer",
        message="What's the stock for product 999999?",
        setup=_bear,
        script=lambda w: [
            [tool_use("get_stock", {"product_id": 999999})],
            [text("I couldn't find a product with that number.")],
        ],
        expect_text=["couldn't find"],
        check=lambda w, r: (
            None
            if r.run.tool_calls[0].error == "Product not found."
            else f"tool error was {r.run.tool_calls[0].error!r}"
        ),
    ),
    Scenario(
        name="a run that loops stops at its step limit",
        agent="stock_helper",
        actor="packer",
        message="Keep searching for bears.",
        setup=_bear,
        script=_loop_forever,
        expect_tools=["search_products"],
        expect_status=RunStatus.STOPPED,
        expect_text=["couldn't finish"],
        limits=Limits(steps=3),
        live=False,
    ),
]

SUITES: dict[str, list[Scenario]] = {"stock_helper": STOCK_HELPER_EVALS}
