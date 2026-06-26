from __future__ import annotations

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from math import radians, sin, cos, sqrt, atan2

from ..models import ScenicSpot, FoodPlace, Hotel

itinerary_bp = Blueprint("itinerary", __name__, url_prefix="/api/itineraries")


def _time_str(h: int, m: int) -> str:
    return f"{h:02d}:{m:02d}"


def _alloc_times(n: int) -> List[tuple[str, str]]:
    # 简单时间片：上午两段 + 下午两段，超出则均分
    slots = [
        (9, 30, 11, 30),
        (12, 0, 13, 0),
        (14, 0, 16, 0),
        (19, 0, 20, 0),
    ]
    if n <= len(slots):
        return [(_time_str(a, b), _time_str(c, d)) for a, b, c, d in slots[:n]]
    # 超出时段，均分 9:30-20:00 区间
    start = datetime(2000, 1, 1, 9, 30)
    end = datetime(2000, 1, 1, 20, 0)
    total = (end - start).total_seconds()
    step = int(total // n)
    out = []
    for i in range(n):
        s = start + timedelta(seconds=i * step)
        e = start + timedelta(seconds=(i + 1) * step)
        out.append((_time_str(s.hour, s.minute), _time_str(e.hour, e.minute)))
    return out


def _fetch_by_ids(model, ids: List[int]):
    if not ids:
        return []
    rows = model.query.filter(model.id.in_(ids)).all()
    id2 = {r.id: r for r in rows}
    return [id2[i] for i in ids if i in id2]


def _haversine_km(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    r = 6371.0
    lon1, lat1_r = radians(lng1), radians(lat1)
    lon2, lat2_r = radians(lng2), radians(lat2)
    dlon = lon2 - lon1
    dlat = lat2_r - lat1_r
    a = sin(dlat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def _parse_list(s):
    if not s:
        return []
    if isinstance(s, list):
        return [str(x).strip() for x in s if str(x).strip()]
    return [t for t in str(s).split(",") if t.strip()]


def _load_profile(uid: int | None):
    from ..models import User, UserProfile  # local import to avoid cycles
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


def _score_scenic(s: ScenicSpot, profile: dict) -> float:
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
    ag = _age_group(profile.get("age"))
    if ag == "senior" and s.category and ("博物馆" in s.category or "公园" in s.category):
        boost += 0.05
    if ag == "young" and s.category and ("购物" in s.category or "娱乐" in s.category):
        boost += 0.05
    return base + boost


def _score_food(f: FoodPlace, profile: dict) -> float:
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


def _obj_coords(obj):
    try:
        lng = float(getattr(obj, "longitude")) if getattr(obj, "longitude") is not None else None
        lat = float(getattr(obj, "latitude")) if getattr(obj, "latitude") is not None else None
        if lng is None or lat is None:
            return None
        return (lng, lat)
    except Exception:
        return None


def _order_by_nearest(objs: List[tuple[str, object]]) -> List[tuple[str, object]]:
    with_coords = [(t, o, _obj_coords(o)) for t, o in objs]
    start_idx = 0
    for i, (_, _, c) in enumerate(with_coords):
        if c is not None:
            start_idx = i
            break
    ordered = []
    if not with_coords:
        return ordered
    current = with_coords.pop(start_idx)
    ordered.append((current[0], current[1]))
    while with_coords:
        _, _, c0 = current
        best_j = 0
        best_d = None
        for j, (tj, oj, cj) in enumerate(with_coords):
            if c0 is None or cj is None:
                d = float('inf')
            else:
                d = _haversine_km(c0[0], c0[1], cj[0], cj[1])
            if best_d is None or d < best_d:
                best_d = d
                best_j = j
        current = with_coords.pop(best_j)
        ordered.append((current[0], current[1]))
    return ordered


@itinerary_bp.post("/suggest")
def suggest_itinerary():
    data = request.get_json(silent=True) or {}
    city = (data.get("city") or "").strip() or None
    user_id_raw = data.get("user_id")
    user_id: Optional[int] = None
    if user_id_raw is not None and str(user_id_raw).strip() != "":
        try:
            user_id = int(user_id_raw)
        except Exception:
            return jsonify({"error": "user_id 必须为整数"}), 400

    days_raw = data.get("days")
    if days_raw is None or days_raw == "":
        days = 2
    else:
        try:
            days = int(days_raw)
        except Exception:
            return jsonify({"error": "days 必须为整数"}), 400
    if days < 1:
        days = 1
    if days > 10:
        days = 10

    candidates_raw = data.get("candidates")
    candidates: Dict[str, Any] = {}
    if candidates_raw is None:
        candidates = {}
    elif isinstance(candidates_raw, dict):
        candidates = candidates_raw
    else:
        return jsonify({"error": "candidates 必须为对象"}), 400

    def _normalize_id_list(value) -> List[int]:
        if value is None:
            return []
        parts: Any = value
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
        elif not isinstance(value, list):
            parts = [value]
        out: List[int] = []
        for x in parts:
            if x is None or x == "":
                continue
            try:
                out.append(int(x))
            except Exception:
                continue
        return out

    scenic_ids = _normalize_id_list(candidates.get("scenic_spot"))
    food_ids = _normalize_id_list(candidates.get("food_place"))
    hotel_ids = _normalize_id_list(candidates.get("hotel"))

    scenics = _fetch_by_ids(ScenicSpot, scenic_ids)
    foods = _fetch_by_ids(FoodPlace, food_ids)
    hotels = _fetch_by_ids(Hotel, hotel_ids)

    # 若未提供候选，则按城市 TopN 作为候选（保障可用性）
    def _top_q(model, limit: int):
        q = model.query
        if city:
            q = q.filter(model.city.like(f"%{city}%"))
        if hasattr(model, "rating_avg") and hasattr(model, "rating_count"):
            q = q.order_by(model.rating_avg.desc(), model.rating_count.desc(), model.id.desc())
        else:
            q = q.order_by(model.id.desc())
        return q.limit(limit).all()

    if not scenics:
        scenics = _top_q(ScenicSpot, 36)
    if not foods:
        foods = _top_q(FoodPlace, 18)

    if not scenics and not foods:
        return jsonify({"error": "当前暂无可用内容，无法生成行程"}), 400

    profile = _load_profile(int(user_id)) if user_id is not None else {}
    if profile:
        try:
            scenics = sorted(scenics, key=lambda s: _score_scenic(s, profile), reverse=True)
        except Exception:
            pass
        try:
            foods = sorted(foods, key=lambda f: _score_food(f, profile), reverse=True)
        except Exception:
            pass

    # 简单分配：每天 2-3 个景点 + 1 顿饭
    per_day_scenic = 0
    if scenics:
        per_day_scenic = max(1, min(3, max(len(scenics) // max(days, 1), 2)))
    per_day_food = 1 if foods else 0

    days_out: List[Dict] = []
    si = 0
    fi = 0
    for d in range(1, days + 1):
        day_items = []
        scenic_today = scenics[si : si + per_day_scenic]
        si += len(scenic_today)
        food_today = foods[fi : fi + per_day_food]
        fi += len(food_today)

        items_cnt = len(scenic_today) + len(food_today)
        times = _alloc_times(items_cnt)
        # 路线顺序优化：按最近邻排序
        combined = [("scenic_spot", s) for s in scenic_today] + [("food_place", f) for f in food_today]
        ordered_pairs = _order_by_nearest(combined)
        ti = 0
        for t, obj in ordered_pairs:
            st, et = times[ti]
            day_items.append({"type": t, "id": obj.id, "start_time": st, "end_time": et})
            ti += 1

        days_out.append({"day_index": d, "items": day_items})

    return jsonify({"itinerary": {"days": days_out, "city": city}})
