"""
AI conversation tests.

Covers:
  - Existing unit tests (title generation, grammar helpers, timeout message)
  - TEST 1  Normal chat (use_profile=false) — no profile in prompt
  - TEST 2  Profile-aware chat (use_profile=true) — profile included
  - TEST 3  Default behaviour (use_profile omitted) — defaults to false
  - TEST 4  User isolation — User B never sees User A's profile
  - TEST 5  Conversation isolation — messages stay inside their conversation
  - TEST 6  Profile OFF performance path — no PostgreSQL profile query
"""

from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import TimeoutException
import pytest

from app.main import app
from app.core.security import hash_password
from app.db.models import (
    CareerPreference,
    Profile,
    ProfileEducation,
    ProfileExperience,
    ProfileProject,
    ProfileSkill,
    User,
)
from app.db.session import SessionLocal
from app.services.languagetool_service import apply_top_replacements, normalize_matches
from app.services.conversation_service import title_from_message
from app.services.ollama_service import AIServiceError, generate_chat

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _add_profile(user_id: str, skill_names: list[str]) -> None:
    db = SessionLocal()
    try:
        profile = Profile(
            user_id=user_id,
            headline="Backend Developer",
            location="Mumbai, India",
            about="Interested in backend engineering and cloud.",
        )
        db.add(profile)
        db.flush()
        for name in skill_names:
            db.add(ProfileSkill(profile_id=profile.id, name=name, normalized_name=name.lower()))
        db.add(ProfileEducation(
            profile_id=profile.id,
            institution="XYZ University",
            degree="B.Tech",
            field_of_study="Computer Science",
        ))
        db.add(ProfileExperience(
            profile_id=profile.id,
            company="Acme",
            job_title="Software Engineering Intern",
            employment_type="Internship",
            currently_working=True,
        ))
        project = ProfileProject(profile_id=profile.id, name="CareerSphere AI")
        db.add(project)
        db.add(CareerPreference(profile_id=profile.id, target_job_role="Backend Developer"))
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Existing unit tests (unchanged behaviour)
# ---------------------------------------------------------------------------

def test_title_from_message_truncates_cleanly():
    title = title_from_message("How should I prepare for a backend developer interview?")
    assert "backend" in title.lower()
    long_title = title_from_message("word " * 40)
    assert len(long_title) <= 80
    assert long_title.endswith("…")


def test_languagetool_apply_replacements():
    text = "I am preparing for interview and I want improve my resume."
    matches = [
        {"offset": 15, "length": 13, "replacements": ["for an interview"]},
        {"offset": 35, "length": 12, "replacements": ["want to improve"]},
    ]
    corrected = apply_top_replacements(text, matches)
    assert "for an interview" in corrected
    assert "want to improve" in corrected

    normalized = normalize_matches(
        text,
        [
            {
                "offset": 15,
                "length": 13,
                "message": "Missing article",
                "replacements": [{"value": "for an interview"}],
                "rule": {"id": "EN_A_VS_AN", "category": {"name": "Grammar"}},
            }
        ],
    )
    assert normalized[0]["original"] == "for interview"
    assert normalized[0]["replacements"] == ["for an interview"]


@patch("app.services.ollama_service.client.chat", new_callable=AsyncMock)
def test_ollama_timeout_has_clear_message(mock_chat):
    mock_chat.side_effect = TimeoutException("slow generation")

    with pytest.raises(AIServiceError) as exc_info:
        import asyncio
        asyncio.run(generate_chat([{"role": "user", "content": "hello"}]))

    assert str(exc_info.value) == "The AI is taking longer than expected. Please try again."


def test_ai_endpoints_require_auth():
    assert client.get("/api/ai/conversations").status_code == 401
    assert client.post("/api/ai/conversations", json={"content": "hello"}).status_code == 401
    assert client.post("/api/ai/grammar-check", json={"text": "hello"}).status_code == 401


# ---------------------------------------------------------------------------
# TEST 1 — Normal chat: use_profile=false → NO profile in LLM prompt
# ---------------------------------------------------------------------------

@patch("app.services.conversation_service.generate_chat", new_callable=AsyncMock)
def test_normal_chat_no_profile_context(mock_chat):
    """When use_profile=false, profile_context_service must not be called and
    the system message must contain NO user profile data."""
    mock_chat.return_value = "Docker containers package applications and their dependencies."
    user_id, username = _create_user("t1_no_profile")
    _add_profile(user_id, ["Python", "Docker"])
    headers = _login(username)

    with patch("app.services.conversation_service.profile_context_service.build_profile_context") as mock_build:
        res = client.post(
            "/api/ai/conversations",
            headers=headers,
            json={"content": "Explain Docker containers.", "use_profile": False},
        )

    assert res.status_code == 200, res.text
    # build_profile_context must never be called when use_profile=false
    mock_build.assert_not_called()

    # The LLM must have been called without any profile section
    assert mock_chat.called
    system_content = mock_chat.call_args.args[0][0]["content"]
    assert "USER PROFILE CONTEXT" not in system_content
    assert "Python" not in system_content
    assert "Docker" not in system_content

    # used_profile_context on the assistant message must be false
    payload = res.json()
    assert payload["assistant_message"]["used_profile_context"] is False


# ---------------------------------------------------------------------------
# TEST 2 — Profile-aware chat: use_profile=true → profile included in prompt
# ---------------------------------------------------------------------------

@patch("app.services.conversation_service.generate_chat", new_callable=AsyncMock)
def test_profile_aware_chat_includes_context(mock_chat):
    """When use_profile=true the authenticated user's profile must appear in
    the system message sent to Ollama."""
    mock_chat.return_value = "Based on your Python and FastAPI background, focus on system design."
    user_id, username = _create_user("t2_with_profile")
    _add_profile(user_id, ["Python", "FastAPI"])
    headers = _login(username)

    res = client.post(
        "/api/ai/conversations",
        headers=headers,
        json={"content": "What should I learn next for my career?", "use_profile": True},
    )

    assert res.status_code == 200, res.text
    messages_sent = mock_chat.call_args.args[0]
    system_content = messages_sent[0]["content"]

    assert "USER PROFILE CONTEXT" in system_content
    assert "Python" in system_content
    assert "FastAPI" in system_content
    # Sensitive fields must never leak
    assert "password" not in system_content.lower()

    payload = res.json()
    assert payload["assistant_message"]["used_profile_context"] is True


# ---------------------------------------------------------------------------
# TEST 3 — Default behaviour: omitting use_profile → defaults to false
# ---------------------------------------------------------------------------

@patch("app.services.conversation_service.generate_chat", new_callable=AsyncMock)
def test_default_use_profile_is_false(mock_chat):
    """Omitting use_profile in the request body must default to false and
    must not load or send any profile context."""
    mock_chat.return_value = "Docker is a containerisation platform."
    user_id, username = _create_user("t3_default")
    _add_profile(user_id, ["Go", "Kubernetes"])
    headers = _login(username)

    with patch("app.services.conversation_service.profile_context_service.build_profile_context") as mock_build:
        # Deliberately omit use_profile from the payload
        res = client.post(
            "/api/ai/conversations",
            headers=headers,
            json={"content": "Explain Docker."},
        )

    assert res.status_code == 200, res.text
    mock_build.assert_not_called()

    system_content = mock_chat.call_args.args[0][0]["content"]
    assert "USER PROFILE CONTEXT" not in system_content
    assert "Kubernetes" not in system_content

    payload = res.json()
    assert payload["assistant_message"]["used_profile_context"] is False


# ---------------------------------------------------------------------------
# TEST 4 — User isolation: User B can only access User B's profile
# ---------------------------------------------------------------------------

@patch("app.services.conversation_service.generate_chat", new_callable=AsyncMock)
def test_user_profile_isolation(mock_chat):
    """User A enabling profile context must never expose User A's data to
    User B's requests or conversations."""
    mock_chat.return_value = "Here is some advice."
    user_a_id, username_a = _create_user("t4_user_a")
    user_b_id, username_b = _create_user("t4_user_b")
    _add_profile(user_a_id, ["Rust", "WebAssembly"])
    _add_profile(user_b_id, ["React", "TypeScript"])
    headers_a = _login(username_a)
    headers_b = _login(username_b)

    # User A sends with profile ON — check only User A's skills appear
    res_a = client.post(
        "/api/ai/conversations",
        headers=headers_a,
        json={"content": "What should I learn?", "use_profile": True},
    )
    assert res_a.status_code == 200, res_a.text
    system_a = mock_chat.call_args.args[0][0]["content"]
    assert "Rust" in system_a
    assert "WebAssembly" in system_a
    assert "React" not in system_a
    assert "TypeScript" not in system_a

    # User B sends with profile ON — must only see User B's profile
    res_b = client.post(
        "/api/ai/conversations",
        headers=headers_b,
        json={"content": "What should I learn?", "use_profile": True},
    )
    assert res_b.status_code == 200, res_b.text
    system_b = mock_chat.call_args.args[0][0]["content"]
    assert "React" in system_b
    assert "TypeScript" in system_b
    assert "Rust" not in system_b
    assert "WebAssembly" not in system_b

    # User B cannot access User A's conversation
    conv_a_id = res_a.json()["conversation"]["id"]
    forbidden = client.get(f"/api/ai/conversations/{conv_a_id}", headers=headers_b)
    assert forbidden.status_code == 404


# ---------------------------------------------------------------------------
# TEST 5 — Conversation isolation: messages stay inside their conversation
# ---------------------------------------------------------------------------

@patch("app.services.conversation_service.generate_chat", new_callable=AsyncMock)
def test_conversation_history_isolation(mock_chat):
    """Messages from Conversation A must never appear in the history sent for
    Conversation B, even when both belong to the same user."""
    mock_chat.return_value = "Sure, here is some advice."
    user_id, username = _create_user("t5_conv_isolation")
    headers = _login(username)

    # --- Conversation A ---
    res_a = client.post(
        "/api/ai/conversations",
        headers=headers,
        json={"content": "Help me prepare for a backend interview."},
    )
    assert res_a.status_code == 200, res_a.text
    conv_a_id = res_a.json()["conversation"]["id"]

    # Follow-up in Conversation A
    client.post(
        f"/api/ai/conversations/{conv_a_id}/messages",
        headers=headers,
        json={"content": "What about system design questions?"},
    )

    # --- Conversation B (new, separate) ---
    res_b = client.post(
        "/api/ai/conversations",
        headers=headers,
        json={"content": "Help me write a resume."},
    )
    assert res_b.status_code == 200, res_b.text
    conv_b_id = res_b.json()["conversation"]["id"]
    assert conv_b_id != conv_a_id

    # The messages sent to Ollama for Conversation B must only contain
    # Conversation B's user message, not anything from Conversation A.
    messages_for_b = mock_chat.call_args.args[0]
    non_system = [m for m in messages_for_b if m["role"] != "system"]

    # Conversation A content must not appear
    all_content = " ".join(m["content"] for m in non_system)
    assert "backend interview" not in all_content
    assert "system design" not in all_content

    # Only the single Conversation B message must be present
    assert len(non_system) == 1
    assert "resume" in non_system[0]["content"].lower()


# ---------------------------------------------------------------------------
# TEST 6 — Profile OFF performance path: no DB query, no profile text
# ---------------------------------------------------------------------------

@patch("app.services.conversation_service.generate_chat", new_callable=AsyncMock)
def test_profile_off_no_db_query_and_no_profile_text(mock_chat):
    """When use_profile=false, profile_context_service.get_profile_for_ai
    (the DB query) must not be invoked, and the Ollama payload must contain
    no profile text whatsoever."""
    mock_chat.return_value = "Python is a general-purpose programming language."
    user_id, username = _create_user("t6_perf")
    _add_profile(user_id, ["Python", "Django"])
    headers = _login(username)

    with patch(
        "app.services.conversation_service.profile_context_service.get_profile_for_ai"
    ) as mock_db_query:
        res = client.post(
            "/api/ai/conversations",
            headers=headers,
            json={"content": "What is Python?", "use_profile": False},
        )

    assert res.status_code == 200, res.text
    # The PostgreSQL profile query must not have been executed at all
    mock_db_query.assert_not_called()

    # Every message in the Ollama payload must be free of profile sections
    for msg in mock_chat.call_args.args[0]:
        assert "USER PROFILE CONTEXT" not in msg["content"]
        assert "Django" not in msg["content"]


# ---------------------------------------------------------------------------
# Existing integration test — user-scoped conversations (updated for opt-in)
# ---------------------------------------------------------------------------

@patch("app.services.conversation_service.generate_chat", new_callable=AsyncMock)
def test_conversation_is_user_scoped(mock_chat):
    """Full integration: profile context appears when use_profile=true,
    conversation ownership is enforced, and history grows correctly."""
    mock_chat.return_value = "Focus on Python, APIs, and databases."
    user_a_id, username_a = _create_user("test_ai_a")
    user_b_id, username_b = _create_user("test_ai_b")
    _add_profile(user_a_id, ["Python", "FastAPI", "PostgreSQL", "Docker"])
    _add_profile(user_b_id, ["Kubernetes"])
    headers_a = _login(username_a)
    headers_b = _login(username_b)

    # User A starts a conversation WITH profile context
    create_res = client.post(
        "/api/ai/conversations",
        headers=headers_a,
        json={"content": "What skills should I learn for backend development?", "use_profile": True},
    )
    assert create_res.status_code == 200, create_res.text
    payload = create_res.json()
    conversation_id = payload["conversation"]["id"]
    assert payload["assistant_message"]["content"].startswith("Focus on Python")
    assert mock_chat.call_args.args[0][0]["role"] == "system"
    assert mock_chat.call_args.args[0][-1]["role"] == "user"
    system_context = mock_chat.call_args.args[0][0]["content"]
    assert "USER PROFILE CONTEXT" in system_context
    assert "Backend Developer" in system_context
    for skill in ["Python", "FastAPI", "PostgreSQL", "Docker"]:
        assert skill in system_context
    assert "CareerSphere AI" in system_context
    assert "Kubernetes" not in system_context
    assert "password" not in system_context.lower()

    # Conversation list scoping
    list_a = client.get("/api/ai/conversations", headers=headers_a)
    list_b = client.get("/api/ai/conversations", headers=headers_b)
    assert list_a.status_code == 200
    assert any(item["id"] == conversation_id for item in list_a.json())
    assert list_b.json() == []

    # User B cannot view User A's conversation
    forbidden = client.get(f"/api/ai/conversations/{conversation_id}", headers=headers_b)
    assert forbidden.status_code == 404

    # Follow-up in same conversation — history grows, profile still present (use_profile=true)
    follow_up = client.post(
        f"/api/ai/conversations/{conversation_id}/messages",
        headers=headers_a,
        json={"content": "Which one should I learn first?", "use_profile": True},
    )
    assert follow_up.status_code == 200, follow_up.text
    sent_roles = [item["role"] for item in mock_chat.call_args.args[0] if item["role"] != "system"]
    assert sent_roles == ["user", "assistant", "user"]
    for skill in ["Python", "FastAPI", "PostgreSQL", "Docker"]:
        assert skill in mock_chat.call_args.args[0][0]["content"]

    # User B cannot delete User A's conversation
    delete_forbidden = client.delete(f"/api/ai/conversations/{conversation_id}", headers=headers_b)
    assert delete_forbidden.status_code == 404

    delete_ok = client.delete(f"/api/ai/conversations/{conversation_id}", headers=headers_a)
    assert delete_ok.status_code == 204


# ---------------------------------------------------------------------------
# Existing one-shot chat test — updated for opt-in profile (use_profile=true)
# ---------------------------------------------------------------------------

@patch("app.services.ollama_service.generate_chat", new_callable=AsyncMock)
def test_one_shot_chat_uses_authenticated_profile(mock_chat):
    """The /ai/chat endpoint includes profile context only when use_profile=true."""
    mock_chat.return_value = "Your strongest listed skills are Python and FastAPI."
    user_id, username = _create_user("test_ai_profile")
    _add_profile(user_id, ["Python", "FastAPI"])
    headers = _login(username)

    # Without use_profile — no profile context
    res_no_profile = client.post(
        "/api/ai/chat",
        headers=headers,
        json={"prompt": "What are my strongest skills?"},
    )
    assert res_no_profile.status_code == 200, res_no_profile.text
    messages_no_profile = mock_chat.call_args.args[0]
    assert "USER PROFILE CONTEXT" not in messages_no_profile[0]["content"]

    # With use_profile=true — profile context must be present
    res_with_profile = client.post(
        "/api/ai/chat",
        headers=headers,
        json={"prompt": "What are my strongest skills?", "use_profile": True},
    )
    assert res_with_profile.status_code == 200, res_with_profile.text
    messages_with_profile = mock_chat.call_args.args[0]
    assert messages_with_profile[0]["role"] == "system"
    assert "USER PROFILE CONTEXT" in messages_with_profile[0]["content"]
    assert "Python" in messages_with_profile[0]["content"]
    assert "FastAPI" in messages_with_profile[0]["content"]
    assert messages_with_profile[-1] == {"role": "user", "content": "What are my strongest skills?"}
