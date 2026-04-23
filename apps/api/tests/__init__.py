"""
Test suite for Secretária Digital API.

Structure:
- conftest.py: Shared fixtures (database, clients, factories)
- auth/: Authentication and authorization tests
- professionals/: Professional profile tests
- clients/: Client management tests
- agenda/: Scheduling and availability tests
- reports/: Reports and analytics tests
- whatsapp/: WhatsApp integration tests
- ai/: AI service tests

Each module follows TDD with:
- test_router.py: HTTP endpoint tests
- test_service.py: Business logic tests
- test_repository.py: Database layer tests
"""
