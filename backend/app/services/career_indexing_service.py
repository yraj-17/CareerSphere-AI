"""
Career knowledge indexing service for CareerSphere AI.

Responsibilities
----------------
* Validate the structured career dataset (roles + skills).
* Build searchable document text and Qdrant payload for each role/skill.
* Generate embeddings via the existing embedding service.
* Ensure the career_content Qdrant collection exists.
* Upsert vectors via the existing Qdrant service.
* Remain safe to run repeatedly (fully idempotent via deterministic UUIDs).

Architecture
------------
    career_knowledge.py  (structured data)
          ↓  validate + build documents
    career_indexing_service.py  (this file)
          ↓  embed_text / embed_texts
    embedding_service.py  →  nomic-embed-text (Ollama)
          ↓  upsert_vectors
    qdrant_service.py  →  Qdrant  career_content  collection

Idempotency
-----------
Every Qdrant point ID is derived from a deterministic UUID5 keyed on
``"{source_type}:{source_id}"`` within a fixed private namespace.  Running
``initialize_career_knowledge()`` multiple times simply overwrites the same
point IDs — no duplicates accumulate.  Pre-existing unrelated points in the
collection (e.g. from future profile similarity features) are never touched.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from app.core.config import settings
from app.data.career_knowledge import DOMAINS, ROLES, SKILLS, RoleEntry, SkillEntry
from app.services.embedding_service import embed_texts, get_embedding_dimension
from app.services.qdrant_service import (
    ensure_collection,
    payload_for_text,
    upsert_vectors,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deterministic UUID namespace
# Stable across runs — do NOT change after first indexing.
# ---------------------------------------------------------------------------
_UUID_NAMESPACE = uuid.UUID("c0ffee00-cafe-babe-dead-beefdeadbeef")


def _point_id(source_type: str, source_id: str) -> str:
    """Return a deterministic UUID5 string for a given source_type + source_id."""
    return str(uuid.uuid5(_UUID_NAMESPACE, f"{source_type}:{source_id}"))


# ---------------------------------------------------------------------------
# Document builders
# ---------------------------------------------------------------------------


def build_role_document(role: RoleEntry) -> Tuple[str, Dict[str, Any]]:
    """
    Build the embedding text and Qdrant payload for a career role.

    The embedding text combines the role name, domain, description, and
    skill names so that semantic search over the role captures all of its
    key concepts.

    Returns
    -------
    (text, payload)
        ``text``    — the string that will be embedded.
        ``payload`` — the Qdrant payload dict (via ``payload_for_text``).
    """
    required_names = [SKILLS[s].name for s in role.required_skills if s in SKILLS]
    recommended_names = [SKILLS[s].name for s in role.recommended_skills if s in SKILLS]

    skill_block = ""
    if required_names:
        skill_block += f" Required skills include {', '.join(required_names)}."
    if recommended_names:
        skill_block += f" Recommended skills include {', '.join(recommended_names)}."

    text = (
        f"{role.name} ({role.domain}): {role.description}{skill_block}"
    ).strip()

    payload = payload_for_text(
        source_type="role",
        source_id=role.id,
        text=text,
        metadata={
            "name": role.name,
            "domain": role.domain,
            "required_skills": required_names,
            "recommended_skills": recommended_names,
        },
    )
    return text, payload


def build_skill_document(skill: SkillEntry) -> Tuple[str, Dict[str, Any]]:
    """
    Build the embedding text and Qdrant payload for a skill.

    Returns
    -------
    (text, payload)
        ``text``    — the string that will be embedded.
        ``payload`` — the Qdrant payload dict (via ``payload_for_text``).
    """
    alias_block = ""
    if skill.aliases:
        alias_block = f" Also known as {', '.join(skill.aliases)}."

    text = f"{skill.name}: {skill.description}{alias_block}".strip()

    payload = payload_for_text(
        source_type="skill",
        source_id=skill.id,
        text=text,
        metadata={
            "name": skill.name,
            "category": skill.category,
            "aliases": skill.aliases,
        },
    )
    return text, payload


# ---------------------------------------------------------------------------
# Dataset validation
# ---------------------------------------------------------------------------


class ValidationError(Exception):
    """Raised when the career knowledge dataset fails validation."""


def validate_career_dataset() -> None:
    """
    Validate the career knowledge dataset for internal consistency.

    Checks
    ------
    * Domains list is non-empty and contains no duplicates.
    * All role domains are in the DOMAINS list.
    * All role IDs are unique.
    * All skill IDs are unique.
    * No role has an empty description.
    * No skill has an empty description.
    * Required and recommended skill references point to known skill IDs.
    * A role's required and recommended skill lists do not overlap.
    * No role has duplicate entries in its required or recommended skill lists.
    * ROLES covers all domains defined in DOMAINS (warning only).

    Raises
    ------
    ValidationError
        On any structural problem with the dataset.
    """
    errors: List[str] = []

    # ── Domains ───────────────────────────────────────────────────────────
    if not DOMAINS:
        errors.append("DOMAINS list is empty.")
    domain_set = set(DOMAINS)
    if len(domain_set) != len(DOMAINS):
        dups = [d for d in DOMAINS if DOMAINS.count(d) > 1]
        errors.append(f"Duplicate domain names: {sorted(set(dups))}")

    # ── Skill IDs ─────────────────────────────────────────────────────────
    skill_ids = list(SKILLS.keys())
    skill_id_set = set(skill_ids)
    if len(skill_id_set) != len(skill_ids):
        dups = [s for s in skill_ids if skill_ids.count(s) > 1]
        errors.append(f"Duplicate skill IDs in SKILLS dict: {sorted(set(dups))}")

    for sid, skill in SKILLS.items():
        if sid != skill.id:
            errors.append(
                f"Skill dict key '{sid}' does not match skill.id '{skill.id}'."
            )
        if not skill.description.strip():
            errors.append(f"Skill '{sid}' has an empty description.")
        if not skill.name.strip():
            errors.append(f"Skill '{sid}' has an empty name.")

    # ── Role IDs ──────────────────────────────────────────────────────────
    role_ids = [r.id for r in ROLES]
    if len(set(role_ids)) != len(role_ids):
        dups = [r for r in role_ids if role_ids.count(r) > 1]
        errors.append(f"Duplicate role IDs in ROLES list: {sorted(set(dups))}")

    domains_with_roles: set[str] = set()
    for role in ROLES:
        if not role.description.strip():
            errors.append(f"Role '{role.id}' has an empty description.")
        if not role.name.strip():
            errors.append(f"Role '{role.id}' has an empty name.")

        # Domain validity
        if role.domain not in domain_set:
            errors.append(
                f"Role '{role.id}' references unknown domain '{role.domain}'."
            )
        domains_with_roles.add(role.domain)

        # Skill reference validity
        req_set = set(role.required_skills)
        rec_set = set(role.recommended_skills)

        for sid in role.required_skills:
            if sid not in skill_id_set:
                errors.append(
                    f"Role '{role.id}' required_skill '{sid}' not in SKILLS catalog."
                )
        for sid in role.recommended_skills:
            if sid not in skill_id_set:
                errors.append(
                    f"Role '{role.id}' recommended_skill '{sid}' not in SKILLS catalog."
                )

        # Duplicate skill entries within a role
        if len(req_set) != len(role.required_skills):
            errors.append(f"Role '{role.id}' has duplicate entries in required_skills.")
        if len(rec_set) != len(role.recommended_skills):
            errors.append(
                f"Role '{role.id}' has duplicate entries in recommended_skills."
            )

        # Overlap between required and recommended
        overlap = req_set & rec_set
        if overlap:
            errors.append(
                f"Role '{role.id}' lists skill(s) {sorted(overlap)} in both "
                "required_skills and recommended_skills."
            )

    # ── Domain coverage (informational) ───────────────────────────────────
    uncovered = domain_set - domains_with_roles
    if uncovered:
        logger.warning(
            "[CareerKnowledge] The following domains have no roles: %s",
            sorted(uncovered),
        )

    if errors:
        msg = "Career knowledge dataset validation failed:\n" + "\n".join(
            f"  • {e}" for e in errors
        )
        raise ValidationError(msg)

    logger.info(
        "[CareerKnowledge] Dataset validated: %d domains, %d roles, %d skills.",
        len(domain_set),
        len(ROLES),
        len(SKILLS),
    )


# ---------------------------------------------------------------------------
# Indexing result
# ---------------------------------------------------------------------------


class IndexingResult(NamedTuple):
    collection: str
    roles_indexed: int
    skills_indexed: int
    total_vectors: int
    embedding_model: str
    embedding_dimension: int


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def initialize_career_knowledge(
    collection_name: Optional[str] = None,
    batch_size: int = 20,
) -> IndexingResult:
    """
    Validate the dataset, embed all role and skill documents, and upsert them
    into the Qdrant career_content collection.

    This function is **idempotent** — calling it multiple times produces the
    same Qdrant state.  Each point is identified by a deterministic UUID5;
    re-running overwrites existing points with identical content.

    It does **not** delete any pre-existing points in the collection.  Points
    belonging to other source_types (e.g. future user-profile embeddings)
    remain untouched.

    Parameters
    ----------
    collection_name:
        Override the target collection.  Defaults to
        ``settings.QDRANT_COLLECTION_CONTENT``.
    batch_size:
        Number of documents to embed in a single Ollama call.

    Returns
    -------
    IndexingResult
        Summary of what was indexed.

    Raises
    ------
    ValidationError
        If the dataset is structurally invalid.
    EmbeddingServiceError
        If the embedding model is unavailable.
    Exception
        If Qdrant is unreachable.
    """
    collection = collection_name or settings.QDRANT_COLLECTION_CONTENT

    # 1. Validate dataset
    validate_career_dataset()

    # 2. Determine embedding dimension (uses cached value or probes the model)
    dim = get_embedding_dimension()
    model = settings.EMBEDDING_MODEL

    # 3. Ensure collection exists (does nothing if already present)
    ensure_collection(collection, vector_size=dim)
    logger.info("[CareerKnowledge] Using collection '%s' (dim=%d).", collection, dim)

    # 4. Build all documents
    role_docs: List[Tuple[str, Dict[str, Any]]] = [
        build_role_document(r) for r in ROLES
    ]
    skill_docs: List[Tuple[str, Dict[str, Any]]] = [
        build_skill_document(s) for s in SKILLS.values()
    ]

    all_docs = (
        [("role", r.id, text, payload) for r, (text, payload) in zip(ROLES, role_docs)]
        + [
            ("skill", s.id, text, payload)
            for s, (text, payload) in zip(SKILLS.values(), skill_docs)
        ]
    )

    total = len(all_docs)
    logger.info(
        "[CareerKnowledge] Preparing to index %d documents (%d roles, %d skills).",
        total,
        len(ROLES),
        len(SKILLS),
    )

    # 5. Embed and upsert in batches
    indexed = 0
    for batch_start in range(0, total, batch_size):
        batch = all_docs[batch_start : batch_start + batch_size]
        texts = [text for _, _, text, _ in batch]

        vectors = embed_texts(texts)

        points = [
            {
                "id": _point_id(source_type, source_id),
                "vector": vector,
                "payload": payload,
            }
            for (source_type, source_id, _, payload), vector in zip(batch, vectors)
        ]

        upsert_vectors(
            collection_name=collection,
            points=points,
            vector_size=dim,
        )

        indexed += len(batch)
        logger.info(
            "[CareerKnowledge] Indexed %d / %d documents.", indexed, total
        )

    result = IndexingResult(
        collection=collection,
        roles_indexed=len(ROLES),
        skills_indexed=len(SKILLS),
        total_vectors=indexed,
        embedding_model=model,
        embedding_dimension=dim,
    )
    logger.info(
        "[CareerKnowledge] Indexing complete. %d vectors in '%s'.",
        indexed,
        collection,
    )
    return result
