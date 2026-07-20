"""
AI service — OpenAI-compatible API integration.

This is a transversal service: it has no router or repository.
It is called by other service layers (reports, whatsapp) when AI is needed.

Design decision: AI as a service, not a module with endpoints.
The AI is an internal capability, not directly exposed via HTTP.

The OpenAI SDK is used with a configurable base_url, making this service
compatible with any OpenAI-compatible provider:
  - OpenAI (default)
  - OpenRouter (https://openrouter.ai/api/v1)
  - LiteLLM proxy
  - Local Ollama (http://localhost:11434/v1)
  - Any other compatible endpoint
"""

import openai

from core.config import settings


class AIService:
    """
    Centralized interface for AI completion via OpenAI-compatible API.

    The provider and model are fully configurable via environment variables:
      AI_BASE_URL — API endpoint (default: https://api.openai.com/v1)
      AI_API_KEY  — API key for the provider
      AI_MODEL    — model identifier (e.g. gpt-4o-mini, mistral-small, etc.)

    Usage (from another service):

        ai = AIService()
        response = await ai.complete(
            system_prompt=PROMPTS["whatsapp_secretary"],
            user_message="Quero agendar uma consulta para quinta-feira",
        )
    """

    def __init__(self) -> None:
        self.client = openai.AsyncOpenAI(
            api_key=settings.AI_API_KEY,
            base_url=settings.AI_BASE_URL,
        )
        self.default_model = settings.AI_MODEL

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
        model: str | None = None,
    ) -> str:
        """
        Send a single message to the AI and return the text response.

        The system_prompt is sent as a system-role message, followed by the
        user_message as a user-role message — standard chat completions format.

        Args:
            system_prompt: System context / persona instructions.
            user_message: The user message to respond to.
            max_tokens: Maximum tokens in the response.
            model: Override the default model for this call (optional).

        Returns:
            AI response as plain text.

        Raises:
            core.exceptions.ExternalServiceError: If the AI API call fails.
        """
        from core.exceptions import ExternalServiceError

        try:
            response = await self.client.chat.completions.create(
                model=model or self.default_model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            content = response.choices[0].message.content
            return content if content is not None else ""
        except openai.APIError as e:
            raise ExternalServiceError(
                message=f"AI API error: {e}",
                service_name="ai",
            ) from e

    async def complete_with_history(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a conversation history to the AI.

        Used for WhatsApp conversations where we need context from previous
        messages in the thread. The system_prompt is prepended as a system-role
        message before the conversation history.

        Args:
            system_prompt: System context / persona instructions.
            messages: List of {"role": "user"|"assistant", "content": "..."}.
                      Must follow the OpenAI chat completions message format.
            max_tokens: Maximum tokens in the response.

        Returns:
            AI response as plain text.

        Raises:
            core.exceptions.ExternalServiceError: If the AI API call fails.
        """
        from core.exceptions import ExternalServiceError

        all_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.default_model,
                max_tokens=max_tokens,
                messages=all_messages,  # type: ignore[arg-type]
            )
            content = response.choices[0].message.content
            return content if content is not None else ""
        except openai.APIError as e:
            raise ExternalServiceError(
                message=f"AI API error: {e}",
                service_name="ai",
            ) from e
