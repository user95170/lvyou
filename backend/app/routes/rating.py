from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..db import db
from ..models import Rating, ScenicSpot, Hotel, FoodPlace, User

rating_bp = Blueprint("rating", __name__, url_prefix="/api/ratings")

TARGET_MODELS = {
    "scenic_spot": ScenicSpot,
    "hotel": Hotel,
    "food_place": FoodPlace,
}


@rating_bp.post("")
def create_rating():
    """提交评分评价。

    请求 JSON 示例：
    {
      "user_id": 1,
      "target_type": "scenic_spot",   # scenic_spot/hotel/food_place
      "target_id": 3,
      "score": 5,
      "comment": "很不错的草原体验"
    }
    """

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    target_type = (data.get("target_type") or "").strip()
    target_id = data.get("target_id")
    score = data.get("score")
    comment = (data.get("comment") or None) or None

    if user_id is None or not target_type or target_id is None or score is None:
        return jsonify({"error": "user_id, target_type, target_id and score are required"}), 400

    try:
        user_id = int(user_id)
        target_id = int(target_id)
        score = int(score)
    except (TypeError, ValueError):
        return jsonify({"error": "user_id, target_id and score must be integers"}), 400

    if score < 1 or score > 5:
        return jsonify({"error": "score must be between 1 and 5"}), 400

    target_model = TARGET_MODELS.get(target_type)
    if target_model is None:
        return jsonify({"error": "unsupported target_type"}), 400

    # 简单校验用户是否存在
    if db.session.get(User, user_id) is None:
        return jsonify({"error": "user not found"}), 400

    obj = db.session.get(target_model, target_id)
    if obj is None:
        return jsonify({"error": "target not found"}), 400

    rating = Rating(
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        score=score,
        comment=comment,
    )

    db.session.add(rating)
    db.session.flush()  # 确保本次评分参与后续聚合

    # 聚合更新目标对象的平均分和评分次数
    avg_score, count = db.session.query(
        func.avg(Rating.score), func.count(Rating.id)
    ).filter(
        Rating.target_type == target_type,
        Rating.target_id == target_id,
    ).first()

    avg_score = float(avg_score) if avg_score is not None else None
    count = int(count or 0)

    obj.rating_avg = avg_score
    obj.rating_count = count

    db.session.commit()

    return jsonify(
        {
            "rating": rating.to_dict(),
            "aggregate": {
                "rating_avg": avg_score,
                "rating_count": count,
            },
        }
    ), 201
