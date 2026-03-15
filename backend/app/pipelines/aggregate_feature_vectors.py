from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict

from .. import create_app
from ..db import db
from ..models import (
    ContentStandard,
    FoodPlace,
    Hotel,
    Rating,
    ScenicSpot,
    User,
    UserProfile,
)


def _safe_parse_summary(summary: str) -> Dict[str, Any]:
    """将 ContentStandard.summary 安全解析为 dict。

    兼容 JSON 字符串和 Python dict 的 str 表达形式（单引号）。
    解析失败时返回空 dict。
    """

    if not summary:
        return {}
    try:
        return json.loads(summary)
    except Exception:
        try:
            return json.loads(summary.replace("'", '"'))
        except Exception:
            return {}


def _bucket_age(age: int | None) -> str:
    if age is None or age <= 0:
        return "unknown"
    if age < 18:
        return "<18"
    if age < 26:
        return "18-25"
    if age < 36:
        return "26-35"
    if age < 46:
        return "36-45"
    if age < 61:
        return "46-60"
    return ">60"


def _aggregate_user_features() -> None:
    """聚合用户侧特征，写入 UserProfile.feature_vector。

    特征示例结构：
      {
        "gender": "male",
        "age_bucket": "18-25",
        "home_region": "内蒙古",
        "register_source": "web",
        "rating_total": 12,
        "rating_avg": 4.6,
        "rating_by_type": {"scenic_spot": 8, "hotel": 3, "food_place": 1},
        "last_rating_days_ago": 5,
        "prefer_scenic_types": ["草原风光", "自然风光"],
        "prefer_food_types": ["烧烤", "蒙餐"],
        "travel_style": "轻松休闲",
        "budget_level": 3,
        "travel_frequency": 10
      }
    """

    now = datetime.now(timezone.utc)

    # 预加载用户评分，减少 N+1 查询
    ratings_by_user: Dict[int, list[Rating]] = defaultdict(list)
    for r in Rating.query.all():
        ratings_by_user[r.user_id].append(r)

    users = User.query.all()

    for user in users:
        ratings = ratings_by_user.get(user.id, [])

        rating_total = len(ratings)
        score_sum = 0
        rating_type_counter: Counter[str] = Counter()
        last_rating_at: datetime | None = None

        for r in ratings:
            rating_type_counter[r.target_type] += 1
            try:
                score_sum += int(r.score or 0)
            except (TypeError, ValueError):
                continue
            if last_rating_at is None or (r.created_at and r.created_at > last_rating_at):
                last_rating_at = r.created_at

        rating_avg = float(score_sum) / rating_total if rating_total > 0 else 0.0
        if last_rating_at is not None:
            delta_days = (now - last_rating_at).days
        else:
            delta_days = None

        profile = UserProfile.query.filter_by(user_id=user.id).first()
        if profile is None:
            # 没有评分、没有画像的用户不强制创建画像
            if rating_total == 0:
                continue
            profile = UserProfile(user_id=user.id)
            db.session.add(profile)

        # 解析已有画像字段
        scenic_types = [
            t.strip()
            for t in (profile.prefer_scenic_types or "").split(",")
            if t.strip()
        ]
        food_types = [
            t.strip()
            for t in (profile.prefer_food_types or "").split(",")
            if t.strip()
        ]

        feature = {
            "gender": user.gender,
            "age_bucket": _bucket_age(user.age),
            "home_region": user.home_region,
            "register_source": user.register_source,
            "rating_total": rating_total,
            "rating_avg": round(rating_avg, 4) if rating_total > 0 else None,
            "rating_by_type": dict(rating_type_counter),
            "last_rating_days_ago": delta_days,
            "prefer_scenic_types": scenic_types,
            "prefer_food_types": food_types,
            "travel_style": profile.travel_style,
            "budget_level": profile.budget_level,
            "travel_frequency": profile.travel_frequency,
        }

        profile.feature_vector = json.dumps(feature, ensure_ascii=False)
        profile.updated_at = now


def _load_multi_source_for_entities(entity_type: str) -> Dict[int, Dict[str, Any]]:
    """加载某一实体类型的 internal/OTA/social_media 聚合信息。

    返回结构：entity_id -> {internal_popularity, ota_rating, ota_review_count,
                          social_interactions, social_sentiment}
    """

    rows = (
        ContentStandard.query.filter(
            ContentStandard.entity_type == entity_type,
            ContentStandard.source_type.in_(
                ["internal_rating", "ota_stats", "social_media"]
            ),
        ).all()
    )

    data: Dict[int, Dict[str, Any]] = {}
    for row in rows:
        state = data.setdefault(row.entity_id, {})
        if row.source_type == "internal_rating":
            try:
                state["internal_popularity"] = float(row.popularity_score)
            except (TypeError, ValueError):
                continue
        elif row.source_type == "ota_stats":
            payload = _safe_parse_summary(row.summary)
            try:
                state["ota_rating"] = float(payload.get("external_rating", 0) or 0)
            except (TypeError, ValueError):
                pass
            try:
                state["ota_review_count"] = int(payload.get("review_count", 0) or 0)
            except (TypeError, ValueError):
                pass
        elif row.source_type == "social_media":
            payload = _safe_parse_summary(row.summary)
            try:
                state["social_interactions"] = int(
                    payload.get("interaction_sum", 0) or 0
                )
            except (TypeError, ValueError):
                pass
            try:
                state["social_sentiment"] = float(
                    payload.get("sentiment_avg", 0.0) or 0.0
                )
            except (TypeError, ValueError):
                pass

    return data


def _build_item_feature_for_scenic() -> None:
    multi = _load_multi_source_for_entities("scenic_spot")
    spots = ScenicSpot.query.all()
    now = datetime.now(timezone.utc)

    for spot in spots:
        state = multi.get(spot.id, {})
        try:
            rating_avg = float(spot.rating_avg) if spot.rating_avg is not None else None
        except (TypeError, ValueError):
            rating_avg = None
        try:
            rating_count = int(spot.rating_count or 0)
        except (TypeError, ValueError):
            rating_count = 0

        feature = {
            "entity_type": "scenic_spot",
            "id": spot.id,
            "city": spot.city,
            "category": spot.category,
            "ticket_price": float(spot.ticket_price)
            if spot.ticket_price is not None
            else None,
            "rating_avg": rating_avg,
            "rating_count": rating_count,
            "internal_popularity": state.get("internal_popularity"),
            "ota_rating": state.get("ota_rating"),
            "ota_review_count": state.get("ota_review_count"),
            "social_interactions": state.get("social_interactions"),
            "social_sentiment": state.get("social_sentiment"),
        }

        row = ContentStandard.query.filter_by(
            entity_type="scenic_spot",
            entity_id=spot.id,
            source_type="feature_vector",
        ).first()
        if row is None:
            row = ContentStandard(
                entity_type="scenic_spot",
                entity_id=spot.id,
                source_type="feature_vector",
            )
            db.session.add(row)

        row.title = "ml_feature_vector"
        row.summary = json.dumps(feature, ensure_ascii=False)
        row.last_update = now


def _build_item_feature_for_hotels() -> None:
    multi = _load_multi_source_for_entities("hotel")
    hotels = Hotel.query.all()
    now = datetime.now(timezone.utc)

    for hotel in hotels:
        state = multi.get(hotel.id, {})
        try:
            rating_avg = float(hotel.rating_avg) if hotel.rating_avg is not None else None
        except (TypeError, ValueError):
            rating_avg = None
        try:
            rating_count = int(hotel.rating_count or 0)
        except (TypeError, ValueError):
            rating_count = 0

        feature = {
            "entity_type": "hotel",
            "id": hotel.id,
            "city": hotel.city,
            "star_level": hotel.star_level,
            "avg_price": float(hotel.avg_price)
            if hotel.avg_price is not None
            else None,
            "rating_avg": rating_avg,
            "rating_count": rating_count,
            "internal_popularity": state.get("internal_popularity"),
            "ota_rating": state.get("ota_rating"),
            "ota_review_count": state.get("ota_review_count"),
            "social_interactions": state.get("social_interactions"),
            "social_sentiment": state.get("social_sentiment"),
        }

        row = ContentStandard.query.filter_by(
            entity_type="hotel",
            entity_id=hotel.id,
            source_type="feature_vector",
        ).first()
        if row is None:
            row = ContentStandard(
                entity_type="hotel",
                entity_id=hotel.id,
                source_type="feature_vector",
            )
            db.session.add(row)

        row.title = "ml_feature_vector"
        row.summary = json.dumps(feature, ensure_ascii=False)
        row.last_update = now


def _build_item_feature_for_foods() -> None:
    multi = _load_multi_source_for_entities("food_place")
    foods = FoodPlace.query.all()
    now = datetime.now(timezone.utc)

    for food in foods:
        state = multi.get(food.id, {})
        try:
            rating_avg = float(food.rating_avg) if food.rating_avg is not None else None
        except (TypeError, ValueError):
            rating_avg = None
        try:
            rating_count = int(food.rating_count or 0)
        except (TypeError, ValueError):
            rating_count = 0

        feature = {
            "entity_type": "food_place",
            "id": food.id,
            "city": food.city,
            "cuisine_type": food.cuisine_type,
            "avg_price": float(food.avg_price)
            if food.avg_price is not None
            else None,
            "rating_avg": rating_avg,
            "rating_count": rating_count,
            "internal_popularity": state.get("internal_popularity"),
            "ota_rating": state.get("ota_rating"),
            "ota_review_count": state.get("ota_review_count"),
            "social_interactions": state.get("social_interactions"),
            "social_sentiment": state.get("social_sentiment"),
        }

        row = ContentStandard.query.filter_by(
            entity_type="food_place",
            entity_id=food.id,
            source_type="feature_vector",
        ).first()
        if row is None:
            row = ContentStandard(
                entity_type="food_place",
                entity_id=food.id,
                source_type="feature_vector",
            )
            db.session.add(row)

        row.title = "ml_feature_vector"
        row.summary = json.dumps(feature, ensure_ascii=False)
        row.last_update = now


def aggregate_all() -> None:
    """统一入口：聚合用户特征与内容特征。"""

    _aggregate_user_features()
    _build_item_feature_for_scenic()
    _build_item_feature_for_hotels()
    _build_item_feature_for_foods()
    db.session.commit()


def main() -> None:
    app = create_app()
    with app.app_context():
        aggregate_all()


if __name__ == "__main__":
    main()
