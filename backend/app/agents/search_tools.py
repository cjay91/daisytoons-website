"""search_products and search_knowledge: what agents use to look up products and policies."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.agents.tools import Tool, ToolContext, registry
from app.embeddings import get_embedder
from app.models import TagKind
from app.services.inventory import available
from app.services.search import (
    ProductFilters,
    describe_chunk,
    search_knowledge,
    search_products,
)


class SearchProducts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        max_length=300,
        description="What the customer is looking for, in their words, such as 'something for "
        "a tea lover' or 'teddy bear'. Can be empty when the filters say it all.",
    )
    max_price: Decimal | None = Field(default=None, ge=0, description="Highest price in LKR.")
    min_price: Decimal | None = Field(default=None, ge=0, description="Lowest price in LKR.")
    occasion: str | None = Field(
        default=None, max_length=50, description="An occasion tag, such as 'Birthday'."
    )
    recipient: str | None = Field(
        default=None, max_length=50, description="A recipient tag, such as 'For her'."
    )
    in_stock_only: bool = Field(default=True, description="Leave out products that are sold out.")


class SearchKnowledge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=300, description="The question to answer.")
    kind: str | None = Field(
        default=None,
        pattern="^(policies|faq|guides|suppliers)$",
        description="Only look in policies, faq, guides or suppliers.",
    )


def _search_products(ctx: ToolContext, data: SearchProducts) -> list[dict]:
    filters = ProductFilters(
        in_stock_only=data.in_stock_only,
        min_price=data.min_price,
        max_price=data.max_price,
        occasion=data.occasion,
        recipient=data.recipient,
    )
    products = search_products(ctx.db, get_embedder(), data.query, filters)
    return [
        {
            "product_id": p.id,
            "name": p.name,
            "url": f"/products/{p.slug}",
            "price": str(p.price),
            "in_stock": p.inventory is not None and available(p.inventory) > 0,
            "description": p.description[:300],
            "occasions": [t.name for t in p.tags if t.kind == TagKind.OCCASION],
            "recipients": [t.name for t in p.tags if t.kind == TagKind.RECIPIENT],
        }
        for p in products
    ]


def _search_knowledge(ctx: ToolContext, data: SearchKnowledge) -> list[dict]:
    chunks = search_knowledge(ctx.db, get_embedder(), data.query, kind=data.kind)
    return [describe_chunk(chunk) for chunk in chunks]


registry.add(
    Tool(
        "search_products",
        "Find products for sale, best match first (up to 5). Searches by meaning as well as "
        "words, and the filters always hold. Prices are in LKR.",
        SearchProducts,
        _search_products,
        audience="anyone",
    )
)
registry.add(
    Tool(
        "search_knowledge",
        "Look up the shop's policies (delivery, returns, privacy, terms), FAQs and gift guides. "
        "Returns the passages that best answer the question. Answer only from what it returns.",
        SearchKnowledge,
        _search_knowledge,
        audience="anyone",
    )
)
