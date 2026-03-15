import json
import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool

from flask import Flask

_TEST_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TEST_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.config import Config
from app.db import db
from app.db import init_db
from app.models import FoodPlace, ScenicSpot, User, UserProfile
from app.routes import register_routes


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    app.config["LLM_API_KEY"] = None

    init_db(app)
    register_routes(app)

    with app.app_context():
        db.create_all()

        db.session.add(User(id=1, username="u1", password_hash="x"))

        for i in range(8):
            db.session.add(
                ScenicSpot(
                    name=f"景点{i + 1}",
                    city="呼伦贝尔",
                    address=f"地址{i + 1}",
                    longitude=119.0 + i * 0.01,
                    latitude=49.0 + i * 0.01,
                    rating_avg=4.6,
                    rating_count=100 + i,
                )
            )

        for i in range(4):
            db.session.add(
                FoodPlace(
                    name=f"美食{i + 1}",
                    city="呼伦贝尔",
                    address=f"美食地址{i + 1}",
                    longitude=119.5 + i * 0.01,
                    latitude=49.5 + i * 0.01,
                    rating_avg=4.2,
                    rating_count=50 + i,
                )
            )

        db.session.commit()

    with app.test_client() as c:
        yield c


def test_agent_chat_multi_turn_merge_and_itinerary_anonymous(client):
    user_msg = "预算5000 自驾 想看草原和湖泊 亲子"
    resp = client.post(
        "/api/agent/chat",
        json={
            "text": user_msg,
            "messages": [
                {"role": "assistant", "content": "你好"},
                {"role": "user", "content": "去呼伦贝尔"},
                {"role": "assistant", "content": "好的"},
                {"role": "user", "content": "玩4天"},
                {"role": "assistant", "content": "继续"},
                {"role": "user", "content": user_msg},
            ],
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))

    assert isinstance(data.get("reply"), str) and data["reply"]

    slots = data.get("slots") or {}
    assert slots.get("destination") == "呼伦贝尔"
    assert slots.get("days") == 4
    assert slots.get("transport_mode") == "drive"
    assert slots.get("budget_level") == 3
    assert slots.get("travel_style") == "family"
    assert "草原" in (slots.get("interests") or [])
    assert "湖泊" in (slots.get("interests") or [])

    assert data.get("profile") is None

    itinerary = data.get("itinerary")
    assert isinstance(itinerary, dict)
    assert itinerary.get("city") == "呼伦贝尔"
    assert isinstance(itinerary.get("days"), list) and len(itinerary["days"]) == 4
    assert isinstance(itinerary["days"][0].get("items"), list) and len(itinerary["days"][0]["items"]) >= 1


def test_agent_chat_profile_update_when_logged_in(client):
    resp = client.post(
        "/api/agent/chat",
        json={
            "user_id": 1,
            "text": "预算5000 亲子 草原 湖泊",
            "messages": [
                {"role": "assistant", "content": "你好"},
                {"role": "user", "content": "预算5000 亲子 草原 湖泊"},
            ],
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))

    profile = data.get("profile")
    assert isinstance(profile, dict)
    assert profile.get("budget_level") == 3
    assert profile.get("travel_style") == "family"
    assert "草原" in (profile.get("prefer_scenic_types") or "")

    app = client.application
    with app.app_context():
        p = UserProfile.query.filter_by(user_id=1).first()
        assert p is not None
        assert p.budget_level == 3
        assert p.travel_style == "family"
        assert "草原" in (p.prefer_scenic_types or "")


def test_agent_chat_rejects_overlong_input(client):
    app = client.application
    app.config["AGENT_MAX_INPUT_CHARS"] = 5

    resp = client.post(
        "/api/agent/chat",
        json={
            "text": "123456",
            "messages": [{"role": "user", "content": "123456"}],
        },
    )
    assert resp.status_code == 400
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("error") == "输入过长，请简化描述后再试"


def test_agent_chat_rejects_too_many_turns(client):
    app = client.application
    app.config["AGENT_MAX_TURNS"] = 1

    resp = client.post(
        "/api/agent/chat",
        json={
            "text": "第二句",
            "messages": [
                {"role": "user", "content": "第一句"},
                {"role": "assistant", "content": "好的"},
                {"role": "user", "content": "第二句"},
            ],
        },
    )
    assert resp.status_code == 400
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("error") == "对话轮次过多，请清空对话后继续"


def test_agent_chat_destination_regex_does_not_capture_trailing_verb(client):
    resp = client.post(
        "/api/agent/chat",
        json={
            "text": "想自驾去呼伦贝尔玩3天",
            "messages": [{"role": "user", "content": "想自驾去呼伦贝尔玩3天"}],
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))
    assert (data.get("slots") or {}).get("destination") == "呼伦贝尔"


def test_agent_chat_turn_limit_counts_text_when_not_in_messages(client):
    app = client.application
    app.config["AGENT_MAX_TURNS"] = 1

    # messages 中已有 1 条 user 回合，如果 text 不计数将绕过限制；应返回 400
    resp = client.post(
        "/api/agent/chat",
        json={
            "text": "第二句",
            "messages": [
                {"role": "user", "content": "第一句"},
                {"role": "assistant", "content": "好的"},
            ],
        },
    )
    assert resp.status_code == 400
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("error") == "对话轮次过多，请清空对话后继续"
