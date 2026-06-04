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
from app.models import FoodPlace, Hotel, ScenicSpot, Trip, TripDay, TripItem, User
from app.routes import register_routes


def _single_day_trip_payload(user_id=1):
    return {
        "user_id": user_id,
        "title": "呼和浩特一日游路线",
        "start_date": "2026-04-10",
        "origin_city": "呼和浩特",
        "created_by": "route_planner",
        "trip_days": [
            {
                "day_index": 1,
                "note": None,
                "items": [
                    {
                        "item_index": 1,
                        "item_type": "scenic_spot",
                        "ref_id": 1,
                        "title_snapshot": "大召寺",
                        "city_snapshot": "呼和浩特",
                        "address_snapshot": "玉泉区大召前街",
                        "start_time": None,
                        "end_time": None,
                        "transport_mode": None,
                        "note": None,
                    },
                    {
                        "item_index": 2,
                        "item_type": "scenic_spot",
                        "ref_id": 2,
                        "title_snapshot": "内蒙古博物院",
                        "city_snapshot": "呼和浩特",
                        "address_snapshot": "新城区新华东街",
                        "start_time": None,
                        "end_time": None,
                        "transport_mode": None,
                        "note": None,
                    },
                ],
            }
        ],
    }


def _multi_day_trip_payload(user_id=1):
    return {
        "user_id": user_id,
        "title": "呼伦贝尔三日游",
        "start_date": "2026-04-10",
        "origin_city": "呼伦贝尔",
        "created_by": "agent_planner",
        "trip_days": [
            {
                "day_index": 2,
                "note": "第二天去美食街",
                "items": [
                    {
                        "item_index": 2,
                        "item_type": "food_place",
                        "ref_id": 101,
                        "title_snapshot": "锅茶体验",
                        "city_snapshot": "呼伦贝尔",
                        "address_snapshot": "海拉尔区民族路",
                        "start_time": "12:30",
                        "end_time": "13:30",
                        "transport_mode": "walk",
                        "note": "午餐",
                    }
                ],
            },
            {
                "day_index": 1,
                "note": "第一天先逛景点",
                "items": [
                    {
                        "item_index": 1,
                        "item_type": "scenic_spot",
                        "ref_id": 1,
                        "title_snapshot": "大召寺",
                        "city_snapshot": "呼和浩特",
                        "address_snapshot": "玉泉区大召前街",
                        "start_time": "09:00",
                        "end_time": "11:00",
                        "transport_mode": "drive",
                        "note": "上午出发",
                    }
                ],
            },
            {
                "day_index": 3,
                "note": "第三天补充自定义活动",
                "items": [
                    {
                        "item_index": 1,
                        "item_type": "custom",
                        "ref_id": None,
                        "title_snapshot": "夜间篝火活动",
                        "city_snapshot": "呼伦贝尔",
                        "address_snapshot": "营地活动区",
                        "start_time": "19:00",
                        "end_time": "21:00",
                        "transport_mode": None,
                        "note": "可选活动",
                    }
                ],
            },
        ],
    }


def _blank_trip_payload(user_id=1, days=3):
    return {
        "user_id": user_id,
        "title": f"呼伦贝尔 {days} 天行程",
        "start_date": "2026-04-10",
        "origin_city": "呼伦贝尔",
        "created_by": "manual_draft",
        "trip_days": [
            {
                "day_index": day_index + 1,
                "note": None,
                "items": [],
            }
            for day_index in range(days)
        ],
    }


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
                User(id=1, username="u1", password_hash="x"),
                User(id=2, username="u2", password_hash="x"),
                ScenicSpot(
                    id=1,
                    name="大召寺",
                    city="呼和浩特",
                    address="玉泉区大召前街",
                    longitude=111.654,
                    latitude=40.807,
                ),
                ScenicSpot(
                    id=2,
                    name="内蒙古博物院",
                    city="呼和浩特",
                    address="新城区新华东街",
                    longitude=111.720,
                    latitude=40.842,
                ),
                FoodPlace(
                    id=101,
                    name="锅茶体验",
                    city="呼伦贝尔",
                    address="海拉尔区民族路",
                    longitude=119.775,
                    latitude=49.215,
                ),
                Hotel(
                    id=201,
                    name="Hotel Seed",
                    city="鍛煎拰娴╃壒",
                    address="Seed Address",
                    longitude=111.706,
                    latitude=40.812,
                ),
            ]
        )
        db.session.commit()

    with app.test_client() as test_client:
        yield test_client


def test_create_multiday_trip_and_get_derived_schedule(client):
    create_resp = client.post("/api/trips", json=_multi_day_trip_payload())
    assert create_resp.status_code == 201
    trip = json.loads(create_resp.data.decode("utf-8"))["trip"]

    assert trip["title"] == "呼伦贝尔三日游"
    assert trip["days"] == 3
    assert trip["start_date"] == "2026-04-10"
    assert trip["end_date"] == "2026-04-12"
    assert [day["day_index"] for day in trip["trip_days"]] == [1, 2, 3]
    assert [day["date"] for day in trip["trip_days"]] == [
        "2026-04-10",
        "2026-04-11",
        "2026-04-12",
    ]
    assert trip["trip_days"][1]["items"][0]["item_type"] == "food_place"
    assert trip["trip_days"][0]["items"][0]["longitude"] == pytest.approx(111.654)
    assert trip["trip_days"][0]["items"][0]["latitude"] == pytest.approx(40.807)
    assert trip["trip_days"][1]["items"][0]["longitude"] == pytest.approx(119.775)
    assert trip["trip_days"][1]["items"][0]["latitude"] == pytest.approx(49.215)
    assert trip["trip_days"][2]["items"][0]["item_type"] == "custom"
    assert trip["trip_days"][2]["items"][0]["longitude"] is None
    assert trip["trip_days"][2]["items"][0]["latitude"] is None

    trip_id = trip["id"]
    detail_resp = client.get(f"/api/trips/{trip_id}?user_id=1")
    assert detail_resp.status_code == 200
    detail_trip = json.loads(detail_resp.data.decode("utf-8"))["trip"]
    assert len(detail_trip["trip_days"]) == 3
    assert detail_trip["trip_days"][0]["items"][0]["longitude"] == pytest.approx(111.654)
    assert detail_trip["trip_days"][1]["items"][0]["latitude"] == pytest.approx(49.215)

    list_resp = client.get("/api/trips?user_id=1")
    assert list_resp.status_code == 200
    summary = json.loads(list_resp.data.decode("utf-8"))["items"][0]
    assert summary["days"] == 3
    assert summary["item_count"] == 3


def test_create_trip_rejects_invalid_user_and_trip_day_bounds(client):
    payload = _multi_day_trip_payload(user_id="")
    resp = client.post("/api/trips", json=payload)
    assert resp.status_code == 400
    assert json.loads(resp.data.decode("utf-8"))["error"] == "valid user_id is required"

    payload = _multi_day_trip_payload(user_id=999)
    resp = client.post("/api/trips", json=payload)
    assert resp.status_code == 400
    assert json.loads(resp.data.decode("utf-8"))["error"] == "user not found"

    payload = _multi_day_trip_payload()
    payload["trip_days"] = []
    resp = client.post("/api/trips", json=payload)
    assert resp.status_code == 400
    assert json.loads(resp.data.decode("utf-8"))["error"] == "trip_days must contain 1 to 10 days"

    payload = _multi_day_trip_payload()
    payload["trip_days"] = [
        {"day_index": idx + 1, "items": [{"item_type": "custom", "title_snapshot": f"活动{idx + 1}"}]}
        for idx in range(11)
    ]
    resp = client.post("/api/trips", json=payload)
    assert resp.status_code == 400
    assert json.loads(resp.data.decode("utf-8"))["error"] == "trip_days must contain 1 to 10 days"

    payload = _blank_trip_payload()
    payload["title"] = ""
    resp = client.post("/api/trips", json=payload)
    assert resp.status_code == 400
    assert json.loads(resp.data.decode("utf-8"))["error"] == "title is required"

    payload = _blank_trip_payload()
    payload["origin_city"] = ""
    resp = client.post("/api/trips", json=payload)
    assert resp.status_code == 400
    assert json.loads(resp.data.decode("utf-8"))["error"] == "origin_city is required"


def test_trip_allows_empty_day_and_blank_multiday_draft(client):
    payload = _multi_day_trip_payload()
    payload["trip_days"][0]["items"] = []
    resp = client.post("/api/trips", json=payload)
    assert resp.status_code == 201
    trip = json.loads(resp.data.decode("utf-8"))["trip"]
    assert trip["days"] == 3
    assert trip["trip_days"][1]["items"] == []

    blank_resp = client.post("/api/trips", json=_blank_trip_payload(days=3))
    assert blank_resp.status_code == 201
    blank_trip = json.loads(blank_resp.data.decode("utf-8"))["trip"]
    assert blank_trip["created_by"] == "manual_draft"
    assert blank_trip["days"] == 3
    assert blank_trip["item_count"] == 0
    assert blank_trip["end_date"] == "2026-04-12"
    assert [day["date"] for day in blank_trip["trip_days"]] == [
        "2026-04-10",
        "2026-04-11",
        "2026-04-12",
    ]
    assert all(day["items"] == [] for day in blank_trip["trip_days"])


def test_update_trip_reorders_days_and_items_and_recomputes_dates(client):
    create_resp = client.post("/api/trips", json=_single_day_trip_payload())
    trip_id = json.loads(create_resp.data.decode("utf-8"))["trip"]["id"]

    payload = {
        "user_id": 1,
        "title": "更新后的多日行程",
        "start_date": "2026-05-01",
        "origin_city": "呼伦贝尔",
        "budget_level": 2,
        "travel_style": "family",
        "trip_days": [
            {
                "day_index": 3,
                "note": "第二天晚上自由活动",
                "items": [
                    {
                        "item_index": 3,
                        "item_type": "custom",
                        "ref_id": None,
                        "title_snapshot": "夜游老城",
                        "city_snapshot": "呼伦贝尔",
                        "address_snapshot": "中心街区",
                        "start_time": "20:00",
                        "end_time": "21:30",
                        "transport_mode": "walk",
                        "note": "饭后散步",
                    }
                ],
            },
            {
                "day_index": 1,
                "note": "第一天走景点路线",
                "items": [
                    {
                        "item_index": 2,
                        "item_type": "scenic_spot",
                        "ref_id": 2,
                        "title_snapshot": "内蒙古博物院",
                        "city_snapshot": "呼和浩特",
                        "address_snapshot": "新城区新华东街",
                        "start_time": "14:00",
                        "end_time": "16:00",
                        "transport_mode": "drive",
                        "note": "下午去",
                    },
                    {
                        "item_index": 1,
                        "item_type": "scenic_spot",
                        "ref_id": 1,
                        "title_snapshot": "大召寺",
                        "city_snapshot": "呼和浩特",
                        "address_snapshot": "玉泉区大召前街",
                        "start_time": "09:30",
                        "end_time": "11:00",
                        "transport_mode": "walk",
                        "note": "上午先去",
                    },
                ],
            },
        ],
    }

    update_resp = client.put(f"/api/trips/{trip_id}", json=payload)
    assert update_resp.status_code == 200
    trip = json.loads(update_resp.data.decode("utf-8"))["trip"]

    assert trip["title"] == "更新后的多日行程"
    assert trip["days"] == 2
    assert trip["start_date"] == "2026-05-01"
    assert trip["end_date"] == "2026-05-02"
    assert trip["budget_level"] == 2
    assert trip["travel_style"] == "family"
    assert [day["date"] for day in trip["trip_days"]] == ["2026-05-01", "2026-05-02"]
    assert trip["trip_days"][0]["items"][0]["title_snapshot"] == "大召寺"
    assert trip["trip_days"][0]["items"][1]["title_snapshot"] == "内蒙古博物院"
    assert trip["trip_days"][1]["items"][0]["item_type"] == "custom"


def test_update_start_date_without_trip_days_recomputes_existing_day_dates(client):
    create_resp = client.post("/api/trips", json=_multi_day_trip_payload())
    trip_id = json.loads(create_resp.data.decode("utf-8"))["trip"]["id"]

    update_resp = client.put(
        f"/api/trips/{trip_id}",
        json={
            "user_id": 1,
            "title": "呼伦贝尔三日游",
            "origin_city": "呼伦贝尔",
            "start_date": "2026-06-01",
        },
    )
    assert update_resp.status_code == 200
    trip = json.loads(update_resp.data.decode("utf-8"))["trip"]
    assert trip["end_date"] == "2026-06-03"
    assert [day["date"] for day in trip["trip_days"]] == [
        "2026-06-01",
        "2026-06-02",
        "2026-06-03",
    ]


def test_blank_draft_can_be_filled_and_cleared_again(client):
    create_resp = client.post("/api/trips", json=_blank_trip_payload(days=4))
    trip = json.loads(create_resp.data.decode("utf-8"))["trip"]
    trip_id = trip["id"]
    assert trip["item_count"] == 0

    fill_resp = client.put(
        f"/api/trips/{trip_id}",
        json={
            "user_id": 1,
            "title": "呼伦贝尔 4 天行程",
            "origin_city": "呼伦贝尔",
            "start_date": "2026-04-10",
            "budget_level": 2,
            "trip_days": [
                {
                    "day_index": 2,
                    "note": None,
                    "items": [
                        {
                            "item_index": 1,
                            "item_type": "custom",
                            "title_snapshot": "夜游成吉思汗广场",
                            "city_snapshot": "呼伦贝尔",
                            "address_snapshot": None,
                            "start_time": None,
                            "end_time": None,
                            "transport_mode": None,
                            "note": "晚上安排",
                        }
                    ],
                },
                {"day_index": 1, "note": "第一天先休整", "items": []},
                {"day_index": 3, "note": None, "items": []},
                {"day_index": 4, "note": None, "items": []},
            ],
        },
    )
    assert fill_resp.status_code == 200
    filled_trip = json.loads(fill_resp.data.decode("utf-8"))["trip"]
    assert filled_trip["item_count"] == 1
    assert filled_trip["trip_days"][1]["items"][0]["title_snapshot"] == "夜游成吉思汗广场"

    clear_resp = client.put(
        f"/api/trips/{trip_id}",
        json={
            "user_id": 1,
            "title": "呼伦贝尔 4 天行程（空草稿）",
            "origin_city": "呼伦贝尔",
            "start_date": "2026-04-10",
            "trip_days": [
                {"day_index": 1, "note": None, "items": []},
                {"day_index": 2, "note": None, "items": []},
                {"day_index": 3, "note": None, "items": []},
                {"day_index": 4, "note": None, "items": []},
            ],
        },
    )
    assert clear_resp.status_code == 200
    cleared_trip = json.loads(clear_resp.data.decode("utf-8"))["trip"]
    assert cleared_trip["item_count"] == 0
    assert all(day["items"] == [] for day in cleared_trip["trip_days"])


def test_trip_detail_serializes_coordinates_for_supported_resource_items(client):
    create_resp = client.post("/api/trips", json=_single_day_trip_payload())
    trip_id = json.loads(create_resp.data.decode("utf-8"))["trip"]["id"]

    update_resp = client.put(
        f"/api/trips/{trip_id}",
        json={
            "user_id": 1,
            "title": "Coordinate Serialization",
            "origin_city": "Hohhot",
            "start_date": "2026-04-10",
            "trip_days": [
                {
                    "day_index": 1,
                    "note": None,
                    "items": [
                        {
                            "item_index": 1,
                            "item_type": "scenic_spot",
                            "ref_id": 1,
                            "title_snapshot": "Scenic Stop",
                        },
                        {
                            "item_index": 2,
                            "item_type": "food_place",
                            "ref_id": 101,
                            "title_snapshot": "Tea Stop",
                        },
                        {
                            "item_index": 3,
                            "item_type": "hotel",
                            "ref_id": 201,
                            "title_snapshot": "Hotel Stop",
                        },
                        {
                            "item_index": 4,
                            "item_type": "custom",
                            "ref_id": None,
                            "title_snapshot": "Custom Stop",
                        },
                        {
                            "item_index": 5,
                            "item_type": "hotel",
                            "ref_id": 9999,
                            "title_snapshot": "Missing Hotel",
                        },
                    ],
                }
            ],
        },
    )
    assert update_resp.status_code == 200
    trip = json.loads(update_resp.data.decode("utf-8"))["trip"]
    items = trip["trip_days"][0]["items"]

    assert items[0]["longitude"] == pytest.approx(111.654)
    assert items[0]["latitude"] == pytest.approx(40.807)
    assert items[1]["longitude"] == pytest.approx(119.775)
    assert items[1]["latitude"] == pytest.approx(49.215)
    assert items[2]["longitude"] == pytest.approx(111.706)
    assert items[2]["latitude"] == pytest.approx(40.812)
    assert items[3]["longitude"] is None
    assert items[3]["latitude"] is None
    assert items[4]["longitude"] is None
    assert items[4]["latitude"] is None


def test_delete_trip_cascades_and_owner_checks_hold_for_multiday(client):
    create_resp = client.post("/api/trips", json=_multi_day_trip_payload())
    trip_id = json.loads(create_resp.data.decode("utf-8"))["trip"]["id"]

    wrong_user_detail = client.get(f"/api/trips/{trip_id}?user_id=2")
    assert wrong_user_detail.status_code == 404
    assert json.loads(wrong_user_detail.data.decode("utf-8"))["error"] == "trip not found"

    wrong_user_delete = client.delete(f"/api/trips/{trip_id}?user_id=2")
    assert wrong_user_delete.status_code == 404
    assert json.loads(wrong_user_delete.data.decode("utf-8"))["error"] == "trip not found"

    delete_resp = client.delete(f"/api/trips/{trip_id}?user_id=1")
    assert delete_resp.status_code == 200
    delete_data = json.loads(delete_resp.data.decode("utf-8"))
    assert delete_data["deleted"] is True

    app = client.application
    with app.app_context():
        assert db.session.get(Trip, trip_id) is None
        assert TripDay.query.count() == 0
        assert TripItem.query.count() == 0
