"""Measuring search: a fixed set of questions with the products and passages that answer them.

Runs in a transaction that is rolled back. Inside it, the shop's own products are hidden and the
eval catalog below is added, so the scores are comparable from run to run and nothing changes.

    python -m app.cli search-evals                       # with the configured embedder
    EMBEDDING_PROVIDER=voyage python -m app.cli search-evals

Scores: hit@k is the share of questions with a right answer in the top k; MRR is the mean of
1 / (rank of the first right answer), 0 when none is in the top k.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import Engine, delete, update
from sqlalchemy.orm import Session

from app.embeddings import Embedder
from app.models import Inventory, KnowledgeDocument, Product, Tag, TagKind
from app.services.search import (
    ProductFilters,
    index_knowledge,
    index_products,
    search_knowledge,
    search_products,
)
from app.text import slugify

TOP_K = 5

# key: (name, description, price, on hand, occasions, recipients)
CATALOG: dict[str, tuple[str, str, str, int, list[str], list[str]]] = {
    "daisy-mug": (
        "Daisy ceramic mug",
        "Hand-painted daisy mug. Holds 350 ml, for coffee or tea.",
        "1850",
        24,
        ["Birthday", "Thank you"],
        ["For her", "For friends"],
    ),
    "teddy": (
        "Cuddly teddy bear",
        "Soft 30 cm bear with a red ribbon.",
        "3200",
        15,
        ["Birthday", "Valentine's Day", "New baby"],
        ["For kids", "For her"],
    ),
    "tea-hamper": (
        "Ceylon tea hamper",
        "Three single-estate Ceylon teas with a wooden spoon, in a gift box.",
        "5400",
        8,
        ["Christmas", "Thank you", "Mother's Day"],
        ["For parents", "For colleagues"],
    ),
    "photo-frame": (
        "Couple photo frame",
        "Wooden frame for a 6x4 photo, with 'Us' carved at the top.",
        "2750",
        12,
        ["Anniversary", "Wedding", "Valentine's Day"],
        ["For couples"],
    ),
    "teacher-pen": (
        "Engraved teacher's pen",
        "Metal ballpoint pen engraved 'Thank you, teacher', in a gift box.",
        "1500",
        20,
        ["Thank you", "Graduation"],
        ["For teachers"],
    ),
    "avurudu-card": (
        "Avurudu greeting card",
        "Folded card with a gold-foil kolam design for Sinhala and Tamil New Year.",
        "450",
        120,
        ["Avurudu"],
        ["For parents", "For friends"],
    ),
    "batik-scarf": (
        "Batik silk scarf",
        "Hand-dyed batik scarf in peacock blue, made in Kandy.",
        "4200",
        6,
        ["Birthday", "Mother's Day"],
        ["For her", "For parents"],
    ),
    "elephant-plush": (
        "Baby elephant soft toy",
        "Grey plush elephant, 20 cm, safe for newborns, no small parts.",
        "2100",
        10,
        ["New baby", "Birthday"],
        ["For kids"],
    ),
    "spice-box": (
        "Sri Lankan spice box",
        "Cinnamon, cardamom, cloves and curry powder in a carved wooden box. For keen cooks.",
        "3600",
        9,
        ["Christmas", "Thank you"],
        ["For parents", "For colleagues"],
    ),
    "scented-candle": (
        "Jasmine scented candle",
        "Soy wax candle with jasmine and sandalwood, burns for 40 hours.",
        "1950",
        18,
        ["Birthday", "Thank you", "Christmas"],
        ["For her", "For friends"],
    ),
    "cricket-mug": (
        "Cricket fan mug",
        "Mug with a vintage cricket bat and ball print. For fans of the game.",
        "1750",
        14,
        ["Birthday", "Father's Day"],
        ["For him"],
    ),
    "wallet": (
        "Leather wallet",
        "Brown leather bifold wallet with six card slots.",
        "4800",
        7,
        ["Birthday", "Father's Day", "Graduation"],
        ["For him"],
    ),
    "journal": (
        "Handmade paper journal",
        "A5 journal of handmade elephant-dung paper, 120 pages.",
        "1650",
        25,
        ["Graduation", "Thank you"],
        ["For friends", "For teachers"],
    ),
    "chocolate-box": (
        "Kithul chocolate box",
        "Twelve dark chocolates sweetened with kithul treacle.",
        "2900",
        0,  # sold out
        ["Valentine's Day", "Thank you"],
        ["For her", "For couples"],
    ),
    "wedding-album": (
        "Wedding photo album",
        "Linen-covered album with 40 pages for wedding photos.",
        "6500",
        4,
        ["Wedding", "Anniversary"],
        ["For couples"],
    ),
    "puzzle": (
        "Wooden jigsaw puzzle",
        "100-piece wooden puzzle of Sigiriya, for ages 6 and up.",
        "2400",
        11,
        ["Birthday", "Christmas"],
        ["For kids"],
    ),
}


@dataclass(frozen=True)
class ProductQuestion:
    question: str
    expected: set[str]  # catalog keys, any of which is a right answer
    filters: ProductFilters = field(default_factory=ProductFilters)
    # Keys that must not come back at all (with no `expected`, the question is right when none
    # of these do).
    absent: set[str] = field(default_factory=set)


PRODUCT_QUESTIONS = [
    ProductQuestion("teddy bear", {"teddy"}),
    ProductQuestion("tea hamper", {"tea-hamper"}),
    ProductQuestion("something for a coffee lover", {"daisy-mug", "cricket-mug"}),
    ProductQuestion("a gift for my dad who loves cricket", {"cricket-mug"}),
    ProductQuestion("present for a newborn baby", {"elephant-plush", "teddy"}),
    ProductQuestion("thank you gift for my child's teacher", {"teacher-pen", "journal"}),
    ProductQuestion("something for my mum who loves cooking", {"spice-box"}),
    ProductQuestion("a gift for a couple getting married", {"wedding-album", "photo-frame"}),
    ProductQuestion("New Year card", {"avurudu-card"}),
    ProductQuestion("something that smells nice", {"scented-candle"}),
    ProductQuestion("traditional Sri Lankan fabric", {"batik-scarf"}),
    ProductQuestion("a toy for a 7 year old", {"puzzle", "teddy"}),
    ProductQuestion("somewhere to write notes", {"journal"}),
    ProductQuestion("men's accessories", {"wallet"}),
    ProductQuestion("chocolates", set(), absent={"chocolate-box"}),  # sold out
    ProductQuestion(
        "chocolates", {"chocolate-box"}, ProductFilters(in_stock_only=False)
    ),  # unless sold-out items are allowed
    ProductQuestion(
        "a birthday gift under 2000 rupees",
        {"daisy-mug", "scented-candle", "cricket-mug"},
        ProductFilters(max_price=Decimal("2000"), occasion="Birthday"),
    ),
    ProductQuestion("", {"photo-frame", "wedding-album"}, ProductFilters(recipient="For couples")),
]


@dataclass(frozen=True)
class KnowledgeQuestion:
    question: str
    expected: set[tuple[str, str]]  # (document slug, section heading)


KNOWLEDGE_QUESTIONS = [
    KnowledgeQuestion("How much is delivery to Kandy?", {("policies/shipping", "What it costs")}),
    KnowledgeQuestion("Is delivery free?", {("policies/shipping", "What it costs")}),
    KnowledgeQuestion(
        "How long will my parcel take to arrive?",
        {
            ("policies/shipping", "How long it takes"),
            ("faq/gifts", "Can I choose the delivery day?"),
        },
    ),
    KnowledgeQuestion(
        "Where is my order? I want the tracking number", {("policies/shipping", "Tracking")}
    ),
    KnowledgeQuestion(
        "My mug arrived broken", {("policies/returns", "Damaged, faulty or wrong items")}
    ),
    KnowledgeQuestion(
        "Can I send back something I don't like?", {("policies/returns", "Changing your mind")}
    ),
    KnowledgeQuestion(
        "When will I get my money back?", {("policies/returns", "How refunds are paid")}
    ),
    KnowledgeQuestion("I want to cancel my order", {("policies/returns", "Cancelling an order")}),
    KnowledgeQuestion(
        "Do you keep my card number?",
        {("policies/privacy", "What we collect"), ("faq/orders-and-payment", "How can I pay?")},
    ),
    KnowledgeQuestion("Do you use cookies?", {("policies/privacy", "Cookies")}),
    KnowledgeQuestion("Can you delete my data?", {("policies/privacy", "Your rights")}),
    KnowledgeQuestion(
        "Can I pay cash on delivery?", {("faq/orders-and-payment", "How can I pay?")}
    ),
    KnowledgeQuestion(
        "My payment didn't work", {("faq/orders-and-payment", "My payment failed. What now?")}
    ),
    KnowledgeQuestion(
        "Can I change the address after ordering?",
        {("faq/orders-and-payment", "Can I change my order or the delivery address?")},
    ),
    KnowledgeQuestion(
        "Do you wrap presents?",
        {("faq/gifts", "Can you gift wrap my order?"), ("policies/shipping", "What it costs")},
    ),
    KnowledgeQuestion(
        "Will my friend see how much I paid?",
        {
            ("faq/gifts", "Will the price be in the parcel?"),
            ("policies/shipping", "Sending a gift"),
        },
    ),
    KnowledgeQuestion(
        "How long do you hold items while I pay?",
        {
            ("policies/terms", "Your order"),
            ("faq/orders-and-payment", "My payment failed. What now?"),
        },
    ),
    KnowledgeQuestion("Gift ideas for Avurudu", {("guides/occasions", "Avurudu")}),
    KnowledgeQuestion(
        "What should I get my brother for his birthday?",
        {("guides/birthdays", "Birthday gifts for him")},
    ),
    KnowledgeQuestion("Christmas order deadline", {("guides/occasions", "Christmas")}),
]


@dataclass
class Score:
    name: str
    questions: int = 0
    hits_at_1: int = 0
    hits_at_k: int = 0
    reciprocal_ranks: float = 0.0
    misses: list[str] = field(default_factory=list)

    def add(self, question: str, ranked: list, expected: set, absent: set | None = None) -> None:
        self.questions += 1
        if shown := set(ranked) & (absent or set()):
            self.misses.append(f"{question!r}: shouldn't have found {sorted(shown)}")
            return
        if not expected:
            self.hits_at_1 += 1
            self.hits_at_k += 1
            self.reciprocal_ranks += 1
            return
        rank = next((i for i, item in enumerate(ranked[:TOP_K], 1) if item in expected), None)
        if rank is None:
            self.misses.append(f"{question!r}: got {ranked[:TOP_K]}")
            return
        self.hits_at_1 += rank == 1
        self.hits_at_k += 1
        self.reciprocal_ranks += 1 / rank

    @property
    def hit_at_1(self) -> float:
        return self.hits_at_1 / self.questions

    @property
    def hit_at_k(self) -> float:
        return self.hits_at_k / self.questions

    @property
    def mrr(self) -> float:
        return self.reciprocal_ranks / self.questions

    def summary(self) -> str:
        return (
            f"{self.name}: hit@1 {self.hit_at_1:.0%}, hit@{TOP_K} {self.hit_at_k:.0%}, "
            f"MRR {self.mrr:.2f} ({self.questions} questions)"
        )


def _add_catalog(db: Session) -> dict[int, str]:
    """The eval catalog, with the shop's own products hidden. Returns product id -> key."""
    db.execute(update(Product).values(is_active=False))
    tags: dict[tuple[TagKind, str], Tag] = {}

    def tag(kind: TagKind, name: str) -> Tag:
        if (kind, name) not in tags:
            tags[(kind, name)] = Tag(kind=kind, slug=f"eval-{slugify(name)}", name=name)
        return tags[(kind, name)]

    keys = {}
    for key, (name, description, price, on_hand, occasions, recipients) in CATALOG.items():
        product = Product(
            sku=f"EVAL-{uuid.uuid4().hex[:8]}",
            slug=f"eval-{key}-{uuid.uuid4().hex[:6]}",
            name=name,
            description=description,
            price=Decimal(price),
            inventory=Inventory(on_hand=on_hand),
            tags=[tag(TagKind.OCCASION, o) for o in occasions]
            + [tag(TagKind.RECIPIENT, r) for r in recipients],
        )
        db.add(product)
        db.flush()
        keys[product.id] = key
    return keys


def measure(db: Session, embedder: Embedder) -> tuple[Score, Score]:
    """Score product and knowledge search in `db`. The caller rolls the session back."""
    keys = _add_catalog(db)
    db.execute(delete(KnowledgeDocument))
    index_products(db, embedder)
    index_knowledge(db, embedder)

    products = Score("Products")
    for q in PRODUCT_QUESTIONS:
        found = search_products(db, embedder, q.question, q.filters, limit=TOP_K)
        ranked = [keys.get(p.id, p.slug) for p in found]
        products.add(q.question or str(q.filters), ranked, q.expected, q.absent)
    knowledge = Score("Knowledge")
    for q in KNOWLEDGE_QUESTIONS:
        found = search_knowledge(db, embedder, q.question, limit=TOP_K)
        knowledge.add(q.question, [(c.document.slug, c.heading) for c in found], q.expected)
    return products, knowledge


def run(engine: Engine, embedder: Embedder) -> tuple[Score, Score]:
    with engine.connect() as connection:
        transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            return measure(db, embedder)
        finally:
            db.close()
            transaction.rollback()
