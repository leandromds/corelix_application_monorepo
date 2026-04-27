# 004 - Feature-Based Backend Architecture

**Status:** `accepted`

---

## Context

The backend needed a consistent structure that a solo developer (frontend-first) could follow
without ambiguity. Without explicit layer boundaries, it's easy for HTTP concerns to leak into
business logic, or for database queries to appear inside routers — making the codebase hard to
test and reason about.

## Decision

Every backend module follows a strict 4-file, 3-layer structure:

```
{module}/
├── router.py      → HTTP only: receives request, calls service, returns response
├── service.py     → business rules: logic, validations, orchestration
├── repository.py  → database only: ORM queries, nothing else
└── schemas.py     → Pydantic models: input validation and output serialization
```

Dependency flow (never violate):

```
router → service → repository → banco
              ↓
         ai/service       (when AI is needed)
              ↓
      whatsapp/service    (when sending messages)
```

Modules: `auth` / `professionals` / `clients` / `agenda` / `reports` / `whatsapp` / `ai` / `core`

## Rationale

**Clear separation of concerns:**
- Router never touches the database directly — no `db.execute()` inside a router function
- Repository never contains business rules — no `if` logic deciding what data means
- Service never knows HTTP exists — no `Request`, no `Response`, no status codes

**Testability by layer:**
- Repository tests: verify queries against a real test database
- Service tests: mock the repository, test pure business logic
- Router tests: use `AsyncClient`, test HTTP contracts (status codes, request/response shapes)

**Frontend analogy:** this is the backend equivalent of separating `api/` calls from React
components. The component doesn't write SQL — it calls a hook, which calls a service, which
talks to the API. Same principle, same reasons.

**Predictability for a solo dev:** when something breaks, the layer tells you where to look.
401? Router or auth middleware. Wrong data returned? Service logic. Data not persisted? Repository.

## Consequences

- Every new module requires at least 4 files, even for simple CRUD — intentional overhead that
  pays off in testability and maintainability
- AI and WhatsApp are services, not modules with their own routers — they are called *by* the
  service layer of other modules (e.g. `whatsapp/service.py` calls `ai/service.py`)
- `router.py` is allowed to call `Depends()` for injection (session, current user) but all
  business decisions must happen in `service.py`
- Circular imports are prevented by the one-directional flow — `repository.py` never imports
  from `service.py`, `service.py` never imports from `router.py`
