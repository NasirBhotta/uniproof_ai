from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StructuredLLM(Protocol):
    """Small provider-neutral contract for the only LLM capability we need.

    The user can implement this with Gemini, OpenAI, Claude, a local model, etc.
    The rest of the project never imports a provider SDK.
    """

    def generate_structured(
        self,
        *,
        system: str,
        prompt: str,
        response_model: type[T],
    ) -> T:
        ...


class LLMNotConfigured:
    def generate_structured(self, *, system: str, prompt: str, response_model: type[T]) -> T:
        raise RuntimeError(
            "No StructuredLLM implementation is configured. Inject your Gemini adapter "
            "that implements generate_structured(...)."
        )
