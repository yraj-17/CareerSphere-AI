from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.core.security import hash_password
from app.db.models import User
from app.db.session import SessionLocal
from app.services.languagetool_service import apply_top_replacements, normalize_matches
from app.services.conversation_service import title_from_message

client = TestClient(app)


def _create_user(prefix: str) -> tuple[str, str]:
    db = SessionLocal()
    try:
        user = User(
            first_name="Test",
            last_name="User",
            username=f"{prefix}_{uuid4().hex[:8]}",
            email=f"{prefix}_{uuid4().hex[:8]}@example.com",
            password_hash=hash_password("Password123"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, user.username
    finally:
        db.close()


def _login(username: str) -> dict:
    res = client.post("/api/auth/login", json={"identifier": username, "password": "Password123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_title_from_message_truncates_cleanly():
    title = title_from_message("How should I prepare for a backend developer interview?")
    assert "backend" in title.lower()
    long_title = title_from_message("word " * 40)
    assert len(long_title) <= 80
    assert long_title.endswith("…")


def test_languagetool_apply_replacements():
    text = "I am preparing for interview and I want improve my resume."
    matches = [
        {"offset": 18, "length": 13, "replacements": ["for an interview"]},
        {"offset": 40, "length": 13, "replacements": ["want to improve"]},
    ]
    corrected = apply_top_replacements(text, matches)
    assert "for an interview" in corrected
    assert "want to improve" in corrected

    normalized = normalize_matches(
        text,
        [
            {
                "offset": 18,
                "length": 13,
                "message": "Missing article",
                "replacements": [{"value": "for an interview"}],
                "rule": {"id": "EN_A_VS_AN", "category": {"name": "Grammar"}},
            }
        ],
    )
    assert normalized[0]["original"] == "for interview"
    assert normalized[0]["replacements"] == ["for an interview"]


@patch("app.services.conversation_service.generate_chat", new_callable=AsyncMock)
def test_conversation_is_user_scoped(mock_chat):
    mock_chat.return_value = "Focus on Python, APIs, and databases."
    _, username_a = _create_user("test_ai_a")
    _, username_b = _create_user("test_ai_b")
    headers_a = _login(username_a)
    headers_b = _login(username_b)

    create_res = client.post(
        "/api/ai/conversations",
        headers=headers_a,
        json={"content": "What skills should I learn for backend development?"},
    )
    assert create_res.status_code == 200, create_res.text
    payload = create_res.json()
    conversation_id = payload["conversation"]["id"]
    assert payload["assistant_message"]["content"].startswith("Focus on Python")
    assert mock_chat.call_args.args[0][0]["role"] == "system"
    assert mock_chat.call_args.args[0][-1]["role"] == "user"

    list_a = client.get("/api/ai/conversations", headers=headers_a)
    list_b = client.get("/api/ai/conversations", headers=headers_b)
    assert list_a.status_code == 200
    assert any(item["id"] == conversation_id for item in list_a.json())
    assert list_b.json() == []

    forbidden = client.get(f"/api/ai/conversations/{conversation_id}", headers=headers_b)
    assert forbidden.status_code == 404

    follow_up = client.post(
        f"/api/ai/conversations/{conversation_id}/messages",
        headers=headers_a,
        json={"content": "Which one should I learn first?"},
    )
    assert follow_up.status_code == 200, follow_up.text
    sent_roles = [item["role"] for item in mock_chat.call_args.args[0] if item["role"] != "system"]
    assert sent_roles == ["user", "assistant", "user"]

    delete_forbidden = client.delete(f"/api/ai/conversations/{conversation_id}", headers=headers_b)
    assert delete_forbidden.status_code == 404

    delete_ok = client.delete(f"/api/ai/conversations/{conversation_id}", headers=headers_a)
    assert delete_ok.status_code == 204


def test_ai_endpoints_require_auth():
    assert client.get("/api/ai/conversations").status_code == 401
    assert client.post("/api/ai/conversations", json={"content": "hello"}).status_code == 401
    assert client.post("/api/ai/grammar-check", json={"text": "hello"}).status_code == 401
