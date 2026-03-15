from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..db import db
from ..models import User, UserProfile

profile_bp = Blueprint("profile", __name__, url_prefix="/api/user")

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@profile_bp.get("/profile/<int:user_id>")
def get_profile(user_id: int):
    """获取指定用户的画像与偏好设置。

    返回字段包括：
      - prefer_scenic_types / prefer_food_types：系统根据评分聚合出的偏好类型
      - travel_style / budget_level：用户手动设置的出行风格和预算等级
      - travel_frequency：评分次数近似的出行频率
    """

    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if profile is None:
        return jsonify({"profile": None})
    return jsonify({"profile": profile.to_dict()})


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

    if db.session.get(User, user_id) is None:
        return jsonify({"error": "user not found"}), 400

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

    return jsonify({"profile": profile.to_dict()})
