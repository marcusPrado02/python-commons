"""OpenSearch adapter (A-10) — drop-in for ElasticsearchClient."""

from mp_commons.adapters.opensearch.client import (
    OpenSearchClient,
    OpenSearchRepository,
    OpenSearchSearchQuery,
)

__all__ = ["OpenSearchClient", "OpenSearchRepository", "OpenSearchSearchQuery"]
