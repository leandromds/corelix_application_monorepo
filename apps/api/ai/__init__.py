"""
AI module — OpenAI-compatible API integration.

This module provides AI capabilities across the application:
- Conversational AI for WhatsApp
- Report generation with insights
- Smart scheduling suggestions

The provider is fully configurable via environment variables (AI_BASE_URL,
AI_API_KEY, AI_MODEL), making it compatible with OpenAI, OpenRouter,
LiteLLM, Ollama, and any other OpenAI-compatible endpoint.

All prompts are centralized in prompts.py for versioning and consistency.
"""
