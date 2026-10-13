"""Durable scheduling and owner execution freeze; immutable schema snapshot."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.add_column(
        "wallets",
        sa.Column("execution_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("wallets", sa.Column("generating_run_id", sa.String(36), nullable=True))
    op.create_table(
        "automation",
        sa.Column("wallet_id", sa.String(42), sa.ForeignKey("wallets.id"), primary_key=True),
        sa.Column("policy_version_id", sa.String(36), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("running", sa.Boolean(), nullable=False),
        sa.Column("check_id", sa.String(36), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result", sa.String(240), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO automation (wallet_id, enabled, running, interval_seconds, "
            "last_result, consecutive_failures) "
            "SELECT id, false, false, 300, 'Not enabled', 0 FROM wallets"
        )
    )


def downgrade() -> None:
    op.drop_table("automation")
    op.drop_column("wallets", "generating_run_id")
    op.drop_column("wallets", "execution_paused")
