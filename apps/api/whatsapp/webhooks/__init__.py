"""
Webhook routers para providers WhatsApp (ADR-028).

Submodules:
  - meta: GET/POST /webhooks/whatsapp/meta (Meta Cloud API)
  - twilio: POST /webhooks/whatsapp/twilio (Twilio Shared Account)

Todos os endpoints respondem 200 imediatamente e delegam o processamento
real para background tasks com sessão própria.
"""
