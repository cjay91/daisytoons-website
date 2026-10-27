"""Staff two-step login: the authenticator app secret, when it was turned on, and the last
code step used.

Revision ID: b0d2617ea8e6
Revises: ee5ddcbad4b0
Create Date: 2026-10-27 14:02:26.936251

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b0d2617ea8e6"
down_revision: str | Sequence[str] | None = "ee5ddcbad4b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("staff", sa.Column("totp_secret", sa.String(length=64), nullable=True))
    op.add_column("staff", sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("staff", sa.Column("totp_last_step", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("staff", "totp_last_step")
    op.drop_column("staff", "totp_enabled_at")
    op.drop_column("staff", "totp_secret")
