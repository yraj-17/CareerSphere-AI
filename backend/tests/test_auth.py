import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.db.models import User

# Test database
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///./test_careersphere.db"
test_engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "CareerSphere AI" in data["service"]


def test_check_username_availability():
    # Valid and available username
    res = client.get("/api/auth/check-username", params={"username": "raj_yadav"})
    assert res.status_code == 200
    assert res.json()["available"] is True

    # Invalid username with spaces
    res = client.get("/api/auth/check-username", params={"username": "raj yadav"})
    assert res.status_code == 200
    assert res.json()["available"] is False
    assert "spaces" in res.json()["message"]

    # Short username
    res = client.get("/api/auth/check-username", params={"username": "ab"})
    assert res.status_code == 200
    assert res.json()["available"] is False


def test_register_validation_rules():
    # Missing/empty first name
    res = client.post("/api/auth/register", json={
        "first_name": "  ",
        "last_name": "Yadav",
        "username": "raj123",
        "email": "raj@example.com",
        "password": "Password123"
    })
    assert res.status_code == 422

    # Username with spaces
    res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Yadav",
        "username": "raj yadav",
        "email": "raj@example.com",
        "password": "Password123"
    })
    assert res.status_code == 422

    # Weak password (< 8 chars)
    res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Yadav",
        "username": "raj123",
        "email": "raj@example.com",
        "password": "Pass1"
    })
    assert res.status_code == 422

    # Weak password (no number)
    res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Yadav",
        "username": "raj123",
        "email": "raj@example.com",
        "password": "Password"
    })
    assert res.status_code == 422

    # Weak password (no uppercase)
    res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Yadav",
        "username": "raj123",
        "email": "raj@example.com",
        "password": "password123"
    })
    assert res.status_code == 422


def test_register_and_login_flow():
    # 1. Successful registration
    signup_data = {
        "first_name": "Raj",
        "last_name": "Yadav",
        "username": "raj_yadav",
        "email": "raj@example.com",
        "password": "Password123"
    }
    reg_res = client.post("/api/auth/register", json=signup_data)
    assert reg_res.status_code == 201
    user = reg_res.json()
    assert user["username"] == "raj_yadav"
    assert user["email"] == "raj@example.com"
    assert "password_hash" not in user
    assert "password" not in user

    # 2. Check username availability now reflects taken
    check_res = client.get("/api/auth/check-username", params={"username": "raj_yadav"})
    assert check_res.status_code == 200
    assert check_res.json()["available"] is False
    assert "taken" in check_res.json()["message"]

    # 3. Duplicate username rejection
    dup_user_res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Kumar",
        "username": "raj_yadav",
        "email": "different@example.com",
        "password": "Password123"
    })
    assert dup_user_res.status_code == 409
    assert "username is already taken" in dup_user_res.json()["detail"]

    # 4. Duplicate email rejection
    dup_email_res = client.post("/api/auth/register", json={
        "first_name": "Raj",
        "last_name": "Kumar",
        "username": "raj_other",
        "email": "raj@example.com",
        "password": "Password123"
    })
    assert dup_email_res.status_code == 409
    assert "email already exists" in dup_email_res.json()["detail"]

    # 5. Login using Username
    login_user_res = client.post("/api/auth/login", json={
        "identifier": "raj_yadav",
        "password": "Password123"
    })
    assert login_user_res.status_code == 200
    token_data = login_user_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["user"]["username"] == "raj_yadav"
    token = token_data["access_token"]

    # 6. Login using Email
    login_email_res = client.post("/api/auth/login", json={
        "identifier": "raj@example.com",
        "password": "Password123"
    })
    assert login_email_res.status_code == 200
    assert "access_token" in login_email_res.json()

    # 7. Login with Wrong Password
    wrong_pwd_res = client.post("/api/auth/login", json={
        "identifier": "raj_yadav",
        "password": "WrongPassword123"
    })
    assert wrong_pwd_res.status_code == 401
    assert "Invalid username/email or password." in wrong_pwd_res.json()["detail"]

    # 8. Login with Non-existent user
    non_user_res = client.post("/api/auth/login", json={
        "identifier": "non_existent_user",
        "password": "Password123"
    })
    assert non_user_res.status_code == 401
    assert "Invalid username/email or password." in non_user_res.json()["detail"]

    # 9. Access protected /api/auth/me with Bearer token
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "raj_yadav"
    assert me_data["email"] == "raj@example.com"
    assert me_data["first_name"] == "Raj"

    # 10. Access protected /api/auth/me without token
    unauth_res = client.get("/api/auth/me")
    assert unauth_res.status_code == 401

    # 11. Logout
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200
