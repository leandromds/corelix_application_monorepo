# 006 - Sem `relationship()` nos Models SQLAlchemy

**Status:** `accepted`

---

## Context

SQLAlchemy oferece o mecanismo de `relationship()` para navegar entre entidades relacionadas
diretamente via atributos Python:

```python
# Com relationship() — o que foi evitado
class Professional(Base):
    clients: Mapped[list["Client"]] = relationship("Client", back_populates="professional")

# Uso: professional.clients  ← dispara SELECT implícito
```

Em um sistema multi-tenant com RLS ativo, esse mecanismo cria riscos específicos:

1. **Carregamento implícito entre tenants:** se o contexto de tenant (`SET LOCAL`) não estiver
   ativo no momento em que o ORM resolve um atributo lazy-loaded, a query executa sem RLS —
   potencialmente retornando dados de outro tenant.

2. **Lazy loading em contexto async:** SQLAlchemy async não suporta lazy loading por padrão.
   Acessar um atributo lazy em um contexto assíncrono lança `MissingGreenlet` — um erro runtime
   silencioso durante desenvolvimento que se manifesta em produção.

3. **Imports circulares:** em uma arquitetura feature-based, `clients/models.py` importaria
   `professionals/models.py` (e vice-versa em back_populates), criando dependências circulares
   entre módulos que deveriam ser isolados.

4. **Acoplamento arquitetural:** `relationship()` nos models significa que o model sabe sobre
   outros models — violando o princípio de que a camada de modelo deve ser "burra" (só colunas).
   A lógica de navegação pertence ao repository.

## Decision

**Nenhum model usa `relationship()`.** Os models contêm apenas colunas e constraints.

Navegação entre entidades é feita exclusivamente via **queries explícitas nos repositories**:

```python
# models.py — apenas colunas e FK
class Client(Base, TimestampMixin):
    __tablename__ = "clients"

    professional_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professionals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ... apenas colunas, sem relationship()


# repository.py — navegação explícita
class ClientsRepository:
    async def find_all_for_professional(
        self, db: AsyncSession, professional_id: UUID
    ) -> list[Client]:
        result = await db.execute(
            select(Client).where(Client.professional_id == professional_id)
        )
        return result.scalars().all()
```

## Rationale

- **Segurança:** queries explícitas sempre passam pelo RLS (contexto de tenant ativo na sessão).
  Não há carregamento implícito que possa escapar da barreira.
- **Previsibilidade:** todo acesso ao banco é visível e rastreável — sem "magic" do ORM que
  dispara queries ocultas.
- **Compatibilidade async:** async SQLAlchemy requer `selectinload` / `joinedload` explícitos para
  eager loading. Sem `relationship()`, essa complexidade não existe.
- **Isolamento de módulos:** `clients/models.py` não importa `professionals/models.py`.
  Os módulos são independentes — sem imports circulares.
- **Testabilidade:** repositories são testados com queries diretas contra o banco de teste.
  Sem `relationship()`, não há comportamento de ORM a mockar.

## Consequences

**Positivos:**
- Sem risco de lazy loading cruzando fronteiras de tenant
- Sem `MissingGreenlet` em contexto async
- Sem imports circulares entre módulos
- Queries previsíveis e auditáveis

**Negativos / Trade-offs:**
- Mais código por operação — cada join ou navegação exige uma query explícita no repository
- Sem conveniência de `professional.clients` — o dev precisa chamar `repository.find_all(professional_id)`
- Não se aproveita o eager loading automático do SQLAlchemy (`selectinload`)

**Regra de ouro:** se você precisar de dados de outra tabela, escreva uma query no repository.
Nunca acesse dados de outro módulo via atributo de model.