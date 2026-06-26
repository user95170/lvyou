import json
from math import log
from collections import defaultdict
import random

from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import func

from ..db import db
from ..models import (
    ScenicSpot,
    Hotel,
    FoodPlace,
    UserProfile,
    ContentStandard,
    Rating,
)
from ..services.demographics import (
    load_user_demographics,
    scenic_demographic_adjustment,
    food_demographic_adjustment,
)

recommend_bp = Blueprint("recommend", __name__, url_prefix="/api/recommend")
fallback_metrics = defaultdict(int)
strategy_metrics = defaultdict(int)
request_count = 0

# 缓存 IMDb 风格 Bayesian WR 参数，按 entity_type 维度缓存
_WR_PARAMS = {}  # type: ignore


def _get_wr_params_for(entity_type: str):
    global _WR_PARAMS
    if isinstance(_WR_PARAMS, dict) and entity_type in _WR_PARAMS:
        return _WR_PARAMS[entity_type]

    try:
        C = float(
            db.session.query(func.avg(Rating.score))
            .filter(Rating.target_type == entity_type)
            .scalar()
            or 0.0
        )
    except Exception:
        C = 0.0

    if entity_type == "scenic_spot":
        rows = db.session.query(ScenicSpot.rating_count).all()
    elif entity_type == "hotel":
        rows = db.session.query(Hotel.rating_count).all()
    elif entity_type == "food_place":
        rows = db.session.query(FoodPlace.rating_count).all()
    else:
        rows = []

    counts = []
    for row in rows:
        try:
            counts.append(float(row[0] or 0))
        except Exception:
            continue

    if counts:
        counts.sort()
        idx = int(0.60 * (len(counts) - 1))
        m = float(counts[idx])
        if m < 1.0:
            m = 1.0
    else:
        m = 10.0

    _WR_PARAMS[entity_type] = (C, m)
    return _WR_PARAMS[entity_type]


def _get_limit_from_request(default: int = 10, max_limit: int = 50) -> int:
    try:
        limit = int(request.args.get("limit", default))
    except ValueError:
        limit = default
    if limit < 1:
        limit = default
    if limit > max_limit:
        limit = max_limit
    return limit


def _parse_summary_to_dict(summary: str) -> dict:
    """将 ContentStandard.summary 安全解析为 dict。

    兼容 JSON 字符串和 Python dict 的 str 表达形式（单引号）。
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


def _build_scenic_multi_source_features(spots):
    """为一批景点构建多源特征映射：spot_id -> 特征 dict。"""

    spot_ids = [s.id for s in spots]
    if not spot_ids:
        return {}

    rows = (
        ContentStandard.query.filter(
            ContentStandard.entity_type == "scenic_spot",
            ContentStandard.entity_id.in_(spot_ids),
            ContentStandard.source_type.in_(
                ["internal_rating", "ota_stats", "ota", "social_media"]
            ),
        ).all()
    )

    features = {}
    for row in rows:
        state = features.setdefault(row.entity_id, {})
        if row.source_type == "internal_rating":
            try:
                state["internal_popularity"] = float(row.popularity_score)
            except (TypeError, ValueError):
                continue
        else:
            data = _parse_summary_to_dict(row.summary)
            if not data:
                continue
            if row.source_type in ("ota_stats", "ota"):
                if (
                    state.get("_ota_source") == "ota_stats"
                    and row.source_type != "ota_stats"
                ):
                    continue
                try:
                    state["ota_rating"] = float(
                        data.get("external_rating")
                        or data.get("rating")
                        or 0
                    )
                except (TypeError, ValueError):
                    pass
                try:
                    state["ota_review_count"] = int(
                        data.get("review_count")
                        or data.get("external_review_count")
                        or 0
                    )
                except (TypeError, ValueError):
                    pass
                state["_ota_source"] = row.source_type
            elif row.source_type == "social_media":
                try:
                    state["social_interactions"] = int(
                        data.get("interaction_sum", 0) or 0
                    )
                except (TypeError, ValueError):
                    pass
                try:
                    state["social_sentiment"] = float(
                        data.get("sentiment_avg", 0.0) or 0.0
                    )
                except (TypeError, ValueError):
                    pass

    return features


def _build_hotel_multi_source_features(hotels):
    hotel_ids = [h.id for h in hotels]
    if not hotel_ids:
        return {}

    rows = (
        ContentStandard.query.filter(
            ContentStandard.entity_type == "hotel",
            ContentStandard.entity_id.in_(hotel_ids),
            ContentStandard.source_type.in_(
                ["internal_rating", "ota_stats", "ota", "social_media"]
            ),
        ).all()
    )

    features = {}
    for row in rows:
        state = features.setdefault(row.entity_id, {})
        if row.source_type == "internal_rating":
            try:
                state["internal_popularity"] = float(row.popularity_score)
            except (TypeError, ValueError):
                continue
        else:
            data = _parse_summary_to_dict(row.summary)
            if not data:
                continue
            if row.source_type in ("ota_stats", "ota"):
                if (
                    state.get("_ota_source") == "ota_stats"
                    and row.source_type != "ota_stats"
                ):
                    continue
                try:
                    state["ota_rating"] = float(
                        data.get("external_rating")
                        or data.get("rating")
                        or 0
                    )
                except (TypeError, ValueError):
                    pass
                try:
                    state["ota_review_count"] = int(
                        data.get("review_count")
                        or data.get("external_review_count")
                        or 0
                    )
                except (TypeError, ValueError):
                    pass
                state["_ota_source"] = row.source_type
            elif row.source_type == "social_media":
                try:
                    state["social_interactions"] = int(
                        data.get("interaction_sum", 0) or 0
                    )
                except (TypeError, ValueError):
                    pass
                try:
                    state["social_sentiment"] = float(
                        data.get("sentiment_avg", 0.0) or 0.0
                    )
                except (TypeError, ValueError):
                    pass

    return features


def _build_food_multi_source_features(foods):
    food_ids = [f.id for f in foods]
    if not food_ids:
        return {}

    rows = (
        ContentStandard.query.filter(
            ContentStandard.entity_type.in_(["food_place", "food"]),
            ContentStandard.entity_id.in_(food_ids),
            ContentStandard.source_type.in_(
                ["internal_rating", "ota_stats", "ota", "social_media"]
            ),
        ).all()
    )

    features = {}
    for row in rows:
        state = features.setdefault(row.entity_id, {})
        if row.source_type == "internal_rating":
            try:
                state["internal_popularity"] = float(row.popularity_score)
            except (TypeError, ValueError):
                continue
        else:
            data = _parse_summary_to_dict(row.summary)
            if not data:
                continue
            if row.source_type in ("ota_stats", "ota"):
                if (
                    state.get("_ota_source") == "ota_stats"
                    and row.source_type != "ota_stats"
                ):
                    continue
                try:
                    state["ota_rating"] = float(
                        data.get("external_rating")
                        or data.get("rating")
                        or 0
                    )
                except (TypeError, ValueError):
                    pass
                try:
                    state["ota_review_count"] = int(
                        data.get("review_count")
                        or data.get("external_review_count")
                        or 0
                    )
                except (TypeError, ValueError):
                    pass
                state["_ota_source"] = row.source_type
            elif row.source_type == "social_media":
                try:
                    state["social_interactions"] = int(
                        data.get("interaction_sum", 0) or 0
                    )
                except (TypeError, ValueError):
                    pass
                try:
                    state["social_sentiment"] = float(
                        data.get("sentiment_avg", 0.0) or 0.0
                    )
                except (TypeError, ValueError):
                    pass

    return features


def _compute_multi_source_score(spot: ScenicSpot, feature_map: dict) -> float:
    """根据多源数据为单个景点计算综合得分。

    组合来源：
      - 内部评分聚合的 popularity_score（或按当前评分即时计算）；
      - OTA 外部评分与评论数；
      - 社交媒体互动量与情感得分。
    """

    features = feature_map.get(spot.id) or {}

    rating_avg = float(spot.rating_avg) if spot.rating_avg is not None else 0.0
    rating_count = int(spot.rating_count or 0)

    # 内部受欢迎度：优先使用聚合结果，否则按当前评分即时计算
    internal_pop = None
    try:
        internal_pop = float(features.get("internal_popularity"))
    except (TypeError, ValueError):
        internal_pop = None

    if internal_pop is None:
        C, m = _get_wr_params_for("scenic_spot")
        v = float(max(rating_count, 0))
        R = float(rating_avg)
        denom = v + float(m)
        internal_pop = (v / denom) * R + (float(m) / denom) * float(C) if denom > 0 else float(C)

    try:
        ota_rating = float(features.get("ota_rating", 0.0) or 0.0)
    except (TypeError, ValueError):
        ota_rating = 0.0

    try:
        ota_reviews = int(features.get("ota_review_count", 0) or 0)
    except (TypeError, ValueError):
        ota_reviews = 0

    try:
        social_interactions = int(features.get("social_interactions", 0) or 0)
    except (TypeError, ValueError):
        social_interactions = 0

    try:
        social_sentiment = float(features.get("social_sentiment", 0.0) or 0.0)
    except (TypeError, ValueError):
        social_sentiment = 0.0

    # 社交媒体热度做简单缩放，避免数值过大
    social_heat = min(max(social_interactions, 0), 10000) / 1000.0

    # 综合得分：内部受欢迎度 + 外部评分 + 社交热度 + 情感加权
    score = internal_pop + ota_rating + social_heat + 2.0 * social_sentiment
    return score


def _compute_hotel_multi_source_score(hotel: Hotel, feature_map: dict) -> float:
    features = feature_map.get(hotel.id) or {}

    rating_avg = float(hotel.rating_avg) if hotel.rating_avg is not None else 0.0
    rating_count = int(hotel.rating_count or 0)

    internal_pop = None
    try:
        internal_pop = float(features.get("internal_popularity"))
    except (TypeError, ValueError):
        internal_pop = None

    if internal_pop is None:
        C, m = _get_wr_params_for("hotel")
        v = float(max(rating_count, 0))
        R = float(rating_avg)
        denom = v + float(m)
        internal_pop = (v / denom) * R + (float(m) / denom) * float(C) if denom > 0 else float(C)

    try:
        ota_rating = float(features.get("ota_rating", 0.0) or 0.0)
    except (TypeError, ValueError):
        ota_rating = 0.0
    try:
        social_interactions = int(features.get("social_interactions", 0) or 0)
    except (TypeError, ValueError):
        social_interactions = 0
    try:
        social_sentiment = float(features.get("social_sentiment", 0.0) or 0.0)
    except (TypeError, ValueError):
        social_sentiment = 0.0

    social_heat = min(max(social_interactions, 0), 10000) / 1000.0
    return internal_pop + ota_rating + social_heat + 2.0 * social_sentiment


def _compute_food_multi_source_score(food: FoodPlace, feature_map: dict) -> float:
    features = feature_map.get(food.id) or {}

    rating_avg = float(food.rating_avg) if food.rating_avg is not None else 0.0
    rating_count = int(food.rating_count or 0)

    internal_pop = None
    try:
        internal_pop = float(features.get("internal_popularity"))
    except (TypeError, ValueError):
        internal_pop = None

    if internal_pop is None:
        C, m = _get_wr_params_for("food_place")
        v = float(max(rating_count, 0))
        R = float(rating_avg)
        denom = v + float(m)
        internal_pop = (v / denom) * R + (float(m) / denom) * float(C) if denom > 0 else float(C)

    try:
        ota_rating = float(features.get("ota_rating", 0.0) or 0.0)
    except (TypeError, ValueError):
        ota_rating = 0.0
    try:
        social_interactions = int(features.get("social_interactions", 0) or 0)
    except (TypeError, ValueError):
        social_interactions = 0
    try:
        social_sentiment = float(features.get("social_sentiment", 0.0) or 0.0)
    except (TypeError, ValueError):
        social_sentiment = 0.0

    social_heat = min(max(social_interactions, 0), 10000) / 1000.0
    return internal_pop + ota_rating + social_heat + 2.0 * social_sentiment


def _build_scenic_reasons(spot: ScenicSpot, feature_map: dict, user_profile, preferred_set, demo=None):
    reasons = []
    features = feature_map.get(spot.id) or {}

    try:
        rating_avg = float(spot.rating_avg) if spot.rating_avg is not None else 0.0
    except (TypeError, ValueError):
        rating_avg = 0.0
    try:
        rating_count = int(spot.rating_count or 0)
    except (TypeError, ValueError):
        rating_count = 0

    if rating_avg >= 4.5 and rating_count >= 50:
        reasons.append("本站评分较高")

    try:
        ota_rating = float(features.get("ota_rating", 0.0) or 0.0)
    except (TypeError, ValueError):
        ota_rating = 0.0
    try:
        ota_reviews = int(features.get("ota_review_count", 0) or 0)
    except (TypeError, ValueError):
        ota_reviews = 0

    if ota_rating >= 4.6 and ota_reviews >= 100:
        reasons.append("OTA 平台评分优秀")
    elif ota_rating >= 4.5:
        reasons.append("OTA 平台评分较好")

    try:
        social_interactions = int(features.get("social_interactions", 0) or 0)
    except (TypeError, ValueError):
        social_interactions = 0
    try:
        social_sentiment = float(features.get("social_sentiment", 0.0) or 0.0)
    except (TypeError, ValueError):
        social_sentiment = 0.0

    if social_interactions >= 5000:
        reasons.append("社交媒体热度很高")
    elif social_interactions >= 2000:
        reasons.append("社交媒体讨论度较高")

    if social_sentiment >= 0.85:
        reasons.append("网友整体评价非常好")
    elif social_sentiment >= 0.75:
        reasons.append("网友评价较好")

    if preferred_set and spot.category and spot.category in preferred_set:
        reasons.append(f"符合你的偏好类型：{spot.category}")

    if demo:
        _, demo_reasons = scenic_demographic_adjustment(spot, demo)
        for r in demo_reasons:
            if r not in reasons:
                reasons.append(r)

    return reasons


def _build_food_reasons(food: FoodPlace, feature_map: dict, preferred_set, demo=None):
    reasons = []
    features = feature_map.get(food.id) or {}

    try:
        rating_avg = float(food.rating_avg) if food.rating_avg is not None else 0.0
    except (TypeError, ValueError):
        rating_avg = 0.0
    try:
        rating_count = int(food.rating_count or 0)
    except (TypeError, ValueError):
        rating_count = 0

    if rating_avg >= 4.5 and rating_count >= 50:
        reasons.append("本站评分较高")

    try:
        ota_rating = float(features.get("ota_rating", 0.0) or 0.0)
    except (TypeError, ValueError):
        ota_rating = 0.0
    if ota_rating >= 4.6:
        reasons.append("OTA 平台评分优秀")
    elif ota_rating >= 4.5:
        reasons.append("OTA 平台评分较好")

    if preferred_set:
        cuisine = (food.cuisine_type or "").strip()
        matched = cuisine in preferred_set
        if not matched and food.tags:
            for t in preferred_set:
                if t and t in food.tags:
                    matched = True
                    break
        if matched:
            label = cuisine or "你喜欢的口味"
            reasons.append(f"符合你的偏好类型：{label}")

    if demo:
        _, demo_reasons = food_demographic_adjustment(food, demo)
        for r in demo_reasons:
            if r not in reasons:
                reasons.append(r)

    return reasons


def _load_cf_neighbors_map():
    rows = ContentStandard.query.filter_by(
        entity_type="scenic_spot", source_type="item_cf_similarity"
    ).all()
    mapping = {}
    for row in rows:
        if not row.summary:
            continue
        data = _parse_summary_to_dict(row.summary)
        neighbors = data.get("neighbors") or []
        ids = []
        for item in neighbors:
            try:
                sid = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            ids.append(sid)
        if ids:
            mapping[row.entity_id] = ids
    return mapping


def _load_cf_neighbors_map_with_sim():
    rows = ContentStandard.query.filter_by(
        entity_type="scenic_spot", source_type="item_cf_similarity"
    ).all()
    mapping = {}
    for row in rows:
        if not row.summary:
            continue
        data = _parse_summary_to_dict(row.summary)
        neighbors = data.get("neighbors") or []
        pairs = []
        for item in neighbors:
            try:
                sid = int(item.get("id"))
                sim = float(item.get("sim", 0.0) or 0.0)
            except (TypeError, ValueError):
                continue
            pairs.append((sid, sim))
        if pairs:
            mapping[row.entity_id] = pairs
    return mapping


def _recommend_cf_item_ids(user_history, k):
    cf_neighbors = _load_cf_neighbors_map()
    scores = defaultdict(float)
    history_set = set(user_history)

    for sid in history_set:
        neighbors = cf_neighbors.get(sid) or []
        for nid in neighbors:
            if nid in history_set:
                continue
            scores[nid] += 1.0

    if not scores:
        return []

    ranked = sorted(scores.items(), key=lambda x: (-x[1], -x[0]))
    return [sid for sid, _ in ranked[:k]]


def _normalize_score_dict(scores):
    if not scores:
        return {}
    values = list(scores.values())
    min_s = min(values)
    max_s = max(values)
    if max_s <= min_s:
        return {k: 1.0 for k in scores}
    denom = max_s - min_s
    return {k: (float(v) - min_s) / denom for k, v in scores.items()}


def _recommend_scenic_spots_cf_for_user(user_id, limit, city):
    ratings = (
        Rating.query.filter_by(user_id=user_id, target_type="scenic_spot")
        .order_by(Rating.created_at.asc())
        .all()
    )
    if not ratings:
        return []

    history_ids = []
    for r in ratings:
        try:
            sid = int(r.target_id)
        except (TypeError, ValueError):
            continue
        history_ids.append(sid)

    if not history_ids:
        return []

    rec_ids = _recommend_cf_item_ids(history_ids, k=max(limit * 3, limit))
    if not rec_ids:
        return []

    query = ScenicSpot.query.filter(ScenicSpot.id.in_(rec_ids))
    if city:
        query = query.filter(ScenicSpot.city.like(f"%{city}%"))
    spots = query.all()
    if not spots:
        return []

    spot_map = {s.id: s for s in spots}
    ordered = [spot_map[sid] for sid in rec_ids if sid in spot_map]
    return ordered[:limit]


def _recommend_scenic_spots_hybrid_for_user(user_id, limit, city):
    ratings = Rating.query.filter_by(target_type="scenic_spot").all()
    if not ratings:
        return [], {}

    train_triples = []
    all_item_ids_set = set()
    for r in ratings:
        if r.user_id is None:
            continue
        try:
            uid = int(r.user_id)
            sid = int(r.target_id)
            score = float(r.score)
        except (TypeError, ValueError):
            continue
        train_triples.append((uid, sid, score))
        all_item_ids_set.add(sid)

    if not train_triples:
        return [], {}

    random.seed(42)
    global_mean, user_biases, item_biases, user_factors, item_factors = _train_mf(
        train_triples
    )

    user_history_ids = []
    for r in ratings:
        if r.user_id != user_id:
            continue
        try:
            sid = int(r.target_id)
        except (TypeError, ValueError):
            continue
        user_history_ids.append(sid)

    if not user_history_ids:
        return [], {}

    query = ScenicSpot.query
    if city:
        query = query.filter(ScenicSpot.city.like(f"%{city}%"))

    query = query.order_by(
        ScenicSpot.rating_avg.desc(),
        ScenicSpot.rating_count.desc(),
        ScenicSpot.id.desc(),
    )

    candidate_limit = min(200, max(limit * 3, limit))
    candidates = query.limit(candidate_limit).all()
    if not candidates:
        return [], {}

    feature_map = _build_scenic_multi_source_features(candidates)
    candidate_ids = {s.id for s in candidates}

    base_scores = {}
    for spot in candidates:
        base_scores[spot.id] = _compute_multi_source_score(spot, feature_map)

    cf_neighbors = _load_cf_neighbors_map_with_sim()
    cf_scores = defaultdict(float)
    history_set = set(user_history_ids)
    for sid in history_set:
        neighbors = cf_neighbors.get(sid) or []
        for nid, sim in neighbors:
            if nid not in candidate_ids:
                continue
            cf_scores[nid] += float(sim)

    mf_scores = {}
    pu = user_factors.get(user_id)
    if pu is not None:
        bu = user_biases.get(user_id, 0.0)
        for sid in candidate_ids:
            if sid in history_set:
                continue
            qi = item_factors.get(sid)
            if qi is None:
                continue
            bi = item_biases.get(sid, 0.0)
            score = global_mean + bu + bi + sum(p * q for p, q in zip(pu, qi))
            mf_scores[sid] = score

    base_norm = _normalize_score_dict(base_scores)
    cf_norm = _normalize_score_dict(cf_scores) if cf_scores else {}
    mf_norm = _normalize_score_dict(mf_scores) if mf_scores else {}

    w_base = 0.2
    w_cf = 0.4
    w_mf = 0.4

    total_weight = 0.0
    if base_norm:
        total_weight += w_base
    if cf_norm:
        total_weight += w_cf
    if mf_norm:
        total_weight += w_mf

    if total_weight <= 0.0:
        candidates.sort(
            key=lambda spot: (
                -_compute_multi_source_score(spot, feature_map),
                -(float(spot.rating_avg) if spot.rating_avg is not None else 0.0),
                -int(spot.rating_count or 0),
                -spot.id,
            )
        )
        return candidates[:limit], feature_map

    scale_base = w_base / total_weight if base_norm else 0.0
    scale_cf = w_cf / total_weight if cf_norm else 0.0
    scale_mf = w_mf / total_weight if mf_norm else 0.0

    total_scores = {}
    for sid in candidate_ids:
        score = 0.0
        if base_norm:
            score += scale_base * base_norm.get(sid, 0.0)
        if cf_norm:
            score += scale_cf * cf_norm.get(sid, 0.0)
        if mf_norm:
            score += scale_mf * mf_norm.get(sid, 0.0)
        total_scores[sid] = score

    spot_map = {s.id: s for s in candidates}
    ordered_ids = sorted(
        candidate_ids,
        key=lambda sid: (
            -total_scores.get(sid, 0.0),
            -(
                float(spot_map[sid].rating_avg)
                if spot_map[sid].rating_avg is not None
                else 0.0
            ),
            -int(spot_map[sid].rating_count or 0),
            -sid,
        ),
    )

    ordered = [spot_map[sid] for sid in ordered_ids if sid in spot_map]
    return ordered[:limit], feature_map


def _train_mf(train_triples, n_factors=8, n_epochs=15, lr=0.02, reg=0.05):
    if not train_triples:
        return 0.0, {}, {}, {}, {}

    user_factors = {}
    item_factors = {}
    user_biases = {}
    item_biases = {}

    rating_sum = 0.0
    for _, _, r in train_triples:
        rating_sum += r
    global_mean = rating_sum / float(len(train_triples))

    def _init_vector():
        return [0.1 * (random.random() - 0.5) for _ in range(n_factors)]

    for uid, sid, _ in train_triples:
        if uid not in user_factors:
            user_factors[uid] = _init_vector()
            user_biases[uid] = 0.0
        if sid not in item_factors:
            item_factors[sid] = _init_vector()
            item_biases[sid] = 0.0

    for _ in range(n_epochs):
        random.shuffle(train_triples)
        for uid, sid, rating in train_triples:
            pu = user_factors.get(uid)
            qi = item_factors.get(sid)
            if pu is None or qi is None:
                continue
            bu = user_biases.get(uid, 0.0)
            bi = item_biases.get(sid, 0.0)

            pred = global_mean + bu + bi + sum(p * q for p, q in zip(pu, qi))
            err = rating - pred

            user_biases[uid] = bu + lr * (err - reg * bu)
            item_biases[sid] = bi + lr * (err - reg * bi)

            for k in range(n_factors):
                p_k = pu[k]
                q_k = qi[k]
                pu[k] += lr * (err * q_k - reg * p_k)
                qi[k] += lr * (err * p_k - reg * q_k)

    return global_mean, user_biases, item_biases, user_factors, item_factors


def _recommend_mf_item_ids(
    user_id,
    history_ids,
    global_mean,
    user_biases,
    item_biases,
    user_factors,
    item_factors,
    all_item_ids,
    k,
):
    pu = user_factors.get(user_id)
    if pu is None:
        return []

    bu = user_biases.get(user_id, 0.0)
    history_set = set(history_ids)
    scores = []

    for sid in all_item_ids:
        if sid in history_set:
            continue
        qi = item_factors.get(sid)
        if qi is None:
            continue
        bi = item_biases.get(sid, 0.0)
        score = global_mean + bu + bi + sum(p * q for p, q in zip(pu, qi))
        scores.append((sid, score))

    if not scores:
        return []

    scores.sort(key=lambda x: (-x[1], -x[0]))
    return [sid for sid, _ in scores[:k]]


def _recommend_scenic_spots_mf_for_user(user_id, limit, city):
    ratings = Rating.query.filter_by(target_type="scenic_spot").all()
    if not ratings:
        return []

    train_triples = []
    all_item_ids_set = set()
    for r in ratings:
        if r.user_id is None:
            continue
        try:
            uid = int(r.user_id)
            sid = int(r.target_id)
            score = float(r.score)
        except (TypeError, ValueError):
            continue
        train_triples.append((uid, sid, score))
        all_item_ids_set.add(sid)

    if not train_triples:
        return []

    random.seed(42)
    global_mean, user_biases, item_biases, user_factors, item_factors = _train_mf(
        train_triples
    )
    all_item_ids = sorted(all_item_ids_set)

    user_ratings = (
        Rating.query.filter_by(user_id=user_id, target_type="scenic_spot")
        .order_by(Rating.created_at.asc())
        .all()
    )
    if not user_ratings:
        return []

    history_ids = []
    for r in user_ratings:
        try:
            sid = int(r.target_id)
        except (TypeError, ValueError):
            continue
        history_ids.append(sid)

    if not history_ids:
        return []

    rec_ids = _recommend_mf_item_ids(
        user_id,
        history_ids,
        global_mean,
        user_biases,
        item_biases,
        user_factors,
        item_factors,
        all_item_ids,
        k=max(limit * 3, limit),
    )
    if not rec_ids:
        return []

    query = ScenicSpot.query.filter(ScenicSpot.id.in_(rec_ids))
    if city:
        query = query.filter(ScenicSpot.city.like(f"%{city}%"))
    spots = query.all()
    if not spots:
        return []

    spot_map = {s.id: s for s in spots}
    ordered = [spot_map[sid] for sid in rec_ids if sid in spot_map]
    return ordered[:limit]


@recommend_bp.get("/scenic-spots")
def recommend_scenic_spots():
    """景点推荐接口（当前为热门排序）。

    支持参数：
      - city: 可选，按城市过滤
      - limit: 返回条数，默认 10，上限 50
      - user_id: 预留参数，当前版本未启用个性化，仅用于后续扩展
    """

    global request_count
    limit = _get_limit_from_request()
    city = request.args.get("city")
    user_id_raw = request.args.get("user_id")
    raw_strategy = (request.args.get("strategy") or "").lower()

    allowed_strategies = {"popular", "profile", "cf", "mf", "hybrid"}
    strategy = raw_strategy if raw_strategy in allowed_strategies else ""

    uid = None
    if user_id_raw is not None:
        try:
            uid = int(user_id_raw)
        except ValueError:
            uid = None

    user_profile = None
    if uid is not None:
        user_profile = UserProfile.query.filter_by(user_id=uid).first()

    demo = load_user_demographics(uid)

    is_cold_start = False
    if uid is not None:
        has_rating = (
            Rating.query.filter_by(user_id=uid, target_type="scenic_spot")
            .limit(1)
            .first()
            is not None
        )
        if (not has_rating) and (user_profile is None or not user_profile.prefer_scenic_types):
            is_cold_start = True

    # 若未显式指定 strategy，且为有历史行为的登录用户，则默认采用 Hybrid 作为个性化策略
    if not raw_strategy and strategy == "" and uid is not None and not is_cold_start:
        strategy = "hybrid"

    feature_map = {}
    preferred_set = None
    used_strategy = strategy or "multi_source"
    requested_strategy = raw_strategy or None
    fallback_reason = None
    if raw_strategy and raw_strategy not in allowed_strategies:
        fallback_reason = "unknown_strategy"

    items = None

    # 优先尝试 CF/MF/Hybrid 个性化策略
    if strategy == "hybrid" and uid is not None:
        items, feature_map = _recommend_scenic_spots_hybrid_for_user(uid, limit, city)
        if items:
            used_strategy = "hybrid"
        elif fallback_reason is None:
            fallback_reason = "hybrid_cold_start" if is_cold_start else "hybrid_no_recommendations"
    elif raw_strategy == "hybrid" and uid is None and fallback_reason is None:
        fallback_reason = "hybrid_user_required"

    if (items is None or not items) and strategy == "cf" and uid is not None:
        items = _recommend_scenic_spots_cf_for_user(uid, limit, city)
        if items:
            used_strategy = "cf"
        elif fallback_reason is None:
            fallback_reason = "cf_cold_start" if is_cold_start else "cf_no_recommendations"
    elif raw_strategy == "cf" and uid is None and fallback_reason is None:
        fallback_reason = "cf_user_required"

    if (items is None or not items) and strategy == "mf" and uid is not None:
        items = _recommend_scenic_spots_mf_for_user(uid, limit, city)
        if items:
            used_strategy = "mf"
        elif fallback_reason is None:
            fallback_reason = "mf_cold_start" if is_cold_start else "mf_no_recommendations"
    elif items is None and raw_strategy == "mf" and uid is None and fallback_reason is None:
        fallback_reason = "mf_user_required"

    # 若 CF/MF 不可用，则回退到原有热门/画像 + 多源排序逻辑
    if items is None or not items:
        query = ScenicSpot.query
        if city:
            query = query.filter(ScenicSpot.city.like(f"%{city}%"))

        query = query.order_by(
            ScenicSpot.rating_avg.desc(),
            ScenicSpot.rating_count.desc(),
            ScenicSpot.id.desc(),
        )

        # 为了融合多源数据，这里统一先取一批候选，再在内存中根据综合得分排序
        candidate_limit = min(200, max(limit * 3, limit))
        candidates = query.limit(candidate_limit).all()
        feature_map = _build_scenic_multi_source_features(candidates)

        if user_profile is None or not user_profile.prefer_scenic_types or strategy == "popular":

            def sort_key_no_profile(spot: ScenicSpot):
                score = _compute_multi_source_score(spot, feature_map)
                score += scenic_demographic_adjustment(spot, demo)[0]
                rating_avg = float(spot.rating_avg) if spot.rating_avg is not None else 0.0
                rating_count = int(spot.rating_count or 0)
                return (-score, -rating_avg, -rating_count, -spot.id)

            candidates.sort(key=sort_key_no_profile)
            items = candidates[:limit]
            if not strategy:
                used_strategy = "multi_source"
            elif strategy == "popular":
                used_strategy = "popular"
            if is_cold_start and fallback_reason is None and strategy in ("", "profile"):
                fallback_reason = "cold_start_user"
        else:
            preferred_types = [
                t.strip()
                for t in (user_profile.prefer_scenic_types or "").split(",")
                if t.strip()
            ]
            preferred_set = set(preferred_types)

            def sort_key(spot: ScenicSpot):
                in_pref = 0 if (spot.category in preferred_set) else 1
                score = _compute_multi_source_score(spot, feature_map)
                score += scenic_demographic_adjustment(spot, demo)[0]
                rating_avg = float(spot.rating_avg) if spot.rating_avg is not None else 0.0
                rating_count = int(spot.rating_count or 0)
                return (in_pref, -score, -rating_avg, -rating_count, -spot.id)

            candidates.sort(key=sort_key)
            items = candidates[:limit]
            if strategy in ("", "profile"):
                used_strategy = "profile"

    # 若 CF/MF/Hybrid 已产生部分结果但条数少于 limit，则使用多源热门结果进行补全
    if items and len(items) < limit and used_strategy in ("cf", "mf", "hybrid"):
        existing_ids = {s.id for s in items}
        backfill_query = ScenicSpot.query
        if city:
            backfill_query = backfill_query.filter(ScenicSpot.city.like(f"%{city}%"))
        backfill_query = backfill_query.order_by(
            ScenicSpot.rating_avg.desc(),
            ScenicSpot.rating_count.desc(),
            ScenicSpot.id.desc(),
        )
        backfill_candidate_limit = min(200, max(limit * 3, limit))
        backfill_candidates = backfill_query.limit(backfill_candidate_limit).all()
        backfill_candidates = [s for s in backfill_candidates if s.id not in existing_ids]
        if backfill_candidates:
            backfill_feature_map = _build_scenic_multi_source_features(backfill_candidates)

            def sort_key_backfill(spot: ScenicSpot):
                score = _compute_multi_source_score(spot, backfill_feature_map)
                rating_avg = float(spot.rating_avg) if spot.rating_avg is not None else 0.0
                rating_count = int(spot.rating_count or 0)
                return (-score, -rating_avg, -rating_count, -spot.id)

            backfill_candidates.sort(key=sort_key_backfill)
            need = limit - len(items)
            items.extend(backfill_candidates[:need])
            if fallback_reason is None:
                fallback_reason = f"{used_strategy}_backfilled_with_baseline"

    # 为 CF/MF 推荐的结果补全多源特征，便于展示理由
    if feature_map == {} and items:
        feature_map = _build_scenic_multi_source_features(items)

    result_items = []
    for spot in items:
        data = spot.to_dict()
        reasons = _build_scenic_reasons(spot, feature_map, user_profile, preferred_set, demo)
        if reasons:
            data["reasons"] = reasons
        result_items.append(data)

    if fallback_reason:
        fallback_metrics[fallback_reason] += 1
        current_app.logger.info(
            "scenic_reco_fallback reason=%s strategy=%s requested=%s user_id=%s city=%s limit=%s",
            fallback_reason,
            used_strategy,
            requested_strategy,
            uid,
            city,
            limit,
        )

    request_count += 1
    strategy_metrics[used_strategy] += 1

    return jsonify(
        {
            "items": result_items,
            "meta": {
                "limit": limit,
                "city": city,
                "user_id": uid,
                "strategy": used_strategy,
                "requested_strategy": requested_strategy,
                "fallback_reason": fallback_reason,
                "cold_start": is_cold_start,
            },
        }
    )


@recommend_bp.get("/hotels")
def recommend_hotels():
    """酒店推荐接口（当前为热门排序）。

    支持参数：
      - city: 可选，按城市过滤
      - limit: 返回条数，默认 10，上限 50
      - user_id: 预留参数，当前版本未启用个性化
    """

    limit = _get_limit_from_request()
    city = request.args.get("city")
    user_id_raw = request.args.get("user_id")

    uid = None
    if user_id_raw is not None:
        try:
            uid = int(user_id_raw)
        except ValueError:
            uid = None

    user_profile = None
    if uid is not None:
        user_profile = UserProfile.query.filter_by(user_id=uid).first()

    query = Hotel.query
    if city:
        query = query.filter(Hotel.city.like(f"%{city}%"))

    query = query.order_by(
        Hotel.rating_avg.desc(),
        Hotel.rating_count.desc(),
        Hotel.id.desc(),
    )

    # 统一候选集规模，使用多源特征 + WR 回退进行排序
    candidate_limit = min(200, max(limit * 3, limit))
    hotels = query.limit(candidate_limit).all()

    feature_map = _build_hotel_multi_source_features(hotels) if hotels else {}

    if user_profile is not None and hotels:
        budget_level = user_profile.budget_level

        def _price_bucket(price: float) -> int:
            if price < 200:
                return 1
            if price < 400:
                return 2
            if price < 600:
                return 3
            return 4

        def sort_key(h: Hotel):
            score = _compute_hotel_multi_source_score(h, feature_map)
            rating_avg = float(h.rating_avg) if h.rating_avg is not None else 0.0
            rating_count = int(h.rating_count or 0)

            price_mismatch = 0
            if budget_level is not None and h.avg_price is not None:
                try:
                    price = float(h.avg_price)
                except (TypeError, ValueError):
                    price_mismatch = 0
                else:
                    bucket = _price_bucket(price)
                    if budget_level < 1:
                        target_bucket = 1
                    elif budget_level > 4:
                        target_bucket = 4
                    else:
                        target_bucket = budget_level
                    price_mismatch = abs(bucket - target_bucket)

            return (price_mismatch, -score, -rating_avg, -rating_count, -h.id)

        hotels.sort(key=sort_key)
    else:
        def sort_key_no_profile(h: Hotel):
            score = _compute_hotel_multi_source_score(h, feature_map)
            rating_avg = float(h.rating_avg) if h.rating_avg is not None else 0.0
            rating_count = int(h.rating_count or 0)
            return (-score, -rating_avg, -rating_count, -h.id)

        hotels.sort(key=sort_key_no_profile)

    items = hotels[:limit]

    return jsonify(
        {
            "items": [hotel.to_dict() for hotel in items],
            "meta": {"limit": limit, "city": city, "user_id": uid},
        }
    )


@recommend_bp.get("/foods")
def recommend_foods():
    """美食推荐接口（当前为热门排序）。

    支持参数：
      - city: 可选，按城市过滤
      - limit: 返回条数，默认 10，上限 50
      - user_id: 预留参数，当前版本未启用个性化
    """

    limit = _get_limit_from_request()
    city = request.args.get("city")
    user_id_raw = request.args.get("user_id")

    uid = None
    if user_id_raw is not None:
        try:
            uid = int(user_id_raw)
        except ValueError:
            uid = None

    user_profile = None
    if uid is not None:
        user_profile = UserProfile.query.filter_by(user_id=uid).first()

    demo = load_user_demographics(uid)

    query = FoodPlace.query
    if city:
        query = query.filter(FoodPlace.city.like(f"%{city}%"))

    query = query.order_by(
        FoodPlace.rating_avg.desc(),
        FoodPlace.rating_count.desc(),
        FoodPlace.id.desc(),
    )

    candidate_limit = min(200, max(limit * 3, limit))
    preferred_set = None
    if user_profile is not None and user_profile.prefer_food_types:
        preferred_types = [
            t.strip()
            for t in (user_profile.prefer_food_types or "").split(",")
            if t.strip()
        ]
        preferred_set = set(preferred_types)

    foods = query.limit(candidate_limit).all()

    feature_map = _build_food_multi_source_features(foods) if foods else {}

    if preferred_set and foods:

        def sort_key(food: FoodPlace):
            cuisine = (food.cuisine_type or "").strip()
            tags_text = food.tags or ""
            in_pref = 1
            if cuisine in preferred_set:
                in_pref = 0
            else:
                for t in preferred_set:
                    if t and t in tags_text:
                        in_pref = 0
                        break

            score = _compute_food_multi_source_score(food, feature_map)
            score += food_demographic_adjustment(food, demo)[0]
            rating_avg = float(food.rating_avg) if food.rating_avg is not None else 0.0
            rating_count = int(food.rating_count or 0)
            return (in_pref, -score, -rating_avg, -rating_count, -food.id)

        foods.sort(key=sort_key)
    else:
        def sort_key_no_profile(food: FoodPlace):
            score = _compute_food_multi_source_score(food, feature_map)
            score += food_demographic_adjustment(food, demo)[0]
            rating_avg = float(food.rating_avg) if food.rating_avg is not None else 0.0
            rating_count = int(food.rating_count or 0)
            return (-score, -rating_avg, -rating_count, -food.id)

        foods.sort(key=sort_key_no_profile)

    items = foods[:limit]

    result_items = []
    for food in items:
        data = food.to_dict()
        reasons = _build_food_reasons(food, feature_map, preferred_set, demo)
        if reasons:
            data["reasons"] = reasons
        result_items.append(data)

    return jsonify(
        {
            "items": result_items,
            "meta": {"limit": limit, "city": city, "user_id": uid},
        }
    )


@recommend_bp.get("/scenic-spots/<int:spot_id>/similar")
def recommend_similar_scenic_spots(spot_id: int):
    """基于 item-based 协同过滤的相似景点推荐。

    依赖离线脚本 `aggregate_scenic_cf.py` 的结果：
      - content_standard.entity_type = "scenic_spot"
      - source_type = "item_cf_similarity"
      - summary 字段中包含 {"neighbors": [{"id": scenic_id, "sim": similarity}, ...]}
    """

    limit = _get_limit_from_request()

    row = ContentStandard.query.filter_by(
        entity_type="scenic_spot",
        entity_id=spot_id,
        source_type="item_cf_similarity",
    ).first()

    if row is None or not row.summary:
        return jsonify({"items": [], "meta": {"spot_id": spot_id, "limit": limit, "reason": "no_similarity_data"}})

    try:
        summary_obj = json.loads(row.summary)
    except (TypeError, ValueError):
        summary_obj = {}

    neighbors = summary_obj.get("neighbors") or []
    if not isinstance(neighbors, list):
        neighbors = []

    # 保持协同过滤的相似度排序
    neighbor_ids = []
    sim_map = {}
    for item in neighbors:
        try:
            sid = int(item.get("id"))
            sim = float(item.get("sim", 0.0))
        except (TypeError, ValueError):
            continue
        if sid == spot_id:
            continue
        neighbor_ids.append(sid)
        sim_map[sid] = sim

    if not neighbor_ids:
        return jsonify({"items": [], "meta": {"spot_id": spot_id, "limit": limit, "reason": "no_valid_neighbors"}})

    # 为防止部分相似项在主表中已被删除，这里再做一次过滤
    spots = ScenicSpot.query.filter(ScenicSpot.id.in_(neighbor_ids)).all()
    if not spots:
        return jsonify({"items": [], "meta": {"spot_id": spot_id, "limit": limit, "reason": "spots_not_found"}})

    # 先按协同过滤的相似度排序，若相似度相同则兼顾评分和人气
    def sort_key(spot: ScenicSpot):
        sim = float(sim_map.get(spot.id, 0.0))
        rating_avg = float(spot.rating_avg) if spot.rating_avg is not None else 0.0
        rating_count = int(spot.rating_count or 0)
        return (-sim, -rating_avg, -rating_count, -spot.id)

    spots.sort(key=sort_key)
    top_spots = spots[:limit]

    return jsonify(
        {
            "items": [s.to_dict() for s in top_spots],
            "meta": {
                "spot_id": spot_id,
                "limit": limit,
                "source": "item_cf_similarity",
            },
        }
    )


@recommend_bp.get("/metrics")
def recommend_metrics():
    return jsonify(_build_recommend_metrics_payload())


def _build_recommend_metrics_payload() -> dict:
    return {
        "fallback_counts": dict(fallback_metrics),
        "strategy_counts": dict(strategy_metrics),
        "request_count": request_count,
    }
