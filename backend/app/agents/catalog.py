"""Every agent, by name. Importing this registers all their tools."""

from app.agents.core import Agent
from app.agents.customer_agents import GIFT_CONCIERGE, GIFT_MESSAGE, SUPPORT
from app.agents.test_agent import STOCK_HELPER

AGENTS: dict[str, Agent] = {
    agent.name: agent for agent in [STOCK_HELPER, GIFT_CONCIERGE, SUPPORT, GIFT_MESSAGE]
}
