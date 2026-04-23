"""
Agenda router — HTTP layer for scheduling management.

Endpoints to implement:
- GET    /agenda/availability              -> get professional availability slots
- POST   /agenda/availability              -> create availability slot
- DELETE /agenda/availability/{id}         -> remove availability slot

- GET    /agenda/blocked-periods           -> list blocked periods
- POST   /agenda/blocked-periods           -> create blocked period
- DELETE /agenda/blocked-periods/{id}      -> remove blocked period

- GET    /agenda/sessions                  -> list sessions (with filters)
- POST   /agenda/sessions                  -> schedule new session
- GET    /agenda/sessions/{id}             -> get session details
- PATCH  /agenda/sessions/{id}             -> update session
- PATCH  /agenda/sessions/{id}/status      -> update session status

- GET    /agenda/recurrences               -> list recurrences
- POST   /agenda/recurrences               -> create recurrence
- DELETE /agenda/recurrences/{id}          -> cancel recurrence
"""

from fastapi import APIRouter

router = APIRouter()

# TODO: Implement endpoints after service layer is ready
