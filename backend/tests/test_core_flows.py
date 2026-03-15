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
from app.models import ContentStandard, FoodPlace, Hotel, Rating, ScenicSpot, UserBehaviorLog
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
                ScenicSpot(
                    id=1,
                    name="Spot A",
                    city="Hohhot",
                    address="Addr A",
                    longitude=111.10,
                    latitude=40.80,
                    category="grassland",
                    rating_avg=4.7,
                    rating_count=120,
                    description="Hot scenic spot",
                ),
                ScenicSpot(
                    id=2,
                    name="Spot B",
                    city="Hohhot",
                    address="Addr B",
                    longitude=111.20,
                    latitude=40.90,
                    category="lake",
                    rating_avg=4.5,
                    rating_count=90,
                    description="Lake scenic spot",
                ),
                ScenicSpot(
                    id=3,
                    name="Spot C",
                    city="Baotou",
                    address="Addr C",
                    longitude=109.90,
                    latitude=40.70,
                    category="museum",
                    rating_avg=4.2,
                    rating_count=60,
                    description="Museum scenic spot",
                ),
                Hotel(
                    id=1,
                    name="Hotel A",
                    city="Hohhot",
                    address="Hotel Addr A",
                    longitude=111.11,
                    latitude=40.81,
                    star_level="5-star",
                    avg_price=580,
                    rating_avg=4.6,
                    rating_count=88,
                ),
                FoodPlace(
                    id=1,
                    name="Food A",
                    city="Hohhot",
                    address="Food Addr A",
                    longitude=111.12,
                    latitude=40.82,
                    cuisine_type="BBQ",
                    avg_price=88,
                    rating_avg=4.4,
                    rating_count=55,
                ),
                ContentStandard(
                    entity_type="scenic_spot",
                    entity_id=1,
                    source_type="item_cf_similarity",
                    summary=json.dumps(
                        {
                            "neighbors": [
                                {"id": 2, "sim": 0.93},
                                {"id": 3, "sim": 0.88},
                            ]
                        }
                    ),
                ),
            ]
        )
        db.session.commit()

    with app.test_client() as test_client:
        yield test_client


def _register_and_login(client, username="core_user"):
    register_resp = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "123456",
            "email": f"{username}@example.com",
        },
    )
    assert register_resp.status_code == 201
    register_data = json.loads(register_resp.data.decode("utf-8"))

    login_resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": "123456"},
    )
    assert login_resp.status_code == 200
    login_data = json.loads(login_resp.data.decode("utf-8"))
    assert login_data["message"] == "login_success"

    return register_data["id"]


def test_auth_register_login_and_duplicate_username(client):
    user_id = _register_and_login(client, username="core_user_a")
    assert user_id >= 1

    dup_resp = client.post(
        "/api/auth/register",
        json={
            "username": "core_user_a",
            "password": "123456",
            "email": "other@example.com",
        },
    )
    assert dup_resp.status_code == 400
    dup_data = json.loads(dup_resp.data.decode("utf-8"))
    assert dup_data["error"] == "username already exists"


def test_resource_lists_return_seeded_items(client):
    scenic_resp = client.get("/api/scenic-spots?city=Hohhot&page_size=5")
    hotel_resp = client.get("/api/hotels?city=Hohhot&page_size=5")
    food_resp = client.get("/api/foods?city=Hohhot&page_size=5")

    assert scenic_resp.status_code == 200
    assert hotel_resp.status_code == 200
    assert food_resp.status_code == 200

    scenic_data = json.loads(scenic_resp.data.decode("utf-8"))
    hotel_data = json.loads(hotel_resp.data.decode("utf-8"))
    food_data = json.loads(food_resp.data.decode("utf-8"))

    assert len(scenic_data["items"]) == 2
    assert scenic_data["items"][0]["name"] == "Spot A"
    assert len(hotel_data["items"]) == 1
    assert hotel_data["items"][0]["name"] == "Hotel A"
    assert len(food_data["items"]) == 1
    assert food_data["items"][0]["name"] == "Food A"


def test_rating_updates_target_aggregate(client):
    user_id = _register_and_login(client, username="core_user_b")

    resp = client.post(
        "/api/ratings",
        json={
            "user_id": user_id,
            "target_type": "scenic_spot",
            "target_id": 1,
            "score": 5,
            "comment": "great",
        },
    )
    assert resp.status_code == 201
    data = json.loads(resp.data.decode("utf-8"))
    assert data["rating"]["target_id"] == 1
    assert data["aggregate"]["rating_count"] == 1
    assert data["aggregate"]["rating_avg"] == 5.0

    app = client.application
    with app.app_context():
        saved = Rating.query.filter_by(user_id=user_id, target_id=1).first()
        spot = db.session.get(ScenicSpot, 1)
        assert saved is not None
        assert spot is not None
        assert float(spot.rating_avg) == 5.0
        assert int(spot.rating_count) == 1


def test_behavior_endpoint_persists_log(client):
    user_id = _register_and_login(client, username="core_user_c")

    resp = client.post(
        "/api/behaviors",
        json={
            "user_id": user_id,
            "target_type": "scenic_spot",
            "target_id": 1,
            "behavior_type": "click",
            "device": "web",
        },
    )
    assert resp.status_code == 201
    data = json.loads(resp.data.decode("utf-8"))
    assert data["behavior_type"] == "click"
    assert data["target_id"] == 1

    app = client.application
    with app.app_context():
        saved = UserBehaviorLog.query.filter_by(user_id=user_id, target_id=1).first()
        assert saved is not None
        assert saved.behavior_type == "click"


def test_recommend_endpoints_return_items_and_metrics(client):
    scenic_resp = client.get("/api/recommend/scenic-spots?city=Hohhot&limit=5")
    hotel_resp = client.get("/api/recommend/hotels?city=Hohhot&limit=5")
    food_resp = client.get("/api/recommend/foods?city=Hohhot&limit=5")
    metrics_resp = client.get("/api/recommend/metrics")

    assert scenic_resp.status_code == 200
    assert hotel_resp.status_code == 200
    assert food_resp.status_code == 200
    assert metrics_resp.status_code == 200

    scenic_data = json.loads(scenic_resp.data.decode("utf-8"))
    hotel_data = json.loads(hotel_resp.data.decode("utf-8"))
    food_data = json.loads(food_resp.data.decode("utf-8"))
    metrics_data = json.loads(metrics_resp.data.decode("utf-8"))

    assert len(scenic_data["items"]) >= 1
    assert len(hotel_data["items"]) >= 1
    assert len(food_data["items"]) >= 1
    assert "request_count" in metrics_data
    assert "strategy_counts" in metrics_data
    assert "fallback_counts" in metrics_data


def test_similar_scenic_endpoint_uses_item_cf_summary(client):
    resp = client.get("/api/recommend/scenic-spots/1/similar?limit=2")
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))

    assert data["meta"]["source"] == "item_cf_similarity"
    assert [item["id"] for item in data["items"]] == [2, 3]
