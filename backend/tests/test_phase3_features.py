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
from app.models import Activity, ScenicSpot, Specialty, Transportation, User
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

    init_db(app)
    register_routes(app)

    with app.app_context():
        db.create_all()
        db.session.add_all(
            [
                ScenicSpot(id=1, name="景点甲", city="呼和浩特", longitude=111.66, latitude=40.81, rating_avg=4.5, rating_count=50),
                ScenicSpot(id=2, name="景点乙", city="呼和浩特", longitude=111.70, latitude=40.84, rating_avg=4.3, rating_count=40),
                ScenicSpot(id=3, name="景点丙", city="呼和浩特", longitude=111.62, latitude=40.79, rating_avg=4.1, rating_count=30),
                Transportation(id=1, name="呼和浩特站", city="呼和浩特", transport_type="火车站", longitude=111.668, latitude=40.842, rating_avg=None, rating_count=0),
                Activity(id=1, name="中老年文化展", city="呼和浩特", activity_type="展览", tags="中老年;文化;安静", rating_avg=4.2, rating_count=10),
                Activity(id=2, name="青年音乐节", city="呼和浩特", activity_type="演出", tags="年轻人;音乐;夜场", rating_avg=4.2, rating_count=10),
                Specialty(id=1, name="湘味辣酱", city="呼和浩特", category="食品", tags="辣;伴手礼", rating_avg=4.2, rating_count=10),
                Specialty(id=2, name="清淡奶豆腐", city="呼和浩特", category="奶制品", tags="清淡;伴手礼", rating_avg=4.2, rating_count=10),
            ]
        )
        db.session.commit()

    with app.test_client() as test_client:
        yield test_client


def _register(client, username):
    resp = client.post("/api/auth/register", json={"username": username, "password": "123456"})
    return json.loads(resp.data.decode("utf-8"))["id"]


def test_rating_transportation_updates_aggregate(client):
    uid = _register(client, "rater")
    resp = client.post(
        "/api/ratings",
        json={"user_id": uid, "target_type": "transportation", "target_id": 1, "score": 4},
    )
    assert resp.status_code == 201
    data = json.loads(resp.data.decode("utf-8"))
    assert data["aggregate"]["rating_count"] == 1

    detail = client.get("/api/transportations/1")
    body = json.loads(detail.data.decode("utf-8"))
    assert body["rating_count"] == 1
    assert float(body["rating_avg"]) == 4.0


def test_route_plan_with_start_location(client):
    resp = client.post(
        "/api/route/plan",
        json={
            "spot_ids": [1, 2, 3],
            "start_location": {"lng": 111.65, "lat": 40.80},
            "optimize": "greedy",
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))
    assert data["meta"]["start_location_used"] is True
    route = data["route"]
    # 起点应为用户位置，且后续包含 3 个景点
    assert route[0].get("is_origin") is True
    assert len(route) == 4


def test_route_plan_invalid_start_location(client):
    resp = client.post(
        "/api/route/plan",
        json={"spot_ids": [1, 2], "start_location": {"lng": "x", "lat": 40.8}},
    )
    assert resp.status_code == 400


def test_route_plan_options_with_location(client):
    resp = client.post(
        "/api/route/plan-options",
        json={"spot_ids": [1, 2, 3], "start_location": {"lng": 111.65, "lat": 40.80}},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))
    assert data["meta"]["start_location_used"] is True
    options = data["options"]
    assert len(options) >= 1
    labels = [o["label"] for o in options]
    assert "最短路线" in labels
    for opt in options:
        assert opt["route"][0].get("is_origin") is True  # 起点为用户位置
        assert "total_distance_km" in opt
        assert opt["stop_count"] == 3  # 3 个景点（不含起点）


def test_route_plan_options_invalid_spot_ids(client):
    resp = client.post("/api/route/plan-options", json={"spot_ids": [1]})
    assert resp.status_code == 400


def _register_full(client, username, **demo):
    payload = {"username": username, "password": "123456"}
    payload.update(demo)
    resp = client.post("/api/auth/register", json=payload)
    return json.loads(resp.data.decode("utf-8"))["id"]


def test_activity_personalized_for_senior(client):
    uid = _register_full(client, "act_senior", age=66, gender="female")
    resp = client.get(f"/api/activities?user_id={uid}&limit=10")
    items = json.loads(resp.data.decode("utf-8"))["items"]
    # 中老年文化展应排在青年音乐节之前，并带匹配理由
    assert items[0]["id"] == 1
    assert any("中老年" in r for r in items[0].get("reasons", []))


def test_activity_personalized_for_young(client):
    uid = _register_full(client, "act_young", age=22, gender="male")
    resp = client.get(f"/api/activities?user_id={uid}&limit=10")
    items = json.loads(resp.data.decode("utf-8"))["items"]
    assert items[0]["id"] == 2
    assert any("年轻人" in r for r in items[0].get("reasons", []))


def test_specialty_personalized_home_region(client):
    uid = _register_full(client, "spec_hunan", home_region="湖南", age=30)
    resp = client.get(f"/api/specialties?user_id={uid}&limit=10")
    items = json.loads(resp.data.decode("utf-8"))["items"]
    spicy = next(i for i in items if i["id"] == 1)
    assert any("家乡口味" in r for r in spicy.get("reasons", []))


def test_personalized_map_includes_coordinates(client):
    resp = client.post(
        "/api/map/personalized",
        json={"categories": ["scenic_spot", "transportation"], "limit_per_type": 10},
    )
    assert resp.status_code == 200
    items = json.loads(resp.data.decode("utf-8"))["items"]
    assert items["scenic_spot"]
    assert items["scenic_spot"][0]["longitude"] is not None
    assert items["transportation"][0]["latitude"] is not None
