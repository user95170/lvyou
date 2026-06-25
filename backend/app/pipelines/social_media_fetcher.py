from __future__ import annotations

"""社交媒体与 UGC 离线数据导入脚本。

本模块不直接抓取社交平台页面或调用平台 API。它只读取已经合规导出的 CSV 数据，
并将景点维度的互动量、帖子量和情感分汇总到 content_standard 表。
"""

import os
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

from .. import create_app
from ..db import db
from ..models import ContentStandard, ScenicSpot

DEFAULT_SOCIAL_CSV_NAME = "social_media_scenic_sample.csv"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_social_csv_path(path: str | Path | None = None) -> Path:
    if path:
        return Path(path)
    if os.getenv("SOCIAL_MEDIA_CSV"):
        return Path(os.environ["SOCIAL_MEDIA_CSV"])
    data_dir = Path(os.getenv("SOCIAL_MEDIA_DATA_DIR", str(_project_root() / "data")))
    return data_dir / DEFAULT_SOCIAL_CSV_NAME


def load_scenic_mapping() -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    spots = ScenicSpot.query.all()
    for s in spots:
        if not s.name:
            continue
        mapping[s.name.strip()] = s.id
    return mapping


def read_social_csv(path: Path) -> List[dict]:
    if not path.exists():
        return []
    rows: List[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def load_posts_for_keywords(
    keywords: Iterable[str],
    csv_path: str | Path | None = None,
) -> List[dict]:
    """从本地 CSV 加载与关键词相关的 UGC 记录。

    CSV 每条记录建议包含：
      - keyword: 关联的关键词
      - title / text: 文本内容
      - interactions: 互动量（点赞+评论+转发等）
      - sentiment: 情感得分
      - scenic_name: 匹配到的内部景点名称
    """

    rows = read_social_csv(resolve_social_csv_path(csv_path))
    normalized_keywords = {str(k).strip() for k in keywords if str(k).strip()}
    if not normalized_keywords:
        return rows

    matched: List[dict] = []
    for row in rows:
        searchable = " ".join(
            str(row.get(field) or "")
            for field in ("keyword", "scenic_name", "name", "title", "text")
        )
        if any(keyword in searchable for keyword in normalized_keywords):
            matched.append(row)
    return matched


def fetch_posts_for_keywords(keywords: Iterable[str]) -> List[dict]:
    """兼容旧调用名：实际执行本地 CSV 加载，不进行网络采集。"""

    return load_posts_for_keywords(keywords)


def aggregate_to_content_standard(records: List[dict]) -> int:
    """将社交媒体记录聚合到 content_standard 表。

    实际使用中，应先将 scenic_name 映射到内部 scenic_spot.id，
    然后对同一景点的互动量、情感得分等做汇总，写入：
      - entity_type = "scenic_spot"
      - source_type = "social_media"
      - summary: {"window_days": 7, "post_count": ..., "interaction_sum": ..., "sentiment_avg": ...}
    """

    if not records:
        return 0

    mapping = load_scenic_mapping()
    if not mapping:
        return 0

    agg = defaultdict(
        lambda: {
            "post_count": 0,
            "interaction_sum": 0,
            "sentiment_sum": 0.0,
            "sentiment_count": 0,
            "window_days": 0,
        }
    )

    for r in records:
        scenic_name = (
            r.get("scenic_name") or r.get("name") or r.get("keyword") or ""
        ).strip()
        if not scenic_name:
            continue
        scenic_id = mapping.get(scenic_name)
        if not scenic_id:
            continue

        try:
            post_count = int(r.get("post_count", 0) or 0)
        except (TypeError, ValueError):
            post_count = 0

        try:
            interactions = int(
                r.get("interaction_sum", 0)
                or r.get("interactions", 0)
                or 0
            )
        except (TypeError, ValueError):
            interactions = 0

        try:
            sentiment = float(
                r.get("sentiment", r.get("sentiment_avg", 0.0)) or 0.0
            )
        except (TypeError, ValueError):
            sentiment = 0.0

        try:
            window_days = int(r.get("window_days", 7) or 7)
        except (TypeError, ValueError):
            window_days = 7

        state = agg[scenic_id]
        if post_count > 0:
            state["post_count"] += post_count
            sentiment_weight = post_count
        else:
            state["post_count"] += 1
            sentiment_weight = 1
        state["interaction_sum"] += interactions
        state["sentiment_sum"] += sentiment * sentiment_weight
        state["sentiment_count"] += sentiment_weight
        if window_days > state["window_days"]:
            state["window_days"] = window_days

    updated_count = 0
    for scenic_id, state in agg.items():
        if state["sentiment_count"] > 0:
            sentiment_avg = state["sentiment_sum"] / state["sentiment_count"]
        else:
            sentiment_avg = 0.0

        summary_obj = {
            "window_days": state["window_days"],
            "post_count": state["post_count"],
            "interaction_sum": state["interaction_sum"],
            "sentiment_avg": sentiment_avg,
        }

        existing = (
            ContentStandard.query.filter_by(
                entity_type="scenic_spot",
                entity_id=scenic_id,
                source_type="social_media",
            ).first()
        )
        if existing is None:
            existing = ContentStandard(
                entity_type="scenic_spot",
                entity_id=scenic_id,
                source_type="social_media",
            )
            db.session.add(existing)

        existing.title = "social_media_statistics"
        existing.summary = json.dumps(summary_obj, ensure_ascii=False)
        updated_count += 1

    db.session.commit()
    return updated_count


def main() -> None:
    app = create_app()
    with app.app_context():
        keywords = ["希拉穆仁草原", "阿尔山国家森林公园", "成吉思汗陵"]
        records = load_posts_for_keywords(keywords)
        updated_count = aggregate_to_content_standard(records)
        print(f"loaded_social_records={len(records)} updated_entities={updated_count}")


if __name__ == "__main__":
    main()
