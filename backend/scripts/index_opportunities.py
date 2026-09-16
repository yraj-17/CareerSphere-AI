"""
Index curated PostgreSQL opportunities into Qdrant.

Usage
-----
From the project root:

    python -m backend.scripts.index_opportunities

From the backend/ directory:

    python -m scripts.index_opportunities
"""

from __future__ import annotations

import logging
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.embedding_service import EmbeddingServiceError  # noqa: E402
from app.services.opportunity_embedding_service import (  # noqa: E402
    EXPECTED_EMBEDDING_DIMENSION,
    OpportunityEmbeddingError,
    index_curated_opportunities,
    search_opportunities,
)
from app.services.qdrant_service import get_qdrant_client, ping_qdrant  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_SEPARATOR = "-" * 60


def _collection_count(collection_name: str) -> int | None:
    client = get_qdrant_client()
    try:
        result = client.count(collection_name=collection_name, exact=True)
        return int(result.count)
    except Exception:
        try:
            info = client.get_collection(collection_name=collection_name)
            return int(info.points_count)
        except Exception:
            return None


def _print_search_preview() -> None:
    queries = [
        "Python FastAPI backend developer",
        "AWS Kubernetes infrastructure DevOps",
        "machine learning model development",
    ]
    print()
    print("Semantic search preview:")
    for query in queries:
        results = search_opportunities(query, limit=3)
        roles = [
            f"{point.payload.get('title')} ({point.payload.get('target_role')})"
            for point in results
        ]
        print(f"  {query}: {roles}")


def main() -> int:
    print("Indexing opportunities...")
    print(_SEPARATOR)
    print(f"Qdrant URL       : {settings.QDRANT_URL}")
    print(f"Collection       : {settings.QDRANT_COLLECTION_OPPORTUNITIES}")
    print(f"Embedding model  : {settings.EMBEDDING_MODEL}")
    print(f"Expected dim     : {EXPECTED_EMBEDDING_DIMENSION}")
    print(_SEPARATOR)

    if not ping_qdrant():
        print(
            f"Qdrant is not reachable at {settings.QDRANT_URL}. "
            "Start it with: docker compose up -d qdrant",
            file=sys.stderr,
        )
        return 2

    db = SessionLocal()
    start = time.monotonic()
    try:
        result = index_curated_opportunities(db)
        elapsed = time.monotonic() - start
        vector_count = _collection_count(result.collection)

        print()
        print("Indexing complete.")
        print(_SEPARATOR)
        print(f"Opportunities found: {result.opportunities_found}")
        print(f"Embeddings generated: {result.embeddings_generated}")
        print(f"Vectors upserted: {result.vectors_upserted}")
        print(f"Collection: {result.collection}")
        print(f"Vector dimension: {result.embedding_dimension}")
        print(f"Embedding model: {result.embedding_model}")
        if vector_count is not None:
            print(f"Qdrant vector count: {vector_count}")
        print(f"Elapsed: {elapsed:.1f}s")
        print(_SEPARATOR)

        _print_search_preview()
        return 0
    except OpportunityEmbeddingError as exc:
        logger.error("Opportunity indexing validation failed: %s", exc)
        return 1
    except EmbeddingServiceError as exc:
        logger.error(
            "Embedding service error: %s Ensure Ollama is running and model '%s' is available.",
            exc,
            settings.EMBEDDING_MODEL,
        )
        return 2
    except Exception as exc:
        logger.error("Unexpected opportunity indexing error: %s", exc, exc_info=True)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
