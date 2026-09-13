"""
Career knowledge base initialisation script.

Usage
-----
From the ``backend/`` directory:

    python -m scripts.index_career_knowledge

Or from the project root:

    python -m backend.scripts.index_career_knowledge

What this script does
---------------------
1. Validates the structured career knowledge dataset (14 domains, 30 roles,
   80+ skills).
2. Generates embeddings for every role and skill document using the
   configured embedding model (nomic-embed-text via Ollama).
3. Upserts all vectors into the Qdrant ``career_content`` collection using
   deterministic UUID5 point IDs — safe to run multiple times.

Environment
-----------
Reads configuration from the project ``.env`` file via ``app.core.config``.
Requires Qdrant and Ollama (with the nomic-embed-text model) to be running.

Exit codes
----------
0  — success
1  — validation failure (dataset structural error)
2  — service unavailable (Qdrant or embedding model not reachable)
"""

from __future__ import annotations

import logging
import sys
import time

# ---------------------------------------------------------------------------
# Bootstrap: ensure the backend app package is importable when this script is
# run from within the backend/ directory (python -m scripts.index_career_knowledge).
# When run from the project root the path is already correct.
# ---------------------------------------------------------------------------
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_HERE)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

# ---------------------------------------------------------------------------
# Imports (after path fixup)
# ---------------------------------------------------------------------------
from app.services.career_indexing_service import (  # noqa: E402
    IndexingResult,
    ValidationError,
    initialize_career_knowledge,
)
from app.services.embedding_service import EmbeddingServiceError  # noqa: E402
from app.services.qdrant_service import ping_qdrant  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.data.career_knowledge import DOMAINS, ROLES, SKILLS  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_SEPARATOR = "-" * 60


def _banner() -> None:
    print()
    print(_SEPARATOR)
    print("  CareerSphere AI — Career Knowledge Indexer")
    print(_SEPARATOR)
    print(f"  Qdrant URL      : {settings.QDRANT_URL}")
    print(f"  Collection      : {settings.QDRANT_COLLECTION_CONTENT}")
    print(f"  Embedding model : {settings.EMBEDDING_MODEL}")
    print(f"  Embedding dim   : {settings.EMBEDDING_DIMENSION or '(auto-detect)'}")
    print(f"  Domains         : {len(DOMAINS)}")
    print(f"  Roles           : {len(ROLES)}")
    print(f"  Skills          : {len(SKILLS)}")
    print(_SEPARATOR)
    print()


def _print_result(result: IndexingResult, elapsed: float) -> None:
    print()
    print(_SEPARATOR)
    print("  INDEXING COMPLETE")
    print(_SEPARATOR)
    print(f"  Collection      : {result.collection}")
    print(f"  Embedding model : {result.embedding_model}")
    print(f"  Embedding dim   : {result.embedding_dimension}")
    print(f"  Roles indexed   : {result.roles_indexed}")
    print(f"  Skills indexed  : {result.skills_indexed}")
    print(f"  Total vectors   : {result.total_vectors}")
    print(f"  Elapsed         : {elapsed:.1f}s")
    print(_SEPARATOR)
    print()


def main() -> int:
    _banner()

    # 1. Qdrant health check
    logger.info("Checking Qdrant connectivity at %s ...", settings.QDRANT_URL)
    if not ping_qdrant():
        logger.error(
            "Qdrant is not reachable at %s. "
            "Start the container with:  docker compose up -d qdrant",
            settings.QDRANT_URL,
        )
        return 2

    logger.info("Qdrant is reachable. Starting indexing ...")
    start = time.monotonic()

    try:
        result = initialize_career_knowledge()
    except ValidationError as exc:
        logger.error("Dataset validation failed:\n%s", exc)
        return 1
    except EmbeddingServiceError as exc:
        logger.error(
            "Embedding service error: %s\n"
            "Ensure Ollama is running and the model '%s' is available:\n"
            "  ollama pull %s",
            exc,
            settings.EMBEDDING_MODEL,
            settings.EMBEDDING_MODEL,
        )
        return 2
    except Exception as exc:
        logger.error("Unexpected error during indexing: %s", exc, exc_info=True)
        return 2

    elapsed = time.monotonic() - start
    _print_result(result, elapsed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
