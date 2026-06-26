from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..db import db
from ..models import User, UserProfile
from ..services.demographics import parse_demographics_payload
from ..services.auth_tokens import enforce_user

profile_bp = Blueprint("profile", __name__, url_prefix="/api/user")

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _demographics_dict(user: User | None) -> dict:
    """从 User 提取可暴露的人口特征字段。"""
    if user is None:
        return {}
    return {
        "gender": (user.gender or "unknown"),
        "age": user.age,
        "home_region": user.home_region,
    }


def _has_any_demographics(demo: dict) -> bool:
    if not demo:
        return False
    if demo.get("home_region"):
        return True
    if demo.get("age") is not None:
        return True
    return (demo.get("gender") or "unknown") in ("male", "female")


@profile_bp.get("/profile/<int:user_id>")
def get_profile(user_id: int):
    """获取指定用户的画像与偏好设置。

    返回字段包括：
      - prefer_scenic_types / prefer_food_types：系统根据评分聚合出的偏好类型
      - travel_style / budget_level：用户手动设置的出行风格和预算等级
      - travel_frequency：评分次数近似的出行频率
      - gender / age / home_region：用户原始人口特征（用于个性化推荐）
    """

    profile = UserProfile.query.filter_by(user_id=user_id).first()
    user = db.session.get(User, user_id)
    demographics = _demographics_dict(user)

    if profile is None and not _has_any_demographics(demographics):
        return jsonify({"profile": None})

    payload = profile.to_dict() if profile is not None else {"user_id": user_id}
    payload.update(demographics)
    return jsonify({"profile": payload})


@profile_bp.post("/profile")
def upsert_profile():
    """创建或更新用户画像中的手动偏好设置。

    请求 JSON 示例：
    {
      "user_id": 1,
      "travel_style": "relax",   # 可选：出行风格
      "budget_level": 2,          # 可选：预算等级，1=节省，2=适中，3=高档
      "prefer_scenic_types": ["草原", "森林"],   # 可选：显式偏好景点类型
      "prefer_food_types": "烧烤,牛肉"          # 可选：显式偏好美食类型
    }
    """

    data = request.get_json(silent=True) or {}
    user_id_raw = data.get("user_id")
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "valid user_id is required"}), 400

    auth_error = enforce_user(user_id)
    if auth_error is not None:
        return auth_error

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "user not found"}), 400

    # 可选人口特征（性别/年龄/地域），写入 User 记录
    gender, age, home_region, demo_error = parse_demographics_payload(data)
    if demo_error is not None:
        return jsonify({"error": demo_error}), 400
    if "gender" in data:
        user.gender = gender or "unknown"
    if "age" in data:
        user.age = age
    if "home_region" in data:
        user.home_region = home_region

    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.session.add(profile)

    if "travel_style" in data:
        travel_style_raw = data.get("travel_style")
        if travel_style_raw is None or travel_style_raw == "":
            profile.travel_style = None
        else:
            profile.travel_style = str(travel_style_raw).strip() or None

    if "budget_level" in data:
        budget_raw = data.get("budget_level")
        if budget_raw is None or budget_raw == "":
            profile.budget_level = None
        else:
            try:
                budget_level = int(budget_raw)
            except (TypeError, ValueError):
                return jsonify({"error": "budget_level must be an integer"}), 400
            if budget_level not in (1, 2, 3):
                return jsonify({"error": "budget_level must be 1, 2, or 3"}), 400
            profile.budget_level = budget_level

    def _normalize_types(value):
        if value is None:
            return None
        if isinstance(value, list):
            joined = ",".join(str(v).strip() for v in value if str(v).strip())
            return joined or None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        cleaned = str(value).strip()
        return cleaned or None

    if "prefer_scenic_types" in data:
        profile.prefer_scenic_types = _normalize_types(data.get("prefer_scenic_types"))

    if "prefer_food_types" in data:
        profile.prefer_food_types = _normalize_types(data.get("prefer_food_types"))

    profile.updated_at = _utcnow()
    db.session.commit()

    payload = profile.to_dict()
    payload.update(_demographics_dict(user))
    return jsonify({"profile": payload})
