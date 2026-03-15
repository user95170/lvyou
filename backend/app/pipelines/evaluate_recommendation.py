from __future__ import annotations

"""推荐效果评估脚本（离线模拟版）。

说明：
  - 本脚本用于在当前数据库数据的基础上，对不同推荐策略做一个初步的离线评估，
    便于后续真实数据接入之后快速复用。
  - 由于当前评分数据规模有限，本评估脚本更偏向“示范用法”，结果仅供参考。

评估思路（简化版 Top-N 命中率）：
  1. 从 rating 表中抽取有足够评分记录的用户；
  2. 对每个用户，将其最新的一部分评分作为“测试集”，较早的一部分作为“历史行为”；
  3. 以历史行为估计用户偏好，分别构造：
     - 热门推荐：不考虑用户，直接返回热门景点列表；
     - 画像推荐：使用当前在线接口的画像偏好逻辑（若 user_profile 已有数据）；
     - 协同过滤推荐：基于 aggregate_scenic_cf.py 生成的相似度，做 item-based Top-N 推荐；
  4. 检查测试集中景点是否出现在各策略的 Top-K 推荐列表中，统计 hit rate / precision@K 等简单指标。

运行方式（在项目根目录或 backend 目录）：
  python -m app.pipelines.evaluate_recommendation
"""

from collections import defaultdict
from typing import Dict, Iterable, List, Set, Tuple

import json
import random
from math import log

from .. import create_app
from ..db import db
from ..models import ContentStandard, Rating, ScenicSpot, UserProfile
from sqlalchemy import func


def _load_user_ratings(min_ratings_per_user: int = 3) -> Dict[int, List[Rating]]:
    """加载评分数据，并按 user_id -> 时间顺序排序的列表返回。"""

    ratings = Rating.query.filter_by(target_type="scenic_spot").order_by(Rating.created_at.asc()).all()
    user_ratings: Dict[int, List[Rating]] = defaultdict(list)

    for r in ratings:
        if r.user_id is None:
            continue
        user_ratings[r.user_id].append(r)

    # 过滤掉评分数量太少的用户
    return {uid: rs for uid, rs in user_ratings.items() if len(rs) >= min_ratings_per_user}


def _train_test_split(ratings: List[Rating], test_size: int = 1) -> Tuple[List[Rating], List[Rating]]:
    """将单个用户的评分按时间切分为历史（train）和近期（test）。"""

    if len(ratings) <= test_size:
        return ratings, []
    return ratings[:-test_size], ratings[-test_size:]


def _build_popularity_topn(limit: int = 100) -> List[int]:
    """根据评分表构建简单的热门景点 Top-N 列表（按评分次数和平均分）。"""

    sql = """
    SELECT target_id,
           AVG(score) AS avg_score,
           COUNT(*)   AS cnt
    FROM rating
    WHERE target_type = 'scenic_spot'
    GROUP BY target_id
    ORDER BY avg_score DESC, cnt DESC
    LIMIT :limit
    """
    rows = db.session.execute(db.text(sql), {"limit": limit}).fetchall()
    return [int(r.target_id) for r in rows]


def _build_popularity_topn_wr(limit: int = 200) -> List[int]:
    """使用 IMDb 风格 Bayesian WR 作为排序的热门 Top-N 列表。"""

    sql = """
    SELECT target_id,
           AVG(score) AS avg_score,
           COUNT(*)   AS cnt
    FROM rating
    WHERE target_type = 'scenic_spot'
    GROUP BY target_id
    """
    rows = db.session.execute(db.text(sql)).fetchall()

    try:
        C = float(db.session.query(func.avg(Rating.score)).scalar() or 0.0)
    except Exception:
        C = 0.0

    counts = [float(r.cnt or 0) for r in rows]
    counts_sorted = sorted(counts)
    if counts_sorted:
        import math

        idx = int(0.60 * (len(counts_sorted) - 1))
        m = float(counts_sorted[idx])
        if m < 1.0:
            m = 1.0
    else:
        m = 10.0

    scored = []
    for r in rows:
        try:
            R = float(r.avg_score or 0.0)
            v = float(r.cnt or 0.0)
        except (TypeError, ValueError):
            continue
        denom = v + m
        wr = (v / denom) * R + (m / denom) * C if denom > 0 else C
        scored.append((int(r.target_id), float(wr), float(R), float(v)))

    scored.sort(key=lambda x: (-x[1], -x[2], -x[3], -x[0]))
    return [sid for sid, _, __, ___ in scored[:limit]]


def _build_ml_popularity_topn(limit: int = 200) -> List[int]:
    """根据 ContentStandard.internal_rating 的 ML 受欢迎度，构建 Top-N 列表。"""

    rows = (
        ContentStandard.query.filter(
            ContentStandard.entity_type == "scenic_spot",
            ContentStandard.source_type == "internal_rating",
            ContentStandard.popularity_score.isnot(None),
        )
        .order_by(ContentStandard.popularity_score.desc())
        .limit(limit)
        .all()
    )
    return [int(r.entity_id) for r in rows]


def _build_profile_preferred_types(user_id: int) -> Set[str]:
    """读取用户画像中偏好的景点类型集合。"""

    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if profile is None or not profile.prefer_scenic_types:
        return set()
    return {t.strip() for t in profile.prefer_scenic_types.split(";") if t.strip()} | {
        t.strip() for t in profile.prefer_scenic_types.split(",") if t.strip()
    }


def _recommend_profile_based(user_id: int, candidates: List[ScenicSpot], k: int) -> List[int]:
    """基于画像偏好类型对候选景点进行排序并返回 Top-K ID。"""

    preferred_types = _build_profile_preferred_types(user_id)
    if not preferred_types:
        return [s.id for s in candidates[:k]]

    def sort_key(s: ScenicSpot):
        in_pref = 0 if (s.category and s.category in preferred_types) else 1
        avg = float(s.rating_avg) if s.rating_avg is not None else 0.0
        cnt = int(s.rating_count or 0)
        return (in_pref, -avg, -cnt, -s.id)

    sorted_candidates = sorted(candidates, key=sort_key)
    return [s.id for s in sorted_candidates[:k]]


def _load_cf_neighbors() -> Dict[int, List[int]]:
    """从 content_standard 中加载协同过滤邻居列表，返回 scenic_id -> [neighbor_id...]。"""

    rows = ContentStandard.query.filter_by(entity_type="scenic_spot", source_type="item_cf_similarity").all()
    mapping: Dict[int, List[int]] = {}
    for row in rows:
        if not row.summary:
            continue
        try:
            # summary 结构：{"neighbors": [{"id": scenic_id, "sim": similarity}, ...]}
            data = json.loads(row.summary)
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
        except Exception:
            continue
    return mapping


def _load_cf_neighbors_with_sim() -> Dict[int, List[Tuple[int, float]]]:
    rows = ContentStandard.query.filter_by(entity_type="scenic_spot", source_type="item_cf_similarity").all()
    mapping: Dict[int, List[Tuple[int, float]]] = {}
    for row in rows:
        if not row.summary:
            continue
        try:
            data = json.loads(row.summary)
            neighbors = data.get("neighbors") or []
            pairs: List[Tuple[int, float]] = []
            for item in neighbors:
                try:
                    sid = int(item.get("id"))
                    sim = float(item.get("sim", 0.0) or 0.0)
                except (TypeError, ValueError):
                    continue
                pairs.append((sid, sim))
            if pairs:
                mapping[row.entity_id] = pairs
        except Exception:
            continue
    return mapping


def _recommend_cf_based(user_history: Iterable[int], cf_neighbors: Dict[int, List[int]], k: int) -> List[int]:
    """基于 item-based CF 的简单推荐：汇总历史项目的邻居得分。"""

    scores: Dict[int, float] = defaultdict(float)
    history_set = set(user_history)

    for sid in history_set:
        neighbors = cf_neighbors.get(sid) or []
        # 简化版：只统计出现次数，不使用相似度大小
        for nid in neighbors:
            if nid in history_set:
                continue
            scores[nid] += 1.0

    if not scores:
        return []

    ranked = sorted(scores.items(), key=lambda x: (-x[1], -x[0]))
    return [sid for sid, _ in ranked[:k]]


def _normalize_scores(scores: Dict[int, float]) -> Dict[int, float]:
    if not scores:
        return {}
    values = list(scores.values())
    min_s = min(values)
    max_s = max(values)
    if max_s <= min_s:
        return {k: 1.0 for k in scores}
    denom = max_s - min_s
    return {k: (float(v) - min_s) / denom for k, v in scores.items()}


def _train_mf(
    train_triples: List[Tuple[int, int, float]],
    n_factors: int = 8,
    n_epochs: int = 20,
    lr: float = 0.02,
    reg: float = 0.05,
) -> Tuple[float, Dict[int, float], Dict[int, float], Dict[int, List[float]], Dict[int, List[float]]]:
    """基于评分矩阵的带偏置矩阵分解（Biased MF）训练。"""

    if not train_triples:
        return 0.0, {}, {}, {}, {}

    user_factors: Dict[int, List[float]] = {}
    item_factors: Dict[int, List[float]] = {}
    user_biases: Dict[int, float] = {}
    item_biases: Dict[int, float] = {}

    rating_sum = 0.0
    for _, _, r in train_triples:
        rating_sum += r
    global_mean = rating_sum / float(len(train_triples))

    def _init_vector() -> List[float]:
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


def _recommend_mf(
    user_id: int,
    history_ids: Iterable[int],
    global_mean: float,
    user_biases: Dict[int, float],
    item_biases: Dict[int, float],
    user_factors: Dict[int, List[float]],
    item_factors: Dict[int, List[float]],
    all_item_ids: Iterable[int],
    k: int,
) -> List[int]:
    pu = user_factors.get(user_id)
    if pu is None:
        return []

    bu = user_biases.get(user_id, 0.0)
    history_set = set(history_ids)
    scores: List[Tuple[int, float]] = []

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


def _recommend_hybrid(
    user_id: int,
    history_ids: Iterable[int],
    base_scores_all: Dict[int, float],
    cf_neighbors_sim: Dict[int, List[Tuple[int, float]]],
    global_mean: float,
    user_biases: Dict[int, float],
    item_biases: Dict[int, float],
    user_factors: Dict[int, List[float]],
    item_factors: Dict[int, List[float]],
    all_item_ids: Iterable[int],
    k: int,
) -> List[int]:
    history_set = set(history_ids)
    candidate_ids: List[int] = [sid for sid in all_item_ids if sid not in history_set]
    if not candidate_ids:
        return []

    base_scores: Dict[int, float] = {}
    for sid in candidate_ids:
        base_scores[sid] = base_scores_all.get(sid, 0.0)

    cf_scores: Dict[int, float] = defaultdict(float)
    for sid in history_set:
        neighbors = cf_neighbors_sim.get(sid) or []
        for nid, sim in neighbors:
            if nid in history_set:
                continue
            if nid not in base_scores:
                continue
            cf_scores[nid] += float(sim)

    mf_scores: Dict[int, float] = {}
    pu = user_factors.get(user_id)
    if pu is not None:
        bu = user_biases.get(user_id, 0.0)
        for sid in candidate_ids:
            qi = item_factors.get(sid)
            if qi is None:
                continue
            bi = item_biases.get(sid, 0.0)
            score = global_mean + bu + bi + sum(p * q for p, q in zip(pu, qi))
            mf_scores[sid] = score

    base_norm = _normalize_scores(base_scores)
    cf_norm = _normalize_scores(cf_scores) if cf_scores else {}
    mf_norm = _normalize_scores(mf_scores) if mf_scores else {}

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
        scores_list = [
            (sid, base_scores.get(sid, 0.0))
            for sid in candidate_ids
        ]
        scores_list.sort(key=lambda x: (-x[1], -x[0]))
        return [sid for sid, _ in scores_list[:k]]

    scale_base = w_base / total_weight if base_norm else 0.0
    scale_cf = w_cf / total_weight if cf_norm else 0.0
    scale_mf = w_mf / total_weight if mf_norm else 0.0

    total_scores: Dict[int, float] = {}
    for sid in candidate_ids:
        score = 0.0
        if base_norm:
            score += scale_base * base_norm.get(sid, 0.0)
        if cf_norm:
            score += scale_cf * cf_norm.get(sid, 0.0)
        if mf_norm:
            score += scale_mf * mf_norm.get(sid, 0.0)
        total_scores[sid] = score

    ranked = sorted(total_scores.items(), key=lambda x: (-x[1], -x[0]))
    return [sid for sid, _ in ranked[:k]]


def _precision_at_k(recommended: List[int], ground_truth: Set[int], k: int) -> float:
    if not recommended or not ground_truth:
        return 0.0
    topk = recommended[:k]
    hits = sum(1 for sid in topk if sid in ground_truth)
    return hits / float(k)


def _dcg_at_k(recommended: List[int], ground_truth: Set[int], k: int) -> float:
    if not recommended or not ground_truth:
        return 0.0
    dcg = 0.0
    for i, sid in enumerate(recommended[:k]):
        if sid in ground_truth:
            # 二值相关性
            denom = (i + 2)
            import math

            dcg += 1.0 / math.log2(denom)
    return dcg


def _ndcg_at_k(recommended: List[int], ground_truth: Set[int], k: int) -> float:
    dcg = _dcg_at_k(recommended, ground_truth, k)
    # IDCG：二值相关性，理想情况下把所有命中排在前面
    import math

    ideal_hits = min(len(ground_truth), k)
    if ideal_hits <= 0:
        return 0.0
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg <= 0.0:
        return 0.0
    return dcg / idcg


def evaluate(k: int = 5) -> None:
    users_ratings = _load_user_ratings(min_ratings_per_user=3)
    if not users_ratings:
        print("[WARN] 没有足够评分记录的用户，无法评估。")
        return

    popularity_topn = _build_popularity_topn(limit=200)
    popularity_topn_set = popularity_topn  # 直接当作备选列表
    popularity_wr_topn = _build_popularity_topn_wr(limit=200)
    ml_popularity_topn = _build_ml_popularity_topn(limit=200)

    # 统一使用 max_k 推荐，便于同时统计 @5 和 @10
    k5 = 5
    k10 = 10
    max_k = max(k5, k10)

    # 为画像推荐准备候选集：取评分较高的前若干景点
    scenic_candidates = ScenicSpot.query.order_by(
        ScenicSpot.rating_avg.desc(), ScenicSpot.rating_count.desc(), ScenicSpot.id.desc()
    ).limit(200).all()

    cf_neighbors = _load_cf_neighbors()
    cf_neighbors_sim = _load_cf_neighbors_with_sim()

    # 为 MF 模型准备训练数据：对每个用户做 train/test 划分
    splits: Dict[int, Tuple[List[Rating], List[Rating]]] = {}
    train_triples: List[Tuple[int, int, float]] = []
    all_item_ids_set: Set[int] = set()

    for uid, ratings in users_ratings.items():
        train, test = _train_test_split(ratings, test_size=1)
        splits[uid] = (train, test)
        for r in train:
            try:
                sid = int(r.target_id)
                score = float(r.score)
            except (TypeError, ValueError):
                continue
            train_triples.append((uid, sid, score))
            all_item_ids_set.add(sid)

    item_sum: Dict[int, float] = defaultdict(float)
    item_cnt: Dict[int, int] = defaultdict(int)
    for _, sid, score in train_triples:
        item_sum[sid] += score
        item_cnt[sid] += 1

    counts = [float(c) for c in item_cnt.values() if c > 0]
    if counts:
        counts_sorted = sorted(counts)
        idx = int(0.60 * (len(counts_sorted) - 1))
        m_wr = float(counts_sorted[idx])
        if m_wr < 1.0:
            m_wr = 1.0
    else:
        m_wr = 10.0
    try:
        C_wr = float(db.session.query(func.avg(Rating.score)).scalar() or 0.0)
    except Exception:
        C_wr = 0.0

    base_scores_all: Dict[int, float] = {}
    for sid in all_item_ids_set:
        cnt = float(item_cnt.get(sid, 0))
        if cnt <= 0:
            continue
        avg = float(item_sum[sid] / cnt)
        denom = cnt + m_wr
        base_scores_all[sid] = (cnt / denom) * avg + (m_wr / denom) * C_wr if denom > 0 else C_wr

    global_mean, user_biases, item_biases, user_factors, item_factors = _train_mf(
        train_triples
    )
    all_item_ids = sorted(all_item_ids_set)

    pop_p5: List[float] = []
    pop_p10: List[float] = []
    pop_n5: List[float] = []
    pop_n10: List[float] = []

    popwr_p5: List[float] = []
    popwr_p10: List[float] = []
    popwr_n5: List[float] = []
    popwr_n10: List[float] = []

    mlpop_p5: List[float] = []
    mlpop_p10: List[float] = []
    mlpop_n5: List[float] = []
    mlpop_n10: List[float] = []

    profile_p5: List[float] = []
    profile_p10: List[float] = []
    profile_n5: List[float] = []
    profile_n10: List[float] = []

    cf_p5: List[float] = []
    cf_p10: List[float] = []
    cf_n5: List[float] = []
    cf_n10: List[float] = []

    mf_p5: List[float] = []
    mf_p10: List[float] = []
    mf_n5: List[float] = []
    mf_n10: List[float] = []

    hybrid_p5: List[float] = []
    hybrid_p10: List[float] = []
    hybrid_n5: List[float] = []
    hybrid_n10: List[float] = []

    for uid, (train, test) in splits.items():
        if not test:
            continue
        test_ids = {int(r.target_id) for r in test}
        history_ids = [int(r.target_id) for r in train]

        # 热门推荐：与用户无关
        rec_pop = popularity_topn_set[:max_k]
        pop_p5.append(_precision_at_k(rec_pop, test_ids, k5))
        pop_p10.append(_precision_at_k(rec_pop, test_ids, k10))
        pop_n5.append(_ndcg_at_k(rec_pop, test_ids, k5))
        pop_n10.append(_ndcg_at_k(rec_pop, test_ids, k10))

        # Popular-WR：IMDb 风格 WR 排序
        rec_popwr = popularity_wr_topn[:max_k]
        popwr_p5.append(_precision_at_k(rec_popwr, test_ids, k5))
        popwr_p10.append(_precision_at_k(rec_popwr, test_ids, k10))
        popwr_n5.append(_ndcg_at_k(rec_popwr, test_ids, k5))
        popwr_n10.append(_ndcg_at_k(rec_popwr, test_ids, k10))

        # ML-Popular（基于 ContentStandard.internal_rating.popularity_score）
        rec_mlpop = ml_popularity_topn[:max_k]
        mlpop_p5.append(_precision_at_k(rec_mlpop, test_ids, k5))
        mlpop_p10.append(_precision_at_k(rec_mlpop, test_ids, k10))
        mlpop_n5.append(_ndcg_at_k(rec_mlpop, test_ids, k5))
        mlpop_n10.append(_ndcg_at_k(rec_mlpop, test_ids, k10))

        # 画像推荐
        rec_profile = _recommend_profile_based(uid, scenic_candidates, max_k)
        profile_p5.append(_precision_at_k(rec_profile, test_ids, k5))
        profile_p10.append(_precision_at_k(rec_profile, test_ids, k10))
        profile_n5.append(_ndcg_at_k(rec_profile, test_ids, k5))
        profile_n10.append(_ndcg_at_k(rec_profile, test_ids, k10))

        # 协同过滤推荐
        rec_cf = _recommend_cf_based(history_ids, cf_neighbors, max_k)
        if rec_cf:
            cf_p5.append(_precision_at_k(rec_cf, test_ids, k5))
            cf_p10.append(_precision_at_k(rec_cf, test_ids, k10))
            cf_n5.append(_ndcg_at_k(rec_cf, test_ids, k5))
            cf_n10.append(_ndcg_at_k(rec_cf, test_ids, k10))

        # 矩阵分解推荐
        rec_mf = _recommend_mf(
            uid,
            history_ids,
            global_mean,
            user_biases,
            item_biases,
            user_factors,
            item_factors,
            all_item_ids,
            max_k,
        )
        if rec_mf:
            mf_p5.append(_precision_at_k(rec_mf, test_ids, k5))
            mf_p10.append(_precision_at_k(rec_mf, test_ids, k10))
            mf_n5.append(_ndcg_at_k(rec_mf, test_ids, k5))
            mf_n10.append(_ndcg_at_k(rec_mf, test_ids, k10))

        # Hybrid 混合推荐（热门基线 + CF + MF）
        rec_hybrid = _recommend_hybrid(
            uid,
            history_ids,
            base_scores_all,
            cf_neighbors_sim,
            global_mean,
            user_biases,
            item_biases,
            user_factors,
            item_factors,
            all_item_ids,
            max_k,
        )
        if rec_hybrid:
            hybrid_p5.append(_precision_at_k(rec_hybrid, test_ids, k5))
            hybrid_p10.append(_precision_at_k(rec_hybrid, test_ids, k10))
            hybrid_n5.append(_ndcg_at_k(rec_hybrid, test_ids, k5))
            hybrid_n10.append(_ndcg_at_k(rec_hybrid, test_ids, k10))

    def _avg(xs: List[float]) -> float:
        return sum(xs) / len(xs) if xs else 0.0

    print("=== 推荐效果评估 (Precision@K / NDCG@K) ===")
    print("用户数量:", len(users_ratings))
    def _fmt(p5, p10, n5, n10):
        return "P@5={:.4f} | P@10={:.4f} | NDCG@5={:.4f} | NDCG@10={:.4f}".format(
            _avg(p5), _avg(p10), _avg(n5), _avg(n10)
        )
    print("热门推荐:", _fmt(pop_p5, pop_p10, pop_n5, pop_n10))
    print("热门推荐-WR:", _fmt(popwr_p5, popwr_p10, popwr_n5, popwr_n10))
    print("ML-Popular:", _fmt(mlpop_p5, mlpop_p10, mlpop_n5, mlpop_n10))
    print("画像推荐:", _fmt(profile_p5, profile_p10, profile_n5, profile_n10))
    print("协同过滤(仅对有 CF 推荐的用户统计):", _fmt(cf_p5, cf_p10, cf_n5, cf_n10))
    print("MF 矩阵分解(仅对有 MF 推荐的用户统计):", _fmt(mf_p5, mf_p10, mf_n5, mf_n10))
    print("Hybrid 混合推荐(CF+MF+热门基线):", _fmt(hybrid_p5, hybrid_p10, hybrid_n5, hybrid_n10))


def main() -> None:
    app = create_app()
    with app.app_context():
        evaluate(k=5)


if __name__ == "__main__":
    main()
