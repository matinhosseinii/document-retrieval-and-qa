from rest_framework.exceptions import APIException


class EmbeddingConfigurationAPIError(APIException):
    status_code = 503
    default_detail = "Document embeddings are not configured."
    default_code = "embedding_not_configured"


class EmbeddingUpstreamAPIError(APIException):
    status_code = 502
    default_detail = "The embedding provider is temporarily unavailable."
    default_code = "embedding_provider_unavailable"
