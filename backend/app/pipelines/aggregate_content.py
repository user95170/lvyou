from __future__ import annotations

import logging
import pickle
import json
from datetime import datetime, timezone
from math import log, log1p
from pathlib import Path

from .. import create_app
from ..db import db
from ..models import ContentStandard, FoodPlace, Hotel, ScenicSpot


logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "popularity_model.pkl"
MODEL_META_PATH = MODEL_DIR / "popularity_model.meta.json"
POPULARITY_MODEL = None
POPULARITY_META = None


def _calc_popularity(rating_avg, rating_count) -> float | None:
    """根据评分和评分人数计算简单的受欢迎度分数。

    当前策略：rating_avg * (1 + ln(1 + rating_count))
    若评分为空，则返回 None。
    """

    if rating_avg is None or rating_count is None:
        return None

    try:
        rating_avg_f = float(rating_avg)
        rating_count_i = int(rating_count)
    except (TypeError, ValueError):
        return None

    if rating_count_i < 0:
        rating_count_i = 0

    return rating_avg_f * (1.0 + log(1.0 + rating_count_i))


def _load_popularity_model():
    """懒加载受欢迎度回归模型。

    如果模型文件不存在或加载失败，将抛出 RuntimeError，提示先完成模型训练。
    """

    global POPULARITY_MODEL

    if POPULARITY_MODEL is not None:
        return POPULARITY_MODEL

    if not MODEL_PATH.exists():
        msg = (
            "受欢迎度模型文件不存在，请先运行 train_popularity_model.py 训练模型: "
            f"{MODEL_PATH}"
        )
        logger.error(msg)
        raise RuntimeError(msg)

    try:
        with open(MODEL_PATH, "rb") as f:
            POPULARITY_MODEL = pickle.load(f)
        logger.info("已加载受欢迎度模型: %s", MODEL_PATH)
        # 读取元信息（如是否启用对数变换）
        global POPULARITY_META
        POPULARITY_META = None
        if MODEL_META_PATH.exists():
            try:
                with open(MODEL_META_PATH, "r", encoding="utf-8") as mf:
                    POPULARITY_META = json.load(mf)
            except Exception:
                POPULARITY_META = None
    except Exception as exc:  # noqa: BLE001
        msg = f"加载受欢迎度模型失败，请检查模型文件: {exc}"
        logger.error(msg)
        POPULARITY_MODEL = None
        raise RuntimeError(msg)

    return POPULARITY_MODEL


def _parse_summary(summary: str) -> dict:
    if not summary:
        return {}
    try:
        return json.loads(summary)
    except Exception:
        try:
            return json.loads(summary.replace("'", '"'))
        except Exception:
            return {}


def _extract_ota_features(entity_type: str, entity_id: int) -> tuple[float, float]:
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
    payload = _parse_summary(row.summary)

    def _get_float(keys: list[str], default: float = 0.0) -> float:
        for k in keys:
            v = payload.get(k)
            if v is None:
                continue
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
        return float(default)

    def _get_int_as_float(keys: list[str], default: float = 0.0) -> float:
        for k in keys:
            v = payload.get(k)
            if v is None:
                continue
            try:
                return float(int(v))
            except (TypeError, ValueError):
                continue
        return float(default)

    ota_rating = _get_float(["external_rating", "rating"], default=0.0)
    ota_reviews = _get_int_as_float(["review_count", "external_review_count"], default=0.0)
    return ota_rating, ota_reviews


def _extract_social_features(entity_type: str, entity_id: int) -> tuple[float, float]:
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
    payload = _parse_summary(row.summary)

    def _get_float(keys: list[str], default: float = 0.0) -> float:
        for k in keys:
            v = payload.get(k)
            if v is None:
                continue
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
        return float(default)

    def _get_int_as_float(keys: list[str], default: float = 0.0) -> float:
        for k in keys:
            v = payload.get(k)
            if v is None:
                continue
            try:
                return float(int(v))
            except (TypeError, ValueError):
                continue
        return float(default)

    interactions = _get_int_as_float(["interaction_sum", "interactions", "social_interactions"], default=0.0)
    sentiment = _get_float(["sentiment_avg", "sentiment"], default=0.0)
    return interactions, sentiment


def _predict_popularity_with_model(entity_type: str, entity_id: int, rating_avg, rating_count) -> float | None:
    if rating_avg is None or rating_count is None:
        return None

    try:
        model = _load_popularity_model()
    except RuntimeError:
        # 模型缺失时退回到简单的评分×log(评论数)公式，保证可用性
        return _calc_popularity(rating_avg, rating_count)

    try:
        avg = float(rating_avg)
        cnt = float(rating_count)
    except (TypeError, ValueError):
        return None

    ota_rating, ota_reviews = _extract_ota_features(entity_type, entity_id)
    social_interactions, social_sentiment = _extract_social_features(entity_type, entity_id)

    # 与训练保持一致的特征工程：若模型元信息指示启用对数变换，则对计数特征做 log1p
    log_transform = False
    try:
        if POPULARITY_META and bool(POPULARITY_META.get("log_transform")):
            log_transform = True
    except Exception:
        log_transform = False

    cnt_f = log1p(float(cnt)) if log_transform else float(cnt)
    ota_reviews_f = log1p(float(ota_reviews or 0.0)) if log_transform else float(ota_reviews or 0.0)
    social_interactions_f = (
        log1p(float(social_interactions or 0.0)) if log_transform else float(social_interactions or 0.0)
    )

    try:
        y_pred = model.predict(
            [
                [
                    avg,
                    cnt_f,
                    float(ota_rating or 0.0),
                    ota_reviews_f,
                    social_interactions_f,
                    float(social_sentiment or 0.0),
                ]
            ]
        )
        return float(y_pred[0])
    except Exception as exc:  # noqa: BLE001
        msg = f"使用受欢迎度模型预测失败: {exc}"
        logger.error(msg)
        # 预测失败时也回退到基础公式
        return _calc_popularity(rating_avg, rating_count)


def _upsert_content(entity_type: str, entity_id: int, title: str, popularity_score: float | None) -> None:
    """向 content_standard 中插入或更新一条记录。"""

    row = ContentStandard.query.filter_by(
        entity_type=entity_type,
        entity_id=entity_id,
        source_type="internal_rating",
    ).first()

    if row is None:
        row = ContentStandard(
            entity_type=entity_type,
            entity_id=entity_id,
            source_type="internal_rating",
        )
        db.session.add(row)

    row.title = title
    row.popularity_score = popularity_score
    row.last_update = datetime.now(timezone.utc)


def aggregate_all() -> None:
    """聚合景点、酒店、美食的评分信息到 content_standard 表。"""

    # 景点
    for spot in ScenicSpot.query.all():
        popularity = _predict_popularity_with_model(
            "scenic_spot",
            spot.id,
            spot.rating_avg,
            spot.rating_count,
        )
        _upsert_content("scenic_spot", spot.id, spot.name, popularity)

    # 酒店
    for hotel in Hotel.query.all():
        popularity = _predict_popularity_with_model(
            "hotel",
            hotel.id,
            hotel.rating_avg,
            hotel.rating_count,
        )
        _upsert_content("hotel", hotel.id, hotel.name, popularity)

    # 美食
    for food in FoodPlace.query.all():
        popularity = _predict_popularity_with_model(
            "food_place",
            food.id,
            food.rating_avg,
            food.rating_count,
        )
        _upsert_content("food_place", food.id, food.name, popularity)

    db.session.commit()


def main() -> None:
    app = create_app()
    with app.app_context():
        aggregate_all()


if __name__ == "__main__":
    main()
