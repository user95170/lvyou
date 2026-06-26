from __future__ import annotations

from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import and_

from ..models import (
    ScenicSpot,
    Hotel,
    FoodPlace,
    User,
    UserProfile,
    Transportation,
    Activity,
    Specialty,
)

map_bp = Blueprint("map", __name__, url_prefix="/api/map")


def _parse_bounds(bounds: dict | None):
    if not isinstance(bounds, dict):
        return None
    try:
        min_lng = float(bounds.get("min_lng"))
        min_lat = float(bounds.get("min_lat"))
        max_lng = float(bounds.get("max_lng"))
        max_lat = float(bounds.get("max_lat"))
        return (min_lng, min_lat, max_lng, max_lat)
    except Exception:
        return None


def _query_entities(model, city: str | None, bounds, limit: int):
    q = model.query
    if city:
        q = q.filter(model.city.like(f"%{city}%"))
    if bounds is not None and hasattr(model, "longitude") and hasattr(model, "latitude"):
        min_lng, min_lat, max_lng, max_lat = bounds
        q = q.filter(
            and_(
                model.longitude >= min_lng,
                model.longitude <= max_lng,
                model.latitude >= min_lat,
                model.latitude <= max_lat,
            )
        )
    # 粗略排序：评分均分/评分数
    if hasattr(model, "rating_avg") and hasattr(model, "rating_count"):
        q = q.order_by(model.rating_avg.desc(), model.rating_count.desc(), model.id.desc())
    else:
        q = q.order_by(model.id.desc())
    return q.limit(limit).all()


@map_bp.post("/personalized")
def personalized_map():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    city = (data.get("city") or "").strip() or None
    bounds = _parse_bounds(data.get("bounds"))
    categories = data.get("categories") or [
        "scenic_spot",
        "food_place",
        "hotel",
        "transportation",
        "activity",
        "specialty",
    ]
    limit_per_type = int(data.get("limit_per_type") or 20)

    result = {
        "scenic_spot": [],
        "food_place": [],
        "hotel": [],
        "transportation": [],
        "activity": [],
        "specialty": [],
    }

    _SIMPLE_TYPES = {
        "transportation": Transportation,
        "activity": Activity,
        "specialty": Specialty,
    }

    def _parse_list(s):
        if not s:
            return []
        if isinstance(s, list):
            return [str(x).strip() for x in s if str(x).strip()]
        return [t for t in str(s).split(",") if t.strip()]

    def _load_profile(uid: int | None):
        if not uid:
            return {}
        u = User.query.filter_by(id=uid).first()
        p = UserProfile.query.filter_by(user_id=uid).first()
        out = {}
        if u is not None:
            out["gender"] = (u.gender or "unknown").lower()
            try:
                out["age"] = int(u.age) if u.age is not None else None
            except Exception:
                out["age"] = None
            out["home_region"] = (u.home_region or "").strip() or None
        if p is not None:
            out["prefer_scenic_types"] = _parse_list(p.prefer_scenic_types)
            out["prefer_food_types"] = _parse_list(p.prefer_food_types)
            out["budget_level"] = p.budget_level
            out["travel_style"] = (p.travel_style or "").strip() or None
        return out

    profile = _load_profile(int(user_id)) if user_id is not None else {}

    def _age_group(age: int | None) -> str:
        if age is None:
            return "unknown"
        if age < 18:
            return "teen"
        if age < 30:
            return "young"
        if age < 50:
            return "adult"
        return "senior"

    def _score_scenic(s: ScenicSpot) -> float:
        base = 0.0
        try:
            if s.rating_avg is not None:
                base += float(s.rating_avg) / 5.0
        except Exception:
            pass
        try:
            rc = int(s.rating_count or 0)
            if rc >= 200:
                base += 0.1
            elif rc >= 50:
                base += 0.05
        except Exception:
            pass
        boost = 0.0
        pref = set(profile.get("prefer_scenic_types", []))
        if s.category and s.category in pref:
            boost += 0.3
        if s.tags:
            for t in pref:
                if t and t in s.tags:
                    boost += 0.1
                    break
        hr = profile.get("home_region")
        if hr and s.city and hr == s.city:
            boost -= 0.05
        g = (profile.get("gender") or "unknown").lower()
        ag = _age_group(profile.get("age"))
        if ag == "senior" and s.category and ("博物馆" in s.category or "公园" in s.category):
            boost += 0.05
        if ag == "young" and s.category and ("购物" in s.category or "娱乐" in s.category):
            boost += 0.05
        return base + boost

    def _score_food(f: FoodPlace) -> float:
        base = 0.0
        try:
            if f.rating_avg is not None:
                base += float(f.rating_avg) / 5.0
        except Exception:
            pass
        pref = set(profile.get("prefer_food_types", []))
        boost = 0.0
        if f.cuisine_type:
            for t in pref:
                if t and t in f.cuisine_type:
                    boost += 0.25
                    break
        hr = profile.get("home_region")
        if hr and f.city and hr == f.city:
            boost -= 0.03
        return base + boost

    def _score_hotel(h: Hotel) -> float:
        base = 0.0
        try:
            if h.rating_avg is not None:
                base += float(h.rating_avg) / 5.0
        except Exception:
            pass
        boost = 0.0
        bl = profile.get("budget_level")
        try:
            if bl is not None and h.avg_price is not None:
                price = float(h.avg_price)
                if bl == 1 and price <= 300:
                    boost += 0.1
                if bl == 2 and 200 <= price <= 700:
                    boost += 0.1
                if bl == 3 and price >= 600:
                    boost += 0.1
        except Exception:
            pass
        return base + boost

    for cat in categories:
        if cat == "scenic_spot":
            items = _query_entities(ScenicSpot, city, bounds, limit_per_type * 3)
            if profile:
                items = sorted(items, key=_score_scenic, reverse=True)[:limit_per_type]
            else:
                items = items[:limit_per_type]
            result["scenic_spot"] = [
                {
                    "id": s.id,
                    "name": s.name,
                    "city": s.city,
                    "longitude": float(s.longitude) if s.longitude is not None else None,
                    "latitude": float(s.latitude) if s.latitude is not None else None,
                    "fit_reasons": _fit_reasons_for_scenic(s),
                }
                for s in items
            ]
        elif cat == "food_place":
            items = _query_entities(FoodPlace, city, bounds, limit_per_type * 3)
            if profile:
                items = sorted(items, key=_score_food, reverse=True)[:limit_per_type]
            else:
                items = items[:limit_per_type]
            result["food_place"] = [
                {
                    "id": f.id,
                    "name": f.name,
                    "city": f.city,
                    "longitude": float(f.longitude) if f.longitude is not None else None,
                    "latitude": float(f.latitude) if f.latitude is not None else None,
                    "fit_reasons": _fit_reasons_for_food(f),
                }
                for f in items
            ]
        elif cat == "hotel":
            items = _query_entities(Hotel, city, bounds, limit_per_type * 3)
            if profile:
                items = sorted(items, key=_score_hotel, reverse=True)[:limit_per_type]
            else:
                items = items[:limit_per_type]
            result["hotel"] = [
                {
                    "id": h.id,
                    "name": h.name,
                    "city": h.city,
                    "longitude": float(h.longitude) if h.longitude is not None else None,
                    "latitude": float(h.latitude) if h.latitude is not None else None,
                    "fit_reasons": _fit_reasons_for_hotel(h),
                }
                for h in items
            ]
        elif cat in _SIMPLE_TYPES:
            model = _SIMPLE_TYPES[cat]
            items = _query_entities(model, city, bounds, limit_per_type)
            result[cat] = [
                {
                    "id": obj.id,
                    "name": obj.name,
                    "city": obj.city,
                    "longitude": float(obj.longitude) if obj.longitude is not None else None,
                    "latitude": float(obj.latitude) if obj.latitude is not None else None,
                }
                for obj in items
            ]

    return jsonify({"items": result, "meta": {"strategy": "multi_source+profile-demographic", "city": city, "profile_used": bool(profile)}})


def _fit_reasons_for_scenic(s: ScenicSpot) -> list[str]:
    reasons: list[str] = []
    try:
        if (s.rating_avg is not None and float(s.rating_avg) >= 4.5) and int(s.rating_count or 0) >= 50:
            reasons.append("本站评分较高")
    except Exception:
        pass
    if s.category:
        reasons.append(f"类型：{s.category}")
    return reasons


def _fit_reasons_for_food(f: FoodPlace) -> list[str]:
    reasons: list[str] = []
    if f.cuisine_type:
        reasons.append(f"菜系：{f.cuisine_type}")
    try:
        if (f.rating_avg is not None and float(f.rating_avg) >= 4.5) and int(f.rating_count or 0) >= 50:
            reasons.append("口碑较好")
    except Exception:
        pass
    return reasons


def _fit_reasons_for_hotel(h: Hotel) -> list[str]:
    reasons: list[str] = []
    if h.star_level:
        reasons.append(f"档次：{h.star_level}")
    try:
        if h.avg_price is not None:
            reasons.append("价格：有参考价")
    except Exception:
        pass
    return reasons
