"""LLM provider abstraction layer supporting Perplexity and Claude."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx
from anthropic import AsyncAnthropic

from ..config import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Send a completion request and return the response text.

        Args:
            prompt: The user prompt to send.
            system: Optional system prompt for context.

        Returns:
            The model's response text.
        """
        pass

    @abstractmethod
    async def complete_json(
        self, prompt: str, system: str | None = None
    ) -> dict[str, Any]:
        """Send a completion request expecting JSON response.

        Args:
            prompt: The user prompt to send.
            system: Optional system prompt for context.

        Returns:
            Parsed JSON response as a dictionary.

        Raises:
            json.JSONDecodeError: If the response is not valid JSON.
        """
        pass


class PerplexityProvider(LLMProvider):
    """Perplexity API implementation using httpx."""

    API_URL = "https://api.perplexity.ai/chat/completions"
    DEFAULT_MODEL = "sonar"

    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def _make_request(
        self, prompt: str, system: str | None = None
    ) -> str:
        """Make a request to the Perplexity API."""
        client = await self._get_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
        }

        response = await client.post(self.API_URL, json=payload)
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Send a completion request to Perplexity."""
        logger.debug(f"Perplexity completion request: {prompt[:100]}...")
        return await self._make_request(prompt, system)

    async def complete_json(
        self, prompt: str, system: str | None = None
    ) -> dict[str, Any]:
        """Send a completion request expecting JSON response."""
        json_system = (system or "") + "\nRespond only with valid JSON."
        response = await self._make_request(prompt, json_system.strip())

        # Try to extract JSON from the response
        response = response.strip()

        # Handle markdown code blocks
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        return json.loads(response.strip())

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


class ClaudeProvider(LLMProvider):
    """Claude API implementation using the anthropic SDK."""

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"

    def __init__(self, api_key: str, model: str | None = None):
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL
        self._client = AsyncAnthropic(api_key=api_key)

    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Send a completion request to Claude."""
        logger.debug(f"Claude completion request: {prompt[:100]}...")

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system:
            kwargs["system"] = system

        message = await self._client.messages.create(**kwargs)
        return message.content[0].text

    async def complete_json(
        self, prompt: str, system: str | None = None
    ) -> dict[str, Any]:
        """Send a completion request expecting JSON response."""
        json_system = (system or "") + "\nRespond only with valid JSON."

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "system": json_system.strip(),
        }

        message = await self._client.messages.create(**kwargs)
        response = message.content[0].text.strip()

        # Handle markdown code blocks
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        return json.loads(response.strip())

    async def close(self) -> None:
        """Close the client (no-op for anthropic SDK)."""
        pass


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Factory function to get the configured LLM provider.

    Args:
        settings: Optional settings instance. Uses global settings if not provided.

    Returns:
        Configured LLM provider instance.

    Raises:
        ValueError: If the configured provider is not supported.
    """
    if settings is None:
        settings = get_settings()

    if settings.llm_provider == "claude":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Claude provider")
        return ClaudeProvider(settings.anthropic_api_key)

    if settings.llm_provider == "perplexity":
        if not settings.perplexity_api_key:
            raise ValueError("PERPLEXITY_API_KEY is required for Perplexity provider")
        return PerplexityProvider(settings.perplexity_api_key)

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
