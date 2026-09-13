import os
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from qdrant_client.http import models as qmodels

from app.core.config import Settings
from app.services import embedding_service, qdrant_service


class FakeEmbedClient:
    def __init__(self, vectors):
        self.vectors = vectors
        self.calls = []

    def embed(self, model, input):
        self.calls.append({"model": model, "input": input})
        return {"embeddings": self.vectors[: len(input)]}


def test_embed_text_generates_vector(monkeypatch):
    client = FakeEmbedClient([[0.1, 0.2, 0.3]])
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: client)

    vector = embedding_service.embed_text("Python backend development")

    assert vector == [0.1, 0.2, 0.3]
    assert client.calls[0]["model"] == embedding_service.settings.EMBEDDING_MODEL


def test_embed_text_rejects_empty_text():
    with pytest.raises(ValueError, match="cannot be empty"):
        embedding_service.embed_text("   ")


def test_embed_texts_requires_consistent_dimensions(monkeypatch):
    client = FakeEmbedClient([[0.1, 0.2], [0.1]])
    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: client)

    with pytest.raises(embedding_service.EmbeddingServiceError, match="inconsistent"):
        embedding_service.embed_texts(["backend", "frontend"])


def test_embedding_dimension_uses_actual_model_dimension(monkeypatch):
    embedding_service.get_embedding_dimension.cache_clear()
    monkeypatch.setattr(embedding_service, "embed_text", lambda text: [0.1, 0.2, 0.3, 0.4])
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_DIMENSION", None)

    assert embedding_service.get_embedding_dimension() == 4
    embedding_service.get_embedding_dimension.cache_clear()


def test_embedding_service_wraps_provider_failures(monkeypatch):
    class FailingClient:
        def embed(self, model, input):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(embedding_service, "get_embedding_client", lambda: FailingClient())

    with pytest.raises(embedding_service.EmbeddingServiceError, match="currently unavailable"):
        embedding_service.embed_text("backend")


def test_qdrant_client_initialization(monkeypatch):
    qdrant_service._client = None
    created = {}

    class FakeQdrantClient:
        def __init__(self, **kwargs):
            created.update(kwargs)

    monkeypatch.setattr(qdrant_service, "QdrantClient", FakeQdrantClient)
    monkeypatch.setattr(qdrant_service.settings, "QDRANT_URL", "http://localhost:6333")
    monkeypatch.setattr(qdrant_service.settings, "QDRANT_API_KEY", "test-key")

    qdrant_service.get_qdrant_client()

    assert created["url"] == "http://localhost:6333"
    assert created["api_key"] == "test-key"
    assert created["prefer_grpc"] is False
    qdrant_service._client = None


def test_qdrant_connection_failure_handling(monkeypatch):
    class FailingClient:
        def get_collections(self):
            raise RuntimeError("down")

    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: FailingClient())

    assert qdrant_service.ping_qdrant() is False


def test_collection_creation_and_existence(monkeypatch):
    client = MagicMock()
    client.collection_exists.side_effect = [False, True]
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: client)

    qdrant_service.ensure_collection("test_collection", vector_size=3)
    exists = qdrant_service.collection_exists("test_collection")

    client.create_collection.assert_called_once()
    assert client.create_collection.call_args.kwargs["collection_name"] == "test_collection"
    assert exists is True


def test_upsert_vectors_preserves_payload(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: client)

    payload = qdrant_service.payload_for_text(
        source_type="skill",
        source_id="skill-1",
        text="Python backend development",
        metadata={"user_id": "user-1"},
    )
    qdrant_service.upsert_embedding(
        collection_name="profiles",
        point_id="point-1",
        vector=[0.1, 0.2, 0.3],
        payload=payload,
        vector_size=3,
    )

    point = client.upsert.call_args.kwargs["points"][0]
    assert point.id == "point-1"
    assert point.vector == [0.1, 0.2, 0.3]
    assert point.payload["source_type"] == "skill"
    assert point.payload["metadata"]["user_id"] == "user-1"


def test_semantic_search_uses_embedding_and_returns_payload(monkeypatch):
    scored = qmodels.ScoredPoint(
        id="point-1",
        version=1,
        score=0.91,
        payload={"text": "Python backend development using FastAPI"},
    )
    client = MagicMock()
    client.query_points.return_value = SimpleNamespace(points=[scored])
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: client)
    monkeypatch.setattr(qdrant_service, "embed_text", lambda text: [0.1, 0.2, 0.3])

    results = qdrant_service.semantic_search("content", "backend development using Python", limit=1)

    assert results[0].payload["text"] == "Python backend development using FastAPI"
    assert client.query_points.call_args.kwargs["query"] == [0.1, 0.2, 0.3]


def test_delete_and_retrieve_vectors(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(qdrant_service, "get_qdrant_client", lambda: client)

    qdrant_service.delete_vectors("content", ["point-1"])
    qdrant_service.retrieve_points("content", ["point-1"])

    selector = client.delete.call_args.kwargs["points_selector"]
    assert selector.points == ["point-1"]
    client.retrieve.assert_called_once_with(
        collection_name="content",
        ids=["point-1"],
        with_payload=True,
        with_vectors=False,
    )


def test_embedding_dimension_config_accepts_blank():
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/careersphere_db",
        SECRET_KEY="test-secret",
        EMBEDDING_DIMENSION="",
    )

    assert settings.EMBEDDING_DIMENSION is None


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("RUN_QDRANT_INTEGRATION") != "1",
    reason="Set RUN_QDRANT_INTEGRATION=1 and ensure Qdrant + Ollama embedding model are running.",
)
def test_real_text_embedding_to_qdrant_semantic_search():
    embedding_service.get_embedding_dimension.cache_clear()
    collection = f"semantic_proof_{uuid.uuid4().hex}"
    texts = [
        "Python backend development using FastAPI",
        "REST API development and backend engineering",
        "Machine learning and neural networks",
        "AWS cloud infrastructure and deployment",
        "Kubernetes container orchestration",
    ]
    client = qdrant_service.get_qdrant_client()
    vectors = embedding_service.embed_texts(texts)
    vector_size = len(vectors[0])
    qdrant_service.ensure_collection(collection, vector_size=vector_size)
    try:
        point_ids = [str(uuid.uuid4()) for _ in texts]
        qdrant_service.upsert_vectors(
            collection_name=collection,
            points=[
                {
                    "id": point_id,
                    "vector": vector,
                    "payload": qdrant_service.payload_for_text(
                        source_type="test_content",
                        source_id=str(index),
                        text=text,
                        metadata={"dataset": "semantic_proof"},
                    ),
                }
                for index, (point_id, text, vector) in enumerate(zip(point_ids, texts, vectors), start=1)
            ],
            vector_size=vector_size,
        )
        query_vector = embedding_service.embed_text("backend development using Python")
        results = qdrant_service.similarity_search(
            collection_name=collection,
            query_vector=query_vector,
            limit=2,
            vector_size=vector_size,
        )
        result_texts = [point.payload["text"] for point in results]
        assert any("Python backend" in text or "backend engineering" in text for text in result_texts)
        assert all(point.payload["metadata"]["dataset"] == "semantic_proof" for point in results)
    finally:
        client.delete_collection(collection_name=collection)
