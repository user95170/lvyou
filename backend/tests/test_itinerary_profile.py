import json
import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool

from flask import Flask
from math import radians, sin, cos, sqrt, atan2

_TEST_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TEST_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.config import Config
from app.db import db, init_db
from app.models import FoodPlace, ScenicSpot, User
from app.routes import register_routes


def _haversine_km(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    r = 6371.0
    lon1, lat1_r = radians(lng1), radians(lat1)
    lon2, lat2_r = radians(lng2), radians(lat2)
    dlon = lon2 - lon1
    dlat = lat2_r - lat1_r
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


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

        db.session.add(User(id=1, username="u1", password_hash="x"))

        for i in range(3):
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

        for i in range(2):
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


def test_itineraries_suggest_default_days_and_city_echo(client):
    app = client.application
    with app.app_context():
        scenic_ids = [s.id for s in ScenicSpot.query.order_by(ScenicSpot.id.asc()).limit(2).all()]
        food_ids = [f.id for f in FoodPlace.query.order_by(FoodPlace.id.asc()).limit(1).all()]

    resp = client.post(
        "/api/itineraries/suggest",
        json={
            "city": "呼伦贝尔",
            "candidates": {"scenic_spot": scenic_ids, "food_place": food_ids},
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))

    itinerary = data.get("itinerary")
    assert isinstance(itinerary, dict)
    assert itinerary.get("city") == "呼伦贝尔"
    assert isinstance(itinerary.get("days"), list)
    assert len(itinerary["days"]) == 2


def test_itineraries_suggest_rejects_invalid_days(client):
    resp = client.post(
        "/api/itineraries/suggest",
        json={"city": "呼伦贝尔", "days": "abc"},
    )
    assert resp.status_code == 400
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("error") == "days 必须为整数"


def test_itineraries_suggest_rejects_invalid_candidates_type(client):
    resp = client.post(
        "/api/itineraries/suggest",
        json={"city": "呼伦贝尔", "candidates": []},
    )
    assert resp.status_code == 400
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("error") == "candidates 必须为对象"


def test_itineraries_suggest_returns_error_when_no_content_for_city(client):
    resp = client.post(
        "/api/itineraries/suggest",
        json={"city": "不存在城市", "days": 2},
    )
    assert resp.status_code == 400
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("error") == "当前暂无可用内容，无法生成行程"


def test_user_profile_upsert_requires_existing_user(client):
    resp = client.post(
        "/api/user/profile",
        json={"user_id": 999, "travel_style": "relax"},
    )
    assert resp.status_code == 400
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("error") == "user not found"


def test_user_profile_upsert_allows_clearing_travel_style_and_budget(client):
    resp1 = client.post(
        "/api/user/profile",
        json={"user_id": 1, "travel_style": "relax", "budget_level": 2},
    )
    assert resp1.status_code == 200

    resp2 = client.post(
        "/api/user/profile",
        json={"user_id": 1, "travel_style": None, "budget_level": ""},
    )
    assert resp2.status_code == 200
    data2 = json.loads(resp2.data.decode("utf-8"))
    profile = data2.get("profile") or {}
    assert profile.get("travel_style") is None
    assert profile.get("budget_level") is None


def test_user_profile_upsert_rejects_budget_level_out_of_range(client):
    resp = client.post(
        "/api/user/profile",
        json={"user_id": 1, "budget_level": 5},
    )
    assert resp.status_code == 400
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("error") == "budget_level must be 1, 2, or 3"


def test_route_plan_2opt_total_distance_matches_haversine_sum(client):
    app = client.application
    app.config["AMAP_WEB_KEY"] = None

    with app.app_context():
        spots = ScenicSpot.query.order_by(ScenicSpot.id.asc()).limit(3).all()
        assert len(spots) >= 3
        spot_ids = [s.id for s in spots]

    resp = client.post(
        "/api/route/plan",
        json={"spot_ids": spot_ids, "optimize": "2opt"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))

    route = data.get("route") or []
    meta = data.get("meta") or {}
    assert len(route) >= 2
    assert meta.get("amap_used") is False

    total = 0.0
    for i in range(len(route) - 1):
        a = route[i]
        b = route[i + 1]
        total += _haversine_km(
            float(a["longitude"]),
            float(a["latitude"]),
            float(b["longitude"]),
            float(b["latitude"]),
        )

    # 后端对 total_distance_km 做了 round(,2)
    assert abs(float(meta.get("total_distance_km")) - round(total, 2)) < 1e-6
