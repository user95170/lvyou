from __future__ import annotations

import argparse
import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

from sqlalchemy import func

from .. import create_app
from ..db import db
from ..models import FoodPlace, Hotel, Rating, ScenicSpot, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


ALLOWED_TARGET_TYPES = {"scenic_spot", "hotel", "food_place"}


@dataclass
class RatingRow:
    user_id: Optional[int]
    username: Optional[str]
    target_type: str
    target_id: int
    score: int
    comment: Optional[str]
    created_at: Optional[datetime]


def _parse_datetime(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None

    # 优先尝试 ISO 格式，例如 2025-05-01T10:20:30
    try:
        return datetime.fromisoformat(text)
    except Exception:  # noqa: BLE001
        pass

    # 其次尝试常见日期格式
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:  # noqa: BLE001
            continue

    logger.warning("无法解析 created_at 字段，使用默认时间: %s", text)
    return None


def _load_csv_rows(csv_path: Path, encoding: str = "utf-8-sig") -> List[RatingRow]:
    if not csv_path.exists():
        raise FileNotFoundError(f"找不到评分导入文件: {csv_path}")

    logger.info("开始从 CSV 加载评分数据: %s", csv_path)

    rows: List[RatingRow] = []

    with csv_path.open("r", encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise RuntimeError("CSV 文件缺少表头行，无法导入评分")

        for line_num, raw in enumerate(reader, start=2):
            # 支持的列名：user_id, username, target_type, target_id, score, comment, created_at
            user_id_val = (raw.get("user_id") or "").strip()
            username = (raw.get("username") or "").strip() or None
            target_type = (raw.get("target_type") or "").strip()
            target_id_val = (raw.get("target_id") or "").strip()
            score_val = (raw.get("score") or "").strip()
            comment = (raw.get("comment") or "").strip() or None
            created_at = _parse_datetime(raw.get("created_at"))

            if not target_type or not target_id_val or not score_val:
                logger.warning("第 %d 行缺少 target_type/target_id/score，已跳过", line_num)
                continue

            if target_type not in ALLOWED_TARGET_TYPES:
                logger.warning("第 %d 行 target_type 不支持: %s", line_num, target_type)
                continue

            try:
                target_id = int(target_id_val)
                score = int(score_val)
            except ValueError:
                logger.warning("第 %d 行 target_id/score 解析失败: %s / %s", line_num, target_id_val, score_val)
                continue

            if score < 1 or score > 5:
                logger.warning("第 %d 行 score 超出范围 [1,5]: %s", line_num, score)
                continue

            user_id: Optional[int] = None
            if user_id_val:
                try:
                    user_id = int(user_id_val)
                except ValueError:
                    logger.warning("第 %d 行 user_id 解析失败: %s", line_num, user_id_val)

            rows.append(
                RatingRow(
                    user_id=user_id,
                    username=username,
                    target_type=target_type,
                    target_id=target_id,
                    score=score,
                    comment=comment,
                    created_at=created_at,
                )
            )

    logger.info("CSV 加载完成，共 %d 条候选记录", len(rows))
    return rows


def _resolve_user(row: RatingRow) -> Optional[User]:
    """根据 user_id 或 username 解析/创建用户。

    - 若提供 user_id 且用户存在，则直接使用；
    - 若提供 user_id 但不存在，且提供 username，则按 username 查找或创建新用户；
    - 若仅提供 username，则按 username 查找或创建；
    - 若两者都缺失，则返回 None。
    """

    if row.user_id is not None:
        user = User.query.get(row.user_id)
        if user is not None:
            return user

    if not row.username:
        return None

    user = User.query.filter_by(username=row.username).first()
    if user is not None:
        return user

    # 创建新用户记录，密码使用随机占位符（线下导入用，不暴露给外部）
    user = User(username=row.username)
    user.set_password(f"import_{row.username}_default")
    db.session.add(user)
    db.session.flush()  # 获取自增 id
    logger.info("创建新用户用于评分导入: id=%s, username=%s", user.id, user.username)
    return user


def _get_target(row: RatingRow):
    if row.target_type == "scenic_spot":
        return ScenicSpot.query.get(row.target_id)
    if row.target_type == "hotel":
        return Hotel.query.get(row.target_id)
    if row.target_type == "food_place":
        return FoodPlace.query.get(row.target_id)
    return None


def _bulk_import_ratings(rows: Iterable[RatingRow]) -> Set[Tuple[str, int]]:
    """将 RatingRow 批量写入 rating 表，并返回受影响的目标集合。"""

    affected: Set[Tuple[str, int]] = set()

    for row in rows:
        user = _resolve_user(row)
        if user is None:
            logger.warning(
                "跳过一条评分：无法解析用户（user_id=%s, username=%s）",
                row.user_id,
                row.username,
            )
            continue

        target = _get_target(row)
        if target is None:
            logger.warning(
                "跳过一条评分：未找到目标实体（type=%s, id=%s）",
                row.target_type,
                row.target_id,
            )
            continue

        created_at = row.created_at or _utcnow()

        rating = Rating(
            user_id=user.id,
            target_type=row.target_type,
            target_id=row.target_id,
            score=row.score,
            comment=row.comment,
            created_at=created_at,
        )
        db.session.add(rating)

        affected.add((row.target_type, row.target_id))

    db.session.flush()
    return affected


def _update_aggregates_for_targets(affected: Set[Tuple[str, int]]) -> None:
    """根据 rating 表中数据，为受影响的目标更新 rating_avg 与 rating_count。"""

    if not affected:
        logger.info("本次导入未产生任何有效评分，不需要更新聚合统计")
        return

    # 按 target_type 分组聚合，避免逐条请求数据库
    type_to_ids: dict[str, Set[int]] = {}
    for ttype, tid in affected:
        type_to_ids.setdefault(ttype, set()).add(tid)

    for ttype, ids in type_to_ids.items():
        if not ids:
            continue

        rows = (
            db.session.query(
                Rating.target_id,
                func.avg(Rating.score),
                func.count(Rating.id),
            )
            .filter(
                Rating.target_type == ttype,
                Rating.target_id.in_(ids),
            )
            .group_by(Rating.target_id)
            .all()
        )

        stats = {int(tid): (float(avg), int(cnt)) for tid, avg, cnt in rows}

        for tid in ids:
            avg_score, cnt = stats.get(tid, (None, 0))

            if ttype == "scenic_spot":
                obj = ScenicSpot.query.get(tid)
            elif ttype == "hotel":
                obj = Hotel.query.get(tid)
            elif ttype == "food_place":
                obj = FoodPlace.query.get(tid)
            else:
                obj = None

            if obj is None:
                continue

            obj.rating_avg = avg_score
            obj.rating_count = cnt

        logger.info(
            "更新聚合统计：type=%s, 受影响实体=%d 个", ttype, len(ids)
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "从 CSV 文件批量导入真实评分数据到 rating 表，并更新景点/酒店/美食的 "
            "rating_avg 与 rating_count 聚合字段。"
        )
    )

    default_csv = Path(__file__).resolve().parents[2] / "data" / "ratings_import.csv"

    parser.add_argument(
        "--csv",
        type=Path,
        default=default_csv,
        help=(
            "评分导入 CSV 文件路径，默认：项目根目录 data/ratings_import.csv。 "
            "需要包含表头：user_id, username, target_type, target_id, score, comment, created_at（部分可选）。"
        ),
    )

    args = parser.parse_args()
    csv_path: Path = args.csv

    app = create_app()
    with app.app_context():
        rows = _load_csv_rows(csv_path)
        if not rows:
            logger.warning("未从 CSV 中加载到有效记录，本次导入结束")
            return

        affected = _bulk_import_ratings(rows)
        _update_aggregates_for_targets(affected)

        db.session.commit()
        logger.info("评分导入与聚合更新已完成，提交事务。")


if __name__ == "__main__":
    main()
