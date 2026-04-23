"""
Clients router — HTTP layer for client management.

All endpoints require authentication (tenant-isolated via RLS).

Endpoints to implement:
- GET    /clients           -> list all clients (with pagination)
- POST   /clients           -> create new client
- GET    /clients/{id}      -> get client details
- PATCH  /clients/{id}      -> update client
- DELETE /clients/{id}      -> deactivate client (soft delete)
"""

from fastapi import APIRouter

router = APIRouter()

# TODO: Implement endpoints after service layer is ready
