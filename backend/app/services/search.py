"""Search for agents (Part 9): products and knowledge, by meaning and by keywords together.

Each search runs two rankings, one by vector similarity and one by Postgres full-text search,
and merges them with reciprocal rank fusion. Structured filters (in stock, price, occasion,
recipient) apply before ranking, so they hold whatever the text says.

Indexing is incremental: a product or passage is embedded again only when its text, or the
embedding model, changes. The worker runs both indexers every minute.
"""

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.embeddings import Embedder
from app.models import (
    Inventory,
    KnowledgeChunk,
    KnowledgeDocument,
    Product,
    ProductVector,
    Tag,
    TagKind,
)
from app.text import slugify

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"
# Storefront pages for documents that have one.
DOCUMENT_URLS = {
    "policies/shipping": "/shipping",
    "policies/returns": "/returns",
    "policies/privacy": "/privacy",
    "policies/terms": "/terms",
}
RRF_K = 60  # the usual constant for reciprocal rank fusion
CANDIDATES = 20  # taken from each ranking before merging
MAX_CHUNK_CHARS = 1200


def _hash(model: str, text: str) -> str:
    return hashlib.sha256(f"{model}\n{text}".encode()).hexdigest()


def _fuse(*rankings: Iterable[int]) -> list[tuple[int, float]]:
    """Reciprocal rank fusion: each list adds 1 / (k + rank) for every id it contains."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda pair: -pair[1])


def _keyword_query(text: str):
    """Any of the words, as a Postgres tsquery, or None if there are no usable words."""
    words = re.findall(r"[a-z0-9]+", text.lower())[:20]
    if not words:
        return None
    return func.to_tsquery("english", " | ".join(words))


# Products


def product_document(product: Product) -> str:
    """The text a product is found by."""
    occasions = [t.name for t in product.tags if t.kind == TagKind.OCCASION]
    recipients = [t.name for t in product.tags if t.kind == TagKind.RECIPIENT]
    lines = [product.name, product.description]
    if occasions:
        lines.append("Occasions: " + ", ".join(occasions))
    if recipients:
        lines.append("Good for: " + ", ".join(recipients))
    return "\n".join(line for line in lines if line)


def index_products(db: Session, embedder: Embedder) -> int:
    """Embed products whose text or model changed. Returns how many were embedded."""
    products = db.scalars(select(Product).options(selectinload(Product.tags))).all()
    existing = {v.product_id: v for v in db.scalars(select(ProductVector))}
    stale = []
    for product in products:
        document = product_document(product)
        content_hash = _hash(embedder.model, document)
        vector = existing.get(product.id)
        if vector is None or vector.content_hash != content_hash:
            stale.append((product, document, content_hash))
    if stale:
        embeddings = embedder.embed([doc for _, doc, _ in stale], "document")
        for (product, document, content_hash), embedding in zip(stale, embeddings, strict=True):
            vector = existing.get(product.id) or ProductVector(product_id=product.id)
            vector.document = document
            vector.content_hash = content_hash
            vector.embedding = embedding
            db.add(vector)
        db.commit()
    return len(stale)


@dataclass(frozen=True)
class ProductFilters:
    in_stock_only: bool = True
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    occasion: str | None = None
    recipient: str | None = None


def _tag(kind: TagKind, value: str):
    """A tag given by its slug or its name, such as "birthday", "Birthday" or "for-her"."""
    return Product.tags.any(
        (Tag.kind == kind) & or_(Tag.slug == slugify(value), Tag.name.ilike(value))
    )


def _filtered(filters: ProductFilters) -> Select:
    query = select(Product.id).where(Product.is_active)
    if filters.in_stock_only:
        query = query.join(Inventory, Inventory.product_id == Product.id).where(
            Inventory.on_hand - Inventory.reserved > 0
        )
    if filters.min_price is not None:
        query = query.where(Product.price >= filters.min_price)
    if filters.max_price is not None:
        query = query.where(Product.price <= filters.max_price)
    if filters.occasion:
        query = query.where(_tag(TagKind.OCCASION, filters.occasion))
    if filters.recipient:
        query = query.where(_tag(TagKind.RECIPIENT, filters.recipient))
    return query


def search_products(
    db: Session,
    embedder: Embedder,
    query: str,
    filters: ProductFilters | None = None,
    limit: int = 5,
) -> list[Product]:
    """Active products matching the filters, best match for `query` first."""
    allowed = _filtered(filters or ProductFilters()).subquery()
    ids: list[int]
    if query.strip():
        [query_vector] = embedder.embed([query], "query")
        by_meaning = db.scalars(
            select(ProductVector.product_id)
            .where(ProductVector.product_id.in_(select(allowed.c.id)))
            .order_by(ProductVector.embedding.cosine_distance(query_vector))
            .limit(CANDIDATES)
        ).all()
        by_words: list[int] = []
        if (tsquery := _keyword_query(query)) is not None:
            # Searched on the product itself, so a product not indexed yet is still found.
            text = func.to_tsvector(
                "english", Product.name + " " + func.coalesce(Product.description, "")
            )
            rank = func.ts_rank_cd(text, tsquery)
            by_words = db.scalars(
                select(Product.id)
                .where(Product.id.in_(select(allowed.c.id)), text.op("@@")(tsquery))
                .order_by(rank.desc(), Product.id)
                .limit(CANDIDATES)
            ).all()
        ids = [item_id for item_id, _ in _fuse(by_meaning, by_words)][:limit]
    else:
        ids = db.scalars(
            select(Product.id)
            .where(Product.id.in_(select(allowed.c.id)))
            .order_by(Product.name)
            .limit(limit)
        ).all()
    products = {
        p.id: p
        for p in db.scalars(
            select(Product)
            .where(Product.id.in_(ids))
            .options(selectinload(Product.tags), selectinload(Product.inventory))
        )
    }
    return [products[i] for i in ids if i in products]


# Knowledge


@dataclass(frozen=True)
class SourceDocument:
    slug: str
    kind: str
    title: str
    text: str


@dataclass(frozen=True)
class Passage:
    heading: str
    text: str


class _Values(dict):
    """Leaves unknown {placeholders} as they are."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _values(settings: Settings) -> dict[str, str]:
    def rupees(amount: Decimal) -> str:
        return f"{amount:,.0f}"

    return _Values(
        delivery_fee_colombo=rupees(settings.delivery_fee_colombo),
        delivery_fee_other=rupees(settings.delivery_fee_other),
        free_delivery_over=rupees(settings.free_delivery_over),
        gift_wrap_fee=rupees(settings.gift_wrap_fee),
        reservation_minutes=str(settings.reservation_minutes),
        shop_email=settings.shop_email,
    )


def load_documents(
    root: Path = KNOWLEDGE_DIR, settings: Settings | None = None
) -> list[SourceDocument]:
    """Every Markdown file under `root` except README.md, with settings filled in."""
    values = _values(settings or get_settings())
    documents = []
    for path in sorted(root.rglob("*.md")):
        if path.name == "README.md":
            continue
        lines = [
            line for line in path.read_text().splitlines() if not line.lstrip().startswith("<!--")
        ]
        if not lines or not lines[0].startswith("# "):
            raise ValueError(f"{path} must start with '# Title'.")
        slug = path.relative_to(root).with_suffix("").as_posix()
        documents.append(
            SourceDocument(
                slug=slug,
                kind=slug.split("/")[0] if "/" in slug else "general",
                title=lines[0][2:].strip(),
                text="\n".join(lines[1:]).strip().format_map(values),
            )
        )
    return documents


def split_passages(document: SourceDocument) -> list[Passage]:
    """One passage per ## section (the text before the first heading too), each long section
    split at paragraphs. Each passage carries the document title and heading, so it reads on
    its own."""
    sections: list[tuple[str, list[str]]] = [(document.title, [])]
    for line in document.text.splitlines():
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        else:
            sections[-1][1].append(line)
    passages = []
    for heading, lines in sections:
        paragraphs = [p.strip() for p in "\n".join(lines).split("\n\n") if p.strip()]
        current: list[str] = []
        for paragraph in paragraphs:
            if current and len("\n\n".join([*current, paragraph])) > MAX_CHUNK_CHARS:
                passages.append(Passage(heading, "\n\n".join(current)))
                current = []
            current.append(paragraph)
        if current:
            passages.append(Passage(heading, "\n\n".join(current)))
    return passages


def _passage_document(document: SourceDocument, passage: Passage) -> str:
    if passage.heading == document.title:
        return f"{document.title}\n\n{passage.text}"
    return f"{document.title}: {passage.heading}\n\n{passage.text}"


def index_knowledge(
    db: Session,
    embedder: Embedder,
    documents: list[SourceDocument] | None = None,
) -> int:
    """Re-embed documents whose text or model changed, and drop removed ones.

    Returns how many documents were embedded.
    """
    documents = load_documents() if documents is None else documents
    stored = {d.slug: d for d in db.scalars(select(KnowledgeDocument))}
    changed = 0
    for source in documents:
        content_hash = _hash(embedder.model, f"{source.title}\n{source.text}")
        document = stored.get(source.slug)
        if document is not None and document.content_hash == content_hash:
            continue
        passages = split_passages(source)
        embeddings = embedder.embed([_passage_document(source, p) for p in passages], "document")
        if document is None:
            document = KnowledgeDocument(slug=source.slug)
            db.add(document)
        document.kind = source.kind
        document.title = source.title
        document.url = DOCUMENT_URLS.get(source.slug)
        document.content_hash = content_hash
        document.chunks = [
            KnowledgeChunk(position=i, heading=p.heading, text=p.text, embedding=embedding)
            for i, (p, embedding) in enumerate(zip(passages, embeddings, strict=True))
        ]
        changed += 1
    removed = set(stored) - {d.slug for d in documents}
    if removed:
        db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.slug.in_(removed)))
    if changed or removed:
        db.commit()
    return changed


def search_knowledge(
    db: Session,
    embedder: Embedder,
    query: str,
    kind: str | None = None,
    limit: int = 4,
) -> list[KnowledgeChunk]:
    """The passages that best answer `query`, optionally from one kind of document."""
    if not query.strip():
        return []
    [query_vector] = embedder.embed([query], "query")
    base = select(KnowledgeChunk.id).join(KnowledgeDocument)
    if kind:
        base = base.where(KnowledgeDocument.kind == kind)
    by_meaning = db.scalars(
        base.order_by(KnowledgeChunk.embedding.cosine_distance(query_vector)).limit(CANDIDATES)
    ).all()
    by_words: list[int] = []
    if (tsquery := _keyword_query(query)) is not None:
        rank = func.ts_rank_cd(KnowledgeChunk.search_vector, tsquery)
        by_words = db.scalars(
            base.where(KnowledgeChunk.search_vector.op("@@")(tsquery))
            .order_by(rank.desc(), KnowledgeChunk.id)
            .limit(CANDIDATES)
        ).all()
    ids = [item_id for item_id, _ in _fuse(by_meaning, by_words)][:limit]
    chunks = {
        c.id: c
        for c in db.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.id.in_(ids))
            .options(selectinload(KnowledgeChunk.document))
        )
    }
    return [chunks[i] for i in ids if i in chunks]


def describe_chunk(chunk: KnowledgeChunk) -> dict[str, Any]:
    document = chunk.document
    return {
        "document": document.title,
        "section": chunk.heading,
        "text": chunk.text,
        "url": document.url,
    }
