"""search indexes for agents

Revision ID: 285d4dd632a3
Revises: 337e465fbfb5
Create Date: 2026-10-30 11:54:03.139437

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "285d4dd632a3"
down_revision: str | Sequence[str] | None = "337e465fbfb5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("url", sa.String(length=200), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_documents")),
        sa.UniqueConstraint("slug", name=op.f("uq_knowledge_documents_slug")),
    )
    op.create_index(
        op.f("ix_knowledge_documents_kind"), "knowledge_documents", ["kind"], unique=False
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("heading", sa.String(length=200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', heading || ' ' || text)", persisted=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["knowledge_documents.id"],
            name=op.f("fk_knowledge_chunks_document_id_knowledge_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_chunks")),
    )
    op.create_index(
        op.f("ix_knowledge_chunks_document_id"), "knowledge_chunks", ["document_id"], unique=False
    )
    op.create_index(
        "ix_knowledge_chunks_embedding",
        "knowledge_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_knowledge_chunks_search_vector",
        "knowledge_chunks",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "product_vectors",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("document", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_vectors_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("product_id", name=op.f("pk_product_vectors")),
    )
    op.create_index(
        "ix_product_vectors_embedding",
        "product_vectors",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_product_vectors_embedding",
        table_name="product_vectors",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_table("product_vectors")
    op.drop_index(
        "ix_knowledge_chunks_search_vector", table_name="knowledge_chunks", postgresql_using="gin"
    )
    op.drop_index(
        "ix_knowledge_chunks_embedding",
        table_name="knowledge_chunks",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.drop_index(op.f("ix_knowledge_chunks_document_id"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_documents_kind"), table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
