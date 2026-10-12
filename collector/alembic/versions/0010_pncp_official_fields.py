"""Campo oficial de edital/aviso nos snapshots de processo.

Revision ID: 0010_pncp_official_fields
Revises: 0009_internal_auth
Create Date: 2026-10-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_pncp_official_fields"
down_revision: Union[str, Sequence[str], None] = "0009_internal_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "process_observations",
        sa.Column("notice_number", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("process_observations", "notice_number")
