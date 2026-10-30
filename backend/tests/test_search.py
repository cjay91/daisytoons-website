import json
import re
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app import search_evals
from app.agents.catalog import AGENTS
from app.agents.context import Actor
from app.agents.core import run
from app.agents.model import ScriptedModel, text, tool_use
from app.config import get_settings
from app.embeddings import DIMENSIONS, HashingEmbedder, VoyageEmbedder
from app.models import KnowledgeChunk, KnowledgeDocument, ProductVector, Tag, TagKind
from app.services.search import (
    KNOWLEDGE_DIR,
    ProductFilters,
    SourceDocument,
    index_knowledge,
    index_products,
    load_documents,
    search_knowledge,
    search_products,
    split_passages,
)

REPO = Path(__file__).resolve().parents[2]
embedder = HashingEmbedder()


class OtherModel(HashingEmbedder):
    model = "hashing-v2"


# Measured search quality. With the hashing stand-in these are a floor that guards against
# regressions; `python -m app.cli search-evals` with Voyage gives the real numbers.


def test_search_quality_holds(db):
    products, knowledge = search_evals.measure(db, embedder)
    assert products.hit_at_k >= 0.8, products.misses
    assert knowledge.hit_at_k >= 0.85, knowledge.misses
    assert products.mrr >= 0.7 and knowledge.mrr >= 0.65


# Products


def test_products_are_indexed_once_until_they_change(db, make_product):
    bear = make_product()
    first = index_products(db, embedder)
    assert first >= 1
    assert index_products(db, embedder) == 0

    bear.name = "Giant teddy bear"
    db.flush()
    assert index_products(db, embedder) == 1
    assert "Giant teddy bear" in db.get(ProductVector, bear.id).document
    # A new embedding model re-embeds everything.
    assert index_products(db, OtherModel()) == first


def test_product_search_finds_by_words_and_meaning(db, make_product):
    bear = make_product()
    bear.name, bear.description = "Cuddly teddy bear", "Soft bear with a ribbon"
    mug = make_product()
    mug.name, mug.description = "Daisy mug", "Ceramic mug for coffee"
    db.flush()
    index_products(db, embedder)

    assert search_products(db, embedder, "teddy")[0] == bear
    assert search_products(db, embedder, "coffee mug")[0] == mug


def test_filters_always_hold(db, make_product):
    cheap, dear, sold_out = make_product("900"), make_product("5000"), make_product("800", 0)
    hidden = make_product("700", is_active=False)
    birthday = db.scalar(select(Tag).where(Tag.kind == TagKind.OCCASION, Tag.slug == "birthday"))
    cheap.tags.append(birthday)
    db.flush()
    index_products(db, embedder)

    def found(**filters):
        return set(search_products(db, embedder, "test product", ProductFilters(**filters), 10))

    assert hidden not in found(in_stock_only=False)
    assert sold_out not in found()
    assert sold_out in found(in_stock_only=False)
    assert found(max_price=Decimal("1000")) == {cheap}
    assert dear in found(min_price=Decimal("4000"))
    assert found(occasion="Birthday") == found(occasion="birthday") == {cheap}


def test_a_product_not_indexed_yet_is_still_found_by_name(db, make_product):
    product = make_product()
    product.name = "Batik silk scarf"
    db.flush()
    assert db.get(ProductVector, product.id) is None
    assert search_products(db, embedder, "batik scarf") == [product]


# Knowledge


def test_documents_are_loaded_with_settings_filled_in():
    documents = {d.slug: d for d in load_documents()}
    assert set(documents) >= {
        "policies/shipping",
        "policies/returns",
        "policies/privacy",
        "policies/terms",
        "faq/gifts",
        "faq/orders-and-payment",
    }
    assert documents["policies/shipping"].kind == "policies"
    assert "Rs 400" in documents["policies/shipping"].text
    assert "Rs 10,000" in documents["policies/shipping"].text
    for document in documents.values():
        assert not re.search(r"\{[a-z_]+\}", document.text), document.slug
        assert "<!--" not in document.text


def test_long_sections_are_split_at_paragraphs():
    paragraph = "word " * 150
    document = SourceDocument(
        "x/y", "x", "Title", f"Intro.\n\n## Long\n\n{paragraph}\n\n{paragraph}"
    )
    passages = split_passages(document)
    assert [(p.heading, len(p.text) < 1200) for p in passages] == [
        ("Title", True),
        ("Long", True),
        ("Long", True),
    ]


def test_knowledge_is_reindexed_only_when_it_changes(db):
    documents = [SourceDocument("faq/a", "faq", "A", "## Q\n\nFirst answer.")]
    assert index_knowledge(db, embedder, documents) == 1
    assert index_knowledge(db, embedder, documents) == 0

    documents = [SourceDocument("faq/a", "faq", "A", "## Q\n\nSecond answer.")]
    assert index_knowledge(db, embedder, documents) == 1
    [chunk] = db.scalars(select(KnowledgeChunk)).all()
    assert chunk.text == "Second answer."

    assert index_knowledge(db, embedder, []) == 0
    assert db.scalars(select(KnowledgeDocument)).all() == []


def test_knowledge_search_returns_the_right_passage(db):
    index_knowledge(db, embedder)
    [first, *_] = search_knowledge(db, embedder, "Do you use cookies?")
    assert (first.document.slug, first.heading) == ("policies/privacy", "Cookies")
    assert first.document.url == "/privacy"
    only_faq = search_knowledge(db, embedder, "refund", kind="faq")
    assert {c.document.kind for c in only_faq} == {"faq"}


# The knowledge copies of the policy pages must match the storefront's.


@pytest.mark.parametrize("page", ["shipping", "returns", "privacy", "terms"])
def test_policy_headings_match_the_storefront(page):
    tsx = (REPO / f"frontend/src/app/{page}/page.tsx").read_text()
    storefront = [re.sub(r"&apos;", "'", h) for h in re.findall(r"<h2>(.*?)</h2>", tsx)]
    markdown = (KNOWLEDGE_DIR / f"policies/{page}.md").read_text()
    assert re.findall(r"^## (.+)$", markdown, re.M) == storefront


def test_policy_numbers_match_the_storefront_and_settings():
    shop = (REPO / "frontend/src/lib/shop.ts").read_text()

    def value(name):
        return re.search(rf'{name}: "?([^",]+)"?,', shop).group(1)

    settings = get_settings()
    assert Decimal(value("deliveryColombo")) == settings.delivery_fee_colombo
    assert Decimal(value("deliveryOther")) == settings.delivery_fee_other
    assert Decimal(value("freeDeliveryOver")) == settings.free_delivery_over
    assert Decimal(value("giftWrap")) == settings.gift_wrap_fee
    assert int(value("holdMinutes")) == settings.reservation_minutes
    shipping = (KNOWLEDGE_DIR / "policies/shipping.md").read_text()
    assert f"{value('deliveryDaysColombo')} working days in Colombo" in shipping
    assert f"{value('deliveryDaysOther')} working days elsewhere" in shipping
    returns = (KNOWLEDGE_DIR / "policies/returns.md").read_text()
    assert returns.count(f"within {value('returnDays')} days of delivery") == 2


# Agent tools


def test_agents_search_products_and_knowledge(db, make_product, make_customer):
    product = make_product()
    product.name = "Ceylon tea hamper"
    db.flush()
    index_knowledge(db, embedder)
    model = ScriptedModel(
        [
            [
                tool_use("search_products", {"query": "tea hamper", "max_price": 5000}, "t1"),
                tool_use("search_knowledge", {"query": "Do you gift wrap?"}, "t2"),
            ],
            [text("Yes.")],
        ]
    )

    result = run(db, AGENTS["stock_helper"], Actor.for_customer(make_customer()), "?", model)

    products, passages = (call.output for call in result.run.tool_calls)
    assert products[0]["name"] == "Ceylon tea hamper"
    assert products[0]["url"] == f"/products/{product.slug}"
    assert products[0]["in_stock"] is True
    assert passages[0]["section"] == "Can you gift wrap my order?"


# Voyage, with a fake server


def test_voyage_embedder_sends_batches_and_keeps_order():
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        sent.append((request.headers["authorization"], body))
        data = [
            {"index": i, "embedding": [float(i)] * DIMENSIONS} for i in range(len(body["input"]))
        ]
        return httpx.Response(200, json={"data": list(reversed(data))})

    voyage = VoyageEmbedder(
        "key", "voyage-3.5-lite", httpx.Client(transport=httpx.MockTransport(handler))
    )
    vectors = voyage.embed([f"text {i}" for i in range(130)], "query")

    assert len(vectors) == 130
    assert [v[0] for v in vectors[:3]] == [0.0, 1.0, 2.0]
    assert [len(body["input"]) for _, body in sent] == [128, 2]
    auth, body = sent[0]
    assert auth == "Bearer key"
    assert (body["model"], body["input_type"], body["output_dimension"]) == (
        "voyage-3.5-lite",
        "query",
        1024,
    )
