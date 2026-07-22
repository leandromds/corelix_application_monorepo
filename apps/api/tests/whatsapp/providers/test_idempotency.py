"""Tests for WhatsApp message idempotency (cross-provider concern)."""


import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whatsapp.models import WhatsAppProviderMessage
from whatsapp.repository import ProviderMessageRepository


class TestProviderMessageIdempotency:
    async def test_exists_returns_false_for_new_message(
        self, tenant_session: AsyncSession, test_professional
    ):
        repo = ProviderMessageRepository(tenant_session)
        exists = await repo.exists(
            professional_id=test_professional.id,
            provider_message_id="SM_NEW_001",
        )
        assert exists is False

    async def test_exists_returns_true_after_create(
        self, tenant_session: AsyncSession, test_professional
    ):
        repo = ProviderMessageRepository(tenant_session)
        await repo.create(
            professional_id=test_professional.id,
            provider_message_id="SM_CREATED_001",
            direction="inbound",
            from_phone="+5511999999999",
            to_phone="+5511000000000",
            body="oi",
            provider_type="twilio_shared",
        )
        exists = await repo.exists(
            professional_id=test_professional.id,
            provider_message_id="SM_CREATED_001",
        )
        assert exists is True

    async def test_same_message_id_different_professional_is_allowed(
        self, db_session: AsyncSession, test_professional
    ):
        """IDs de mensagem de providers diferentes não colidem entre tenants."""
        from core.security import hash_password
        from professionals.models import Professional

        # Criar segundo profissional
        prof2 = Professional(
            email="idempotency_test2@example.com",
            password_hash=hash_password("password"),
            full_name="Prof 2",
        )
        db_session.add(prof2)
        await db_session.flush()

        repo = ProviderMessageRepository(db_session)
        # Mesmo provider_message_id mas para profissionais diferentes é PERMITIDO
        await repo.create(
            professional_id=test_professional.id,
            provider_message_id="SM_SHARED_ID",
            direction="inbound",
            from_phone="+5511999999999",
            to_phone="+5511000000000",
            body="msg1",
            provider_type="twilio_shared",
        )
        # Segundo create com mesmo ID mas profissional diferente deve funcionar
        await repo.create(
            professional_id=prof2.id,
            provider_message_id="SM_SHARED_ID",
            direction="inbound",
            from_phone="+5511999999999",
            to_phone="+5511000000000",
            body="msg2",
            provider_type="twilio_shared",
        )
        # Ambos criados com sucesso
        count = await db_session.scalar(
            select(func.count())
            .select_from(WhatsAppProviderMessage)
            .where(WhatsAppProviderMessage.provider_message_id == "SM_SHARED_ID")
        )
        assert count == 2

    async def test_duplicate_message_id_same_professional_raises(
        self, tenant_session: AsyncSession, test_professional
    ):
        """Mesmo professional_id + provider_message_id deve levantar IntegrityError."""
        from sqlalchemy.exc import IntegrityError

        repo = ProviderMessageRepository(tenant_session)
        await repo.create(
            professional_id=test_professional.id,
            provider_message_id="SM_DUP_001",
            direction="inbound",
            from_phone="+5511999999999",
            to_phone="+5511000000000",
            body="primeira entrega",
            provider_type="twilio_shared",
        )
        with pytest.raises(IntegrityError):
            await repo.create(
                professional_id=test_professional.id,
                provider_message_id="SM_DUP_001",  # mesmo ID
                direction="inbound",
                from_phone="+5511999999999",
                to_phone="+5511000000000",
                body="re-entrega duplicada",
                provider_type="twilio_shared",
            )
