"""The tool registry: what an agent can call, with typed inputs, a risk level and a permission."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.context import Actor
from app.models import AgentRun, Risk
from app.permissions import Permission


@dataclass
class ToolContext:
    db: Session
    # Who the tool runs as: the run's actor, or for an approved tool, the staff member who
    # approved it.
    actor: Actor
    run: AgentRun


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    run: Callable[[ToolContext, Any], Any]
    risk: Risk = Risk.AUTO
    # Needed by whoever the tool runs as. Checked before it runs, whatever the model says.
    permission: Permission | None = None
    # "staff" tools are never offered to customer runs.
    audience: Literal["anyone", "staff"] = "staff"

    def schema(self) -> dict[str, Any]:
        """The tool definition for the Claude API."""
        input_schema = self.input_model.model_json_schema()
        input_schema.pop("title", None)
        return {"name": self.name, "description": self.description, "input_schema": input_schema}

    def offered_to(self, actor: Actor) -> bool:
        if self.audience == "staff" and actor.staff is None:
            return False
        # An approve tool is offered to anyone it can be offered to: it only creates a request,
        # and the approver's permission is checked when it runs.
        return self.risk == Risk.APPROVE or actor.allows(self.permission)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def add(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name} is already registered.")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)


registry = ToolRegistry()
