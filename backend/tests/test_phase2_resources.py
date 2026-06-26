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
from app.models import Activity, Specialty, Transportation
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
                Transportation(
                    id=1, name="呼和浩特站", city="呼和浩特", transport_type="火车站",
                    phone="12306", operating_hours="05:30-23:30", price_info="公交2元",
                    rating_avg=4.2, rating_count=90, tags="火车站",
                ),
                Transportation(
                    id=2, name="包头站", city="包头", transport_type="火车站",
                    rating_avg=4.0, rating_count=30, tags="火车站",
                ),
                Activity(
                    id=1, name="那达慕大会", city="锡林郭勒", activity_type="节庆",
                    hold_time="每年7月", price_info="80-160元", rating_avg=4.8,
                    rating_count=200, tags="亲子;民俗", description="草原盛会",
                ),
                Specialty(
                    id=1, name="科尔沁牛肉干", city="通辽", category="食品",
                    business_hours="09:00-20:00", price_info="80-160元/袋",
                    rating_avg=4.7, rating_count=210, tags="伴手礼;必买",
                    description="风干牛肉干",
                ),
            ]
        )
        db.session.commit()

    with app.test_client() as test_client:
        yield test_client


def _items(resp):
    return json.loads(resp.data.decode("utf-8"))["items"]


def test_transportation_list_and_city_filter(client):
    resp = client.get("/api/transportations")
    assert resp.status_code == 200
    assert len(_items(resp)) == 2

    resp2 = client.get("/api/transportations?city=包头")
    items = _items(resp2)
    assert len(items) == 1
    assert items[0]["name"] == "包头站"


def test_transportation_type_filter_and_detail(client):
    resp = client.get("/api/transportations?transport_type=火车站")
    assert len(_items(resp)) == 2

    detail = client.get("/api/transportations/1")
    assert detail.status_code == 200
    data = json.loads(detail.data.decode("utf-8"))
    assert data["name"] == "呼和浩特站"
    assert data["operating_hours"] == "05:30-23:30"

    missing = client.get("/api/transportations/999")
    assert missing.status_code == 404


def test_activity_list_keyword_and_detail(client):
    resp = client.get("/api/activities?keyword=那达慕")
    items = _items(resp)
    assert len(items) == 1
    assert items[0]["activity_type"] == "节庆"

    detail = client.get("/api/activities/1")
    assert detail.status_code == 200
    data = json.loads(detail.data.decode("utf-8"))
    assert data["hold_time"] == "每年7月"
    assert "亲子" in (data["tags"] or "")


def test_specialty_list_and_detail(client):
    resp = client.get("/api/specialties?category=食品")
    items = _items(resp)
    assert len(items) == 1
    assert items[0]["name"] == "科尔沁牛肉干"

    detail = client.get("/api/specialties/1")
    assert detail.status_code == 200
    data = json.loads(detail.data.decode("utf-8"))
    assert data["price_info"] == "80-160元/袋"


def test_monitor_counts_new_resources(client):
    resp = client.get("/api/monitor/overview")
    assert resp.status_code == 200
    resources = json.loads(resp.data.decode("utf-8"))["resources"]
    assert resources["transportations"] == 2
    assert resources["activities"] == 1
    assert resources["specialties"] == 1


def test_personalized_map_includes_new_types(client):
    resp = client.post("/api/map/personalized", json={"limit_per_type": 10})
    assert resp.status_code == 200
    items = json.loads(resp.data.decode("utf-8"))["items"]
    assert len(items["transportation"]) == 2
    assert len(items["activity"]) == 1
    assert len(items["specialty"]) == 1
