"""
WhatsApp router — HTTP layer for Meta Cloud API integration.

Endpoints to implement:
- GET  /whatsapp/webhook    -> webhook verification (Meta handshake)
- POST /whatsapp/webhook    -> receive incoming messages
- POST /whatsapp/send       -> send message to client
- GET  /whatsapp/conversations         -> list conversations
- GET  /whatsapp/conversations/{id}    -> get conversation with messages
- POST /whatsapp/conversations/{id}/handoff  -> switch from AI to professional
"""

from fastapi import APIRouter

router = APIRouter()

# TODO: Implement endpoints after service layer is ready
