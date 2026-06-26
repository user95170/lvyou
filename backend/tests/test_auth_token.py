import json
import sys
from pathlib import Path

import pytest
from flask import Flask
from sqlalchemy.pool import StaticPool

_TEST_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TEST_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.config import Config
from app.db import db, init_db
from app.models import ScenicSpot
from app.routes import register_routes
from app.services.auth_tokens import generate_token, verify_token


@pytest.fixture
def app_client():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

    init_db(app)
    register_routes(app)

    with app.app_context():
        db.create_all()
        db.session.add(
            ScenicSpot(id=1, name="景点甲", city="呼和浩特", rating_avg=4.0, rating_count=10)
        )
        db.session.commit()

    with app.test_client() as client:
        yield app, client


def _register_login(client, username):
    client.post("/api/auth/register", json={"username": username, "password": "123456"})
    resp = client.post("/api/auth/login", json={"username": username, "password": "123456"})
    data = json.loads(resp.data.decode("utf-8"))
    return data["user"]["id"], data["token"]


def test_login_returns_token(app_client):
    _, client = app_client
    uid, token = _register_login(client, "tok_user")
    assert token


def test_token_roundtrip(app_client):
    app, _ = app_client
    with app.app_context():
        token = generate_token(123)
        assert verify_token(token) == 123
        assert verify_token("garbage") is None


def test_rating_with_matching_token_ok(app_client):
    _, client = app_client
    uid, token = _register_login(client, "tok_match")
    resp = client.post(
        "/api/ratings",
        json={"user_id": uid, "target_type": "scenic_spot", "target_id": 1, "score": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201


def test_rating_with_mismatched_token_forbidden(app_client):
    _, client = app_client
    uid_a, token_a = _register_login(client, "tok_a")
    uid_b, _ = _register_login(client, "tok_b")
    resp = client.post(
        "/api/ratings",
        json={"user_id": uid_b, "target_type": "scenic_spot", "target_id": 1, "score": 5},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 403


def test_rating_with_invalid_token_unauthorized(app_client):
    _, client = app_client
    uid, _ = _register_login(client, "tok_inv")
    resp = client.post(
        "/api/ratings",
        json={"user_id": uid, "target_type": "scenic_spot", "target_id": 1, "score": 5},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401


def test_rating_without_token_legacy_ok(app_client):
    _, client = app_client
    uid, _ = _register_login(client, "tok_legacy")
    resp = client.post(
        "/api/ratings",
        json={"user_id": uid, "target_type": "scenic_spot", "target_id": 1, "score": 5},
    )
    assert resp.status_code == 201


def test_trip_create_mismatched_token_forbidden(app_client):
    _, client = app_client
    uid_a, token_a = _register_login(client, "trip_a")
    uid_b, _ = _register_login(client, "trip_b")
    payload = {
        "user_id": uid_b,
        "title": "测试行程",
        "origin_city": "呼和浩特",
        "trip_days": [
            {"day_index": 1, "items": [{"item_type": "custom", "title_snapshot": "自由活动"}]}
        ],
    }
    resp = client.post(
        "/api/trips", json=payload, headers={"Authorization": f"Bearer {token_a}"}
    )
    assert resp.status_code == 403


def test_behavior_anonymous_with_token_allowed(app_client):
    # 携带令牌但记录匿名行为（无 user_id）应放行
    _, client = app_client
    uid, token = _register_login(client, "beh_user")
    resp = client.post(
        "/api/behaviors",
        json={"target_type": "scenic_spot", "target_id": 1, "behavior_type": "view"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
