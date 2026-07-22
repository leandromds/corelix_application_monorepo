"""whatsapp providers schema

Revision ID: b2c3d4e5f6a7
Revises: 56f1e41b5d4c
Create Date: 2026-05-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "56f1e41b5d4c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- whatsapp_accounts ---
    op.create_table(
        "whatsapp_accounts",
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("provider_type", sa.Text(), nullable=False),
        sa.Column("phone_number", sa.Text(), nullable=False),
        sa.Column("phone_number_id", sa.Text(), nullable=False),
        sa.Column("access_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("routing_tag", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "provider_type IN ('meta', 'twilio_shared')", name="chk_wa_account_provider_type"
        ),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("professional_id"),
        sa.UniqueConstraint("routing_tag"),
    )

    # --- whatsapp_phone_bindings ---
    op.create_table(
        "whatsapp_phone_bindings",
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("phone_number", sa.Text(), nullable=False),
        sa.Column("bound_via", sa.Text(), nullable=False),
        sa.Column(
            "bound_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("bound_via IN ('tag', 'qr', 'manual')", name="chk_bound_via"),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number", "professional_id", name="uq_phone_binding"),
    )
    op.create_index("ix_phone_bindings_phone", "whatsapp_phone_bindings", ["phone_number"])

    # --- whatsapp_provider_messages (idempotency log) ---
    op.create_table(
        "whatsapp_provider_messages",
        sa.Column("professional_id", sa.UUID(), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("from_phone", sa.Text(), nullable=False),
        sa.Column("to_phone", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider_type", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound')", name="chk_provider_msg_direction"
        ),
        sa.ForeignKeyConstraint(["professional_id"], ["professionals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("professional_id", "provider_message_id", name="uq_provider_msg"),
    )

    # --- RLS para todas as 3 tabelas ---
    for table in ["whatsapp_accounts", "whatsapp_phone_bindings", "whatsapp_provider_messages"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (professional_id = current_setting('app.current_tenant', TRUE)::UUID)
            WITH CHECK (professional_id = current_setting('app.current_tenant', TRUE)::UUID)
        """)


def downgrade() -> None:
    for table in ["whatsapp_accounts", "whatsapp_phone_bindings", "whatsapp_provider_messages"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_table("whatsapp_provider_messages")
    op.drop_index("ix_phone_bindings_phone", "whatsapp_phone_bindings")
    op.drop_table("whatsapp_phone_bindings")
    op.drop_table("whatsapp_accounts")
