"""
SQLAlchemy mixins para padrões de timestamp.

Separado de core/database.py para deixar explícito, no próprio model,
qual padrão de auditoria aquela tabela segue.

Uso:
    class Professional(TimestampMixin, Base): ...  # created_at + updated_at
    class RefreshToken(CreatedAtMixin, Base): ...   # created_at apenas (imutável)
    class WhatsAppMessage(Base): ...                # campo próprio: sent_at
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP


class TimestampMixin:
    """
    Adiciona created_at e updated_at ao model.

    Usar em tabelas que registram criação E última modificação:
    professionals, clients, availability_slots, sessions,
    recurrences, whatsapp_conversations.

    Nota: updated_at usa onupdate=func.now() que é aplicado pelo ORM
    no UPDATE. Para atualizações via SQL puro, adicionar um trigger
    no PostgreSQL se necessário (não é o caso do MVP).
    """

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CreatedAtMixin:
    """
    Adiciona apenas created_at ao model.

    Usar em tabelas de registros imutáveis — que não fazem sentido
    ter updated_at porque nunca são editados:
    - refresh_tokens: token é criado e revogado (campo revoked), nunca editado
    - blocked_periods: bloqueio é criado ou deletado, nunca editado
    - audit_logs: log de auditoria é imutável por definição
    """

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
