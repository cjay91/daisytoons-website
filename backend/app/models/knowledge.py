"""Search indexes for agents (Part 9): product vectors, and knowledge passages."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.embeddings import DIMENSIONS
from app.models.base import Base


class ProductVector(Base):
    """A product's text as a vector. Rebuilt when the text or the embedding model changes."""

    __tablename__ = "product_vectors"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    document: Mapped[str] = mapped_column(Text)
    # Of the model and the text, to tell when the vector is out of date.
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSIONS))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "ix_product_vectors_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The file's path under backend/knowledge, without .md, such as "policies/returns".
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)  # policies, faq, guides, ...
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(200))  # a storefront page, if it has one
    content_hash: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="KnowledgeChunk.position"
    )


class KnowledgeChunk(Base):
    """One passage: a section of a document, small enough to hand an agent on its own."""

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int]
    heading: Mapped[str] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(DIMENSIONS))
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', heading || ' ' || text)", persisted=True),
    )

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")

    __table_args__ = (
        Index(
            "ix_knowledge_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_knowledge_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )
