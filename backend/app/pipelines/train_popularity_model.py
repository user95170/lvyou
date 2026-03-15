from __future__ import annotations

import logging
import pickle
from pathlib import Path
import argparse
import json
from math import log1p
from typing import Dict, List, Tuple

from sklearn.ensemble import RandomForestRegressor
try:  # 优先使用 LightGBM（若环境可用）
    from lightgbm import LGBMRegressor  # type: ignore
except Exception:  # noqa: BLE001
    LGBMRegressor = None  # type: ignore

from .. import create_app
from ..db import db
from ..models import ScenicSpot, Hotel, FoodPlace, ContentStandard, Rating
from sqlalchemy import func
from .aggregate_content import _calc_popularity

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "popularity_model.pkl"


def _collect_training_samples(
    w_base: float = 1.0,
    w_ota: float = 1.0,
    w_social_heat: float = 1.0,
    w_sentiment: float = 2.0,
    m_percentile: float = 0.60,
    log_transform: bool = False,
    social_percentile: float = 0.95,
) -> Tuple[List[List[float]], List[float]]:
    """从现有评分统计 + 多源聚合中收集受欢迎度模型的训练样本（多源特征版）。

    特征：
      - rating_avg（内部评分均值，float）
      - rating_count（内部评分次数，float）
      - ota_rating（OTA 平均评分，float，来自 ContentStandard.source_type in {"ota_stats","ota"}）
      - ota_review_count（OTA 评论数，float）
      - social_interactions（社交媒体互动量，float，来自 source_type="social_media"）
      - social_sentiment（社交媒体情感均值，float）

    标签：
      - 仍使用旧版 `_calc_popularity(rating_avg, rating_count)` 作为代理目标，
        以保证在缺少“更真实标签”时模型可训练与落地；未来可替换为更合理的目标定义。
    """

    X: List[List[float]] = []
    y: List[float] = []

    # 计算 IMDb 风格 WR 的全局参数：全局均分 C 与最小票数阈值 m
    def _compute_percentile(values: List[float], q: float) -> float:
        if not values:
            return 0.0
        vs = sorted(values)
        q = max(0.0, min(1.0, float(q)))
        idx = int(q * (len(vs) - 1))
        return float(vs[idx])

    def _collect_global_params() -> Tuple[float, float]:
        try:
            c_val = db.session.query(func.avg(Rating.score)).scalar() or 0.0
        except Exception:
            c_val = 0.0

        counts: List[float] = []
        for spot in ScenicSpot.query.with_entities(ScenicSpot.rating_count).all():
            try:
                counts.append(float(spot.rating_count or 0))
            except Exception:
                continue
        for hotel in Hotel.query.with_entities(Hotel.rating_count).all():
            try:
                counts.append(float(hotel.rating_count or 0))
            except Exception:
                continue
        for food in FoodPlace.query.with_entities(FoodPlace.rating_count).all():
            try:
                counts.append(float(food.rating_count or 0))
            except Exception:
                continue

        m_val = _compute_percentile(counts, float(m_percentile)) if counts else 10.0
        if m_val < 1.0:
            m_val = 1.0
        return float(c_val), float(m_val)

    C_global, m_min_votes = _collect_global_params()

    def _compute_social_clip(p: float) -> float:
        # 收集 social_interactions 的全局分布，用于裁剪与归一化
        vals: List[float] = []
        try:
            rows = (
                ContentStandard.query.with_entities(ContentStandard.summary)
                .filter(ContentStandard.source_type == "social_media")
                .all()
            )
            for (summary,) in rows:
                if not summary:
                    continue
                try:
                    payload = summary
                    if isinstance(payload, str):
                        try:
                            payload = json.loads(payload)
                        except Exception:
                            payload = json.loads(payload.replace("'", '"'))
                    v = payload.get("interaction_sum") or payload.get("interactions") or payload.get("social_interactions")
                    if v is None:
                        continue
                    fv = float(int(v))
                    if fv > 0:
                        vals.append(fv)
                except Exception:
                    continue
        except Exception:
            vals = []
        clip = _compute_percentile(vals, float(p)) if vals else 10000.0
        if clip <= 1.0:
            clip = 1000.0
        return float(clip)

    social_clip = _compute_social_clip(float(social_percentile))

    def _extract_ota_features(entity_type: str, entity_id: int) -> Tuple[float, float]:
        """从 ContentStandard 提取 OTA 相关特征，兼容 ota_stats/ota 两种来源与字段名差异。"""

        row = (
            ContentStandard.query.filter(
                ContentStandard.entity_type == entity_type,
                ContentStandard.entity_id == entity_id,
                ContentStandard.source_type.in_(["ota_stats", "ota"]),
            )
            .order_by(ContentStandard.last_update.desc())
            .first()
        )
        if not row or not row.summary:
            return 0.0, 0.0

        try:
            payload = row.summary
            if isinstance(payload, str):
                import json

                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = json.loads(payload.replace("'", '"'))
        except Exception:
            return 0.0, 0.0

        def _get_float(*keys: str, default: float = 0.0) -> float:
            for k in keys:
                v = payload.get(k)
                if v is None:
                    continue
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
            return float(default)

        def _get_int_as_float(*keys: str, default: float = 0.0) -> float:
            for k in keys:
                v = payload.get(k)
                if v is None:
                    continue
                try:
                    return float(int(v))
                except (TypeError, ValueError):
                    continue
            return float(default)

        ota_rating = _get_float("external_rating", "rating", default=0.0)
        ota_reviews = _get_int_as_float("review_count", "external_review_count", default=0.0)
        return ota_rating, ota_reviews

    def _extract_social_features(entity_type: str, entity_id: int) -> Tuple[float, float]:
        """从 ContentStandard 提取社交媒体相关特征。"""

        row = (
            ContentStandard.query.filter(
                ContentStandard.entity_type == entity_type,
                ContentStandard.entity_id == entity_id,
                ContentStandard.source_type == "social_media",
            )
            .order_by(ContentStandard.last_update.desc())
            .first()
        )
        if not row or not row.summary:
            return 0.0, 0.0

        try:
            payload = row.summary
            if isinstance(payload, str):
                import json

                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = json.loads(payload.replace("'", '"'))
        except Exception:
            return 0.0, 0.0

        def _get_float(*keys: str, default: float = 0.0) -> float:
            for k in keys:
                v = payload.get(k)
                if v is None:
                    continue
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
            return float(default)

        def _get_int_as_float(*keys: str, default: float = 0.0) -> float:
            for k in keys:
                v = payload.get(k)
                if v is None:
                    continue
                try:
                    return float(int(v))
                except (TypeError, ValueError):
                    continue
            return float(default)

        interactions = _get_int_as_float("interaction_sum", "interactions", "social_interactions", default=0.0)
        sentiment = _get_float("sentiment_avg", "sentiment", default=0.0)
        return interactions, sentiment

    def _add_entity(entity_type: str, rating_avg, rating_count, entity_id: int) -> None:
        """收集单个实体的训练样本（多源特征 + 多源组合标签）。"""

        # 特征准备
        try:
            avg = float(rating_avg)
        except (TypeError, ValueError):
            avg = 0.0
        try:
            cnt = float(rating_count)
        except (TypeError, ValueError):
            cnt = 0.0

        ota_rating, ota_reviews = _extract_ota_features(entity_type, entity_id)
        social_interactions, social_sentiment = _extract_social_features(entity_type, entity_id)

        # 组合标签：内部基线改用 IMDb 风格 Bayesian WR
        # WR = (v/(v+m)) * R + (m/(v+m)) * C
        R = float(avg)
        v = max(float(cnt), 0.0)
        m = float(m_min_votes)
        C = float(C_global)
        denom = v + m
        base_pop = (v / denom) * R + (m / denom) * C if denom > 0 else C
        # 采用 log1p + 分位裁剪归一化的 social_heat ∈ [0,1]
        try:
            inter = max(float(social_interactions or 0.0), 0.0)
        except Exception:
            inter = 0.0
        denom = log1p(float(social_clip)) if float(social_clip) > 0 else 1.0
        social_heat = (log1p(inter) / denom) if denom > 0 else 0.0
        if social_heat < 0.0:
            social_heat = 0.0
        if social_heat > 1.0:
            social_heat = 1.0
        label = (
            w_base * float(base_pop)
            + w_ota * float(ota_rating or 0.0)
            + w_social_heat * social_heat
            + w_sentiment * float(social_sentiment or 0.0)
        )

        # 若所有信号均为 0，则跳过该样本，避免噪声
        if (
            (base_pop == 0.0)
            and (float(ota_rating or 0.0) == 0.0)
            and (social_heat == 0.0)
            and (float(social_sentiment or 0.0) == 0.0)
        ):
            return

        # 可选：对计数型特征进行对数变换以压缩长尾
        cnt_f = log1p(float(cnt)) if log_transform else float(cnt)
        ota_reviews_f = log1p(float(ota_reviews or 0.0)) if log_transform else float(ota_reviews or 0.0)
        social_interactions_f = log1p(float(social_interactions or 0.0)) if log_transform else float(social_interactions or 0.0)

        X.append([
            float(avg),
            cnt_f,
            float(ota_rating or 0.0),
            ota_reviews_f,
            social_interactions_f,
            float(social_sentiment or 0.0),
        ])
        y.append(float(label))

    # 景点
    for spot in ScenicSpot.query.all():
        _add_entity("scenic_spot", spot.rating_avg, spot.rating_count, spot.id)

    # 酒店
    for hotel in Hotel.query.all():
        _add_entity("hotel", hotel.rating_avg, hotel.rating_count, hotel.id)

    # 美食
    for food in FoodPlace.query.all():
        _add_entity("food_place", food.rating_avg, food.rating_count, food.id)

    return X, y


def train_and_save_model(
    w_base: float = 1.0,
    w_ota: float = 1.0,
    w_social_heat: float = 1.0,
    w_sentiment: float = 2.0,
    m_percentile: float = 0.60,
    log_transform: bool = False,
    social_percentile: float = 0.95,
) -> None:
    """训练受欢迎度回归模型并保存到磁盘。

    当前实现：
      - 使用 RandomForestRegressor 拟合旧版 popularity 公式，后续可扩展更多特征。
    """

    X, y = _collect_training_samples(
        w_base=w_base,
        w_ota=w_ota,
        w_social_heat=w_social_heat,
        w_sentiment=w_sentiment,
        m_percentile=m_percentile,
        log_transform=log_transform,
        social_percentile=social_percentile,
    )
    n_samples = len(y)

    if n_samples == 0:
        msg = "没有可用的训练样本，无法训练受欢迎度模型，请先收集至少一条评分数据"
        logger.error(msg)
        raise RuntimeError(msg)

    if n_samples < 20:
        logger.warning(
            "可用训练样本不足 20 条，将在样本较少的情况下训练受欢迎度模型（当前样本数: %d）",
            n_samples,
        )

    logger.info("开始训练受欢迎度模型（多源特征），样本数: %d", n_samples)

    model = None
    if LGBMRegressor is not None:
        try:
            # 为 6 个正向特征添加单调约束：rating_avg、rating_count、ota_rating、ota_review_count、social_interactions、social_sentiment
            model = LGBMRegressor(
                n_estimators=400,
                learning_rate=0.05,
                num_leaves=31,
                random_state=42,
                n_jobs=-1,
                monotone_constraints=[1, 1, 1, 1, 1, 1],
            )
        except Exception:  # 某些版本不支持该参数时，回退为无约束的 LGBM
            try:
                model = LGBMRegressor(
                    n_estimators=400,
                    learning_rate=0.05,
                    num_leaves=31,
                    random_state=42,
                    n_jobs=-1,
                )
            except Exception:
                model = None

    if model is None:
        model = RandomForestRegressor(
            n_estimators=100,
            random_state=42,
            n_jobs=-1,
        )
    model.fit(X, y)

    score = model.score(X, y)
    logger.info("受欢迎度模型训练完成，训练集 R^2 = %.4f", score)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    logger.info("受欢迎度模型已保存至: %s", MODEL_PATH)

    # 保存模型元信息，供线上聚合时一致的特征变换
    meta = {
        "log_transform": bool(log_transform),
        "w_base": float(w_base),
        "w_ota": float(w_ota),
        "w_social_heat": float(w_social_heat),
        "w_sentiment": float(w_sentiment),
        "m_percentile": float(m_percentile),
        "social_percentile": float(social_percentile),
        "feature_order": [
            "rating_avg",
            "rating_count",
            "ota_rating",
            "ota_review_count",
            "social_interactions",
            "social_sentiment",
        ],
    }
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "popularity_model.meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def main() -> None:
    app = create_app()
    with app.app_context():
        parser = argparse.ArgumentParser(description="Train popularity model (multi-source label with WR base)")
        parser.add_argument("--w-base", type=float, default=1.0, dest="w_base")
        parser.add_argument("--w-ota", type=float, default=1.0, dest="w_ota")
        parser.add_argument("--w-social-heat", type=float, default=1.0, dest="w_social_heat")
        parser.add_argument("--w-sentiment", type=float, default=2.0, dest="w_sentiment")
        parser.add_argument("--m-percentile", type=float, default=0.60, dest="m_percentile")
        parser.add_argument("--log-transform", action="store_true", dest="log_transform", help="Apply log1p to count features (rating_count, ota_review_count, social_interactions)")
        parser.add_argument("--social-percentile", type=float, default=0.95, dest="social_percentile", help="Percentile for social_heat clipping in label (e.g., 0.95)")
        args = parser.parse_args()

        logger.info(
            "Training with weights: w_base=%.3f w_ota=%.3f w_social_heat=%.3f w_sentiment=%.3f m_percentile=%.2f log_transform=%s",
            args.w_base,
            args.w_ota,
            args.w_social_heat,
            args.w_sentiment,
            args.m_percentile,
            args.log_transform,
        )
        train_and_save_model(
            w_base=args.w_base,
            w_ota=args.w_ota,
            w_social_heat=args.w_social_heat,
            w_sentiment=args.w_sentiment,
            m_percentile=args.m_percentile,
            log_transform=args.log_transform,
            social_percentile=args.social_percentile,
        )


if __name__ == "__main__":
    main()
