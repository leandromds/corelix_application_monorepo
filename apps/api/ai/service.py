"""
AI service — Anthropic Claude integration.

This is a transversal service: it has no router or repository.
It is called by other service layers (reports, whatsapp) when AI is needed.

Design decision: AI as a service, not a module with endpoints.
The AI is an internal capability, not directly exposed via HTTP.
"""

import anthropic

from core.config import settings


class AIService:
    """
    Centralized interface with Anthropic Claude API.

    Usage (from another service):

        ai = AIService()
        response = await ai.complete(
            system_prompt=PROMPTS["whatsapp_secretary"],
            user_message="Quero agendar uma consulta para quinta-feira",
        )
    """

    def __init__(self) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.default_model = "claude-sonnet-4-5"

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
        model: str | None = None,
    ) -> str:
        """
        Send a message to Claude and return the text response.

        Args:
            system_prompt: System context / persona instructions
            user_message: The user message to respond to
            max_tokens: Maximum tokens in the response
            model: Override default model (optional)

        Returns:
            Claude response as plain text

        Raises:
            core.exceptions.ExternalServiceError: If Anthropic API fails
        """
        from core.exceptions import ExternalServiceError

        try:
            message = await self.client.messages.create(
                model=model or self.default_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            # message.content is a list; first item is the text block
            return str(message.content[0].text)  # type: ignore[union-attr]
        except anthropic.APIError as e:
            raise ExternalServiceError(
                message=f"Anthropic API error: {e.message}",
                service_name="anthropic",
            ) from e

    async def complete_with_history(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        max_tokens: int = 1024,
    ) -> str:
        """
        Send a conversation history to Claude.

        Used for WhatsApp conversations where we need context
        from previous messages in the thread.

        Args:
            system_prompt: System context / persona instructions
            messages: List of {"role": "user"|"assistant", "content": "..."}
            max_tokens: Maximum tokens in the response

        Returns:
            Claude response as plain text
        """
        from core.exceptions import ExternalServiceError

        try:
            message = await self.client.messages.create(
                model=self.default_model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )
            return str(message.content[0].text)  # type: ignore[union-attr]
        except anthropic.APIError as e:
            raise ExternalServiceError(
                message=f"Anthropic API error: {e.message}",
                service_name="anthropic",
            ) from e
