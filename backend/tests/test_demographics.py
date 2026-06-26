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
from app.models import FoodPlace, ScenicSpot, User
from app.routes import register_routes
from app.services.demographics import (
    age_group,
    food_demographic_adjustment,
    region_taste_tags,
    scenic_demographic_adjustment,
)
from app.routes.recommend import _apply_demo_rerank


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
                    name="安静博物馆",
                    city="呼和浩特",
                    category="博物馆",
                    tags="文化;历史",
                    rating_avg=4.4,
                    rating_count=80,
                ),
                ScenicSpot(
                    id=2,
                    name="热闹乐园",
                    city="呼和浩特",
                    category="娱乐",
                    tags="夜;网红",
                    rating_avg=4.4,
                    rating_count=80,
                ),
                FoodPlace(
                    id=1,
                    name="辣味湘菜馆",
                    city="呼和浩特",
                    cuisine_type="湘菜",
                    tags="辣;香辣",
                    rating_avg=4.3,
                    rating_count=40,
                ),
                FoodPlace(
                    id=2,
                    name="清淡养生粥铺",
                    city="呼和浩特",
                    cuisine_type="养生",
                    tags="清淡;粥",
                    rating_avg=4.3,
                    rating_count=40,
                ),
            ]
        )
        db.session.commit()

    with app.test_client() as test_client:
        yield test_client


def _register(client, username, **demo):
    payload = {"username": username, "password": "123456"}
    payload.update(demo)
    resp = client.post("/api/auth/register", json=payload)
    return resp


# ---------- 纯函数单元测试 ----------

def test_age_group_buckets():
    assert age_group(None) == "unknown"
    assert age_group(15) == "teen"
    assert age_group(25) == "young"
    assert age_group(40) == "adult"
    assert age_group(65) == "senior"


def test_region_taste_tags_hunan():
    tastes, reason = region_taste_tags("湖南")
    assert "辣" in tastes
    assert reason and "偏辣" in reason
    assert region_taste_tags(None) == ([], None)


def test_scenic_adjustment_senior_quiet_vs_lively():
    class Spot:
        def __init__(self, category, tags=""):
            self.category = category
            self.tags = tags

    demo_senior = {"age_group": "senior", "gender": "female", "home_region": None}
    quiet_delta, quiet_reasons = scenic_demographic_adjustment(Spot("博物馆"), demo_senior)
    lively_delta, _ = scenic_demographic_adjustment(Spot("娱乐", "夜"), demo_senior)
    assert quiet_delta > lively_delta
    assert any("安静" in r for r in quiet_reasons)


class _FakeSpot:
    def __init__(self, sid, category, tags=""):
        self.id = sid
        self.category = category
        self.tags = tags


def test_apply_demo_rerank_floats_senior_fit_up():
    demo = {"age_group": "senior", "gender": "female", "home_region": None}
    # 10 个中性点位，索引1处放一个适配长者的博物馆（紧邻索引0的中性项）
    spots = [_FakeSpot(i, "温泉") for i in range(10)]
    spots[1] = _FakeSpot(101, "博物馆", "文化")
    out = _apply_demo_rerank(spots, demo)
    assert out[0].id == 101  # 博物馆上浮到首位


def test_apply_demo_rerank_no_demo_preserves_order():
    spots = [_FakeSpot(1, "娱乐"), _FakeSpot(2, "博物馆")]
    assert [s.id for s in _apply_demo_rerank(spots, None)] == [1, 2]


def test_food_adjustment_home_region_taste():
    class Food:
        def __init__(self, cuisine, tags=""):
            self.cuisine_type = cuisine
            self.tags = tags

    demo = {"age_group": "adult", "gender": "male", "home_region": "湖南"}
    spicy_delta, spicy_reasons = food_demographic_adjustment(Food("湘菜", "辣"), demo)
    plain_delta, _ = food_demographic_adjustment(Food("养生", "清淡"), demo)
    assert spicy_delta > plain_delta
    assert any("家乡口味" in r for r in spicy_reasons)


# ---------- 接口集成测试 ----------

def test_register_persists_demographics(client):
    resp = _register(client, "demo_user", gender="female", age=65, home_region="湖南")
    assert resp.status_code == 201
    data = json.loads(resp.data.decode("utf-8"))
    assert data["gender"] == "female"
    assert data["age"] == 65
    assert data["home_region"] == "湖南"

    uid = data["id"]
    resp2 = client.get(f"/api/user/profile/{uid}")
    assert resp2.status_code == 200
    profile = json.loads(resp2.data.decode("utf-8"))["profile"]
    assert profile["gender"] == "female"
    assert profile["age"] == 65
    assert profile["home_region"] == "湖南"


def test_register_rejects_invalid_demographics(client):
    resp = _register(client, "bad_gender", gender="X")
    assert resp.status_code == 400
    resp2 = _register(client, "bad_age", age="old")
    assert resp2.status_code == 400


def test_profile_post_updates_demographics(client):
    reg = _register(client, "p_user")
    uid = json.loads(reg.data.decode("utf-8"))["id"]

    resp = client.post(
        "/api/user/profile",
        json={"user_id": uid, "gender": "male", "age": 28, "home_region": "四川"},
    )
    assert resp.status_code == 200
    profile = json.loads(resp.data.decode("utf-8"))["profile"]
    assert profile["gender"] == "male"
    assert profile["age"] == 28
    assert profile["home_region"] == "四川"


def test_food_recommend_includes_home_region_reason(client):
    reg = _register(client, "hunan_user", home_region="湖南", age=30)
    uid = json.loads(reg.data.decode("utf-8"))["id"]

    resp = client.get(f"/api/recommend/foods?user_id={uid}&limit=10")
    assert resp.status_code == 200
    items = json.loads(resp.data.decode("utf-8"))["items"]
    spicy = next(item for item in items if item["id"] == 1)
    assert any("家乡口味" in r for r in spicy.get("reasons", []))


def test_personalized_map_includes_demographic_fit_reason(client):
    reg = _register(client, "map_senior", age=66, gender="female")
    uid = json.loads(reg.data.decode("utf-8"))["id"]

    resp = client.post(
        "/api/map/personalized",
        json={"user_id": uid, "categories": ["scenic_spot"], "limit_per_type": 10},
    )
    assert resp.status_code == 200
    body = json.loads(resp.data.decode("utf-8"))
    assert body["meta"]["profile_used"] is True
    museum = next(s for s in body["items"]["scenic_spot"] if s["id"] == 1)
    assert any("安静" in r for r in museum.get("fit_reasons", []))


def test_scenic_recommend_includes_senior_reason(client):
    reg = _register(client, "senior_user", age=66, gender="female")
    uid = json.loads(reg.data.decode("utf-8"))["id"]

    resp = client.get(f"/api/recommend/scenic-spots?user_id={uid}&limit=10")
    assert resp.status_code == 200
    items = json.loads(resp.data.decode("utf-8"))["items"]
    museum = next(item for item in items if item["id"] == 1)
    assert any("安静" in r for r in museum.get("reasons", []))
