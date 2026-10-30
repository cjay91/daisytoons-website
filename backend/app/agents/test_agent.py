"""A small staff-facing agent that proves the harness: stock lookups and stock settings.

It isn't offered to customers or staff yet. Its eval suite (app/agents/evals.py) checks the
harness's guarantees: approve tools wait, limits hold, permissions hold.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.core import Agent, Limits
from app.agents.tools import Tool, ToolContext, registry
from app.models import Risk
from app.permissions import Permission
from app.schemas import InventoryUpdate
from app.services.inventory import available, get_inventory, update_inventory
from app.services.products import list_active_products


class SearchProducts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(description="Words to look for in product names, descriptions and tags.")
    max_price: Decimal | None = Field(default=None, ge=0, description="Highest price in LKR.")


class ProductId(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)


class BinLocation(ProductId):
    bin_location: str = Field(max_length=50, description="Shelf code, for example B-2.")


class ReorderPoint(ProductId):
    reorder_point: int = Field(ge=0, le=10_000, description="Reorder when stock falls to this.")


def search_products(ctx: ToolContext, data: SearchProducts) -> list[dict]:
    products = list_active_products(ctx.db, q=data.query, max_price=data.max_price)
    return [
        {
            "product_id": p.id,
            "name": p.name,
            "price": str(p.price),
            "in_stock": p.inventory is not None and available(p.inventory) > 0,
        }
        for p in products[:10]
    ]


def get_stock(ctx: ToolContext, data: ProductId) -> dict:
    inventory = get_inventory(ctx.db, ctx.actor.staff, data.product_id)
    return {
        "product_id": inventory.product_id,
        "on_hand": inventory.on_hand,
        "reserved": inventory.reserved,
        "available": available(inventory),
        "reorder_point": inventory.reorder_point,
        "bin_location": inventory.bin_location,
    }


def set_bin_location(ctx: ToolContext, data: BinLocation) -> dict:
    update = InventoryUpdate(bin_location=data.bin_location)
    inventory = update_inventory(ctx.db, ctx.actor.staff, data.product_id, update)
    return {"product_id": inventory.product_id, "bin_location": inventory.bin_location}


def set_reorder_point(ctx: ToolContext, data: ReorderPoint) -> dict:
    update = InventoryUpdate(reorder_point=data.reorder_point)
    inventory = update_inventory(ctx.db, ctx.actor.staff, data.product_id, update)
    return {"product_id": inventory.product_id, "reorder_point": inventory.reorder_point}


registry.add(
    Tool(
        "search_products",
        "Find products for sale by keywords, optionally under a price. Returns up to 10.",
        SearchProducts,
        search_products,
        audience="anyone",
    )
)
registry.add(
    Tool(
        "get_stock",
        "Stock for one product: on hand, reserved for unpaid orders, available, reorder point "
        "and bin location.",
        ProductId,
        get_stock,
        permission=Permission.VIEW_CATALOG,
    )
)
registry.add(
    Tool(
        "set_bin_location",
        "Record which shelf a product is kept on.",
        BinLocation,
        set_bin_location,
        risk=Risk.NOTIFY,
        permission=Permission.MANAGE_STOCK,
    )
)
registry.add(
    Tool(
        "set_reorder_point",
        "Ask to change the stock level at which a product should be reordered. A staff member "
        "must approve the change before it happens.",
        ReorderPoint,
        set_reorder_point,
        risk=Risk.APPROVE,
        permission=Permission.MANAGE_STOCK,
    )
)

STOCK_HELPER = Agent(
    name="stock_helper",
    system=(
        "You help the staff of Daisytoons, a gift shop in Sri Lanka, with questions about stock. "
        "Use the tools to look things up rather than guessing, and answer briefly. Prices are in "
        "LKR. When you ask for a change that needs approval, say that it is waiting for a staff "
        "member to approve it."
    ),
    tools=["search_products", "get_stock", "set_bin_location", "set_reorder_point"],
    effort="low",
    limits=Limits(steps=6, tokens=40_000, cost=Decimal("0.25")),
)
