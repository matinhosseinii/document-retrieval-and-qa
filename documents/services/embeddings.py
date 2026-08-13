import math
from numbers import Real
from time import sleep

from langchain_core.embeddings import Embeddings
from openrouter import OpenRouter


class EmbeddingConfigurationError(Exception):
    """Embedding configuration is missing or invalid."""


class EmbeddingUpstreamError(Exception):
    """The embedding provider failed or returned an invalid response."""


class OpenRouterEmbeddings(Embeddings):
    """LangChain embedding boundary backed by OpenRouter's embeddings API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_ms: int,
        retries: int,
        client=None,
    ):
        if not api_key.strip():
            raise EmbeddingConfigurationError(
                "OPENROUTER_API_KEY is not configured for embeddings."
            )
        if not model.strip():
            raise EmbeddingConfigurationError(
                "OPENROUTER_EMBEDDING_MODEL is not configured."
            )
        if timeout_ms <= 0:
            raise EmbeddingConfigurationError(
                "OPENROUTER_EMBEDDING_TIMEOUT_MS must be positive."
            )
        if retries < 0:
            raise EmbeddingConfigurationError(
                "OPENROUTER_EMBEDDING_RETRIES must not be negative."
            )

        self.model = model
        self.timeout_ms = timeout_ms
        self.retries = retries
        self.client = client or OpenRouter(api_key=api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed([f"passage: {text}" for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([f"query: {text}"])[0]

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        response = None
        for attempt in range(self.retries + 1):
            try:
                response = self.client.embeddings.generate(
                    model=self.model,
                    input=inputs,
                    encoding_format="float",
                    retries=None,
                    timeout_ms=self.timeout_ms,
                )
                break
            except Exception as exc:
                if attempt == self.retries:
                    raise EmbeddingUpstreamError(
                        "The embedding provider is temporarily unavailable."
                    ) from exc
                sleep(min(0.25 * (2**attempt), 1.0))

        try:
            data = list(response.data)
            ordered = self._ordered_response_data(data, len(inputs))
            vectors = [self._normalize(item.embedding) for item in ordered]
            dimensions = {len(vector) for vector in vectors}
            if len(vectors) != len(inputs) or len(dimensions) != 1:
                raise ValueError("Embedding response shape does not match the request.")
            return vectors
        except EmbeddingUpstreamError:
            raise
        except Exception as exc:
            raise EmbeddingUpstreamError(
                "The embedding provider returned an invalid response."
            ) from exc

    @staticmethod
    def _ordered_response_data(data: list, expected_count: int) -> list:
        if len(data) != expected_count:
            raise ValueError("Unexpected embedding count.")

        indices = [getattr(item, "index", None) for item in data]
        if all(index is None for index in indices):
            return data
        if any(index is None for index in indices):
            raise ValueError("Embedding indices are incomplete.")
        if sorted(indices) != list(range(expected_count)):
            raise ValueError("Embedding indices are invalid.")
        return sorted(data, key=lambda item: item.index)

    @staticmethod
    def _normalize(vector) -> list[float]:
        if not isinstance(vector, (list, tuple)) or not vector:
            raise ValueError("Embedding vector is empty or invalid.")
        if any(
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(float(value))
            for value in vector
        ):
            raise ValueError("Embedding vector contains non-numeric values.")

        values = [float(value) for value in vector]
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            raise ValueError("Embedding provider returned a zero vector.")
        return [value / norm for value in values]
