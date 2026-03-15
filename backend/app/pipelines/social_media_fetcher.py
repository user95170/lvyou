from __future__ import annotations

"""社交媒体与 UGC 数据采集骨架脚本。

本脚本用于演示从社交媒体平台（微博/短视频/小红书等）采集旅游相关数据的基本流程。
出于合规与环境限制，本脚本默认不直接调用任何平台 API，只提供结构化的代码骨架，
真正的请求 URL、参数和解析逻辑需要在后续按平台规范补充。
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
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def fetch_posts_for_keywords(keywords: Iterable[str]) -> List[dict]:
    """根据关键词列表抓取社交媒体内容（示意函数）。

    返回的每条记录建议包含：
      - keyword: 关联的关键词
      - title / text: 文本内容
      - interactions: 互动量（点赞+评论+转发等）
      - sentiment: 情感得分（可选，后续用 NLP 计算）
      - scenic_name: 尝试匹配出的景点名称（可选）

    当前为骨架实现，只返回空列表。
    """

    data_dir = Path(os.getenv("SOCIAL_MEDIA_DATA_DIR", "E:/旅游/data"))
    csv_path = data_dir / "social_media_scenic_sample.csv"
    if csv_path.exists():
        rows = read_social_csv(csv_path)
        return rows

    api_key = os.getenv("SOCIAL_MEDIA_API_KEY")
    if not api_key:
        # 没有配置 Key 时，直接返回空结果，避免运行时错误。
        return []

    # TODO: 在此处按具体平台补充请求与解析逻辑。
    return []


def aggregate_to_content_standard(records: List[dict]) -> None:
    """将社交媒体记录聚合到 content_standard 表（示意实现）。

    实际使用中，应先将 scenic_name 映射到内部 scenic_spot.id，
    然后对同一景点的互动量、情感得分等做汇总，写入：
      - entity_type = "scenic_spot"
      - source_type = "social_media"
      - summary: {"window_days": 7, "post_count": ..., "interaction_sum": ..., "sentiment_avg": ...}
    """

    if not records:
        return

    # 这里只给出结构示意，不做具体实现。
    # 可以在后续根据实际数据结构补充聚合逻辑。

    mapping = load_scenic_mapping()
    if not mapping:
        return

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
        scenic_name = (r.get("scenic_name") or r.get("name") or "").strip()
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
        else:
            state["post_count"] += 1
        state["interaction_sum"] += interactions
        state["sentiment_sum"] += sentiment
        state["sentiment_count"] += 1
        if window_days > state["window_days"]:
            state["window_days"] = window_days

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

    db.session.commit()


def main() -> None:
    app = create_app()
    with app.app_context():
        # 示例：对若干景点关键词做采集与聚合
        keywords = ["希拉穆仁草原", "阿尔山国家森林公园", "成吉思汗陵"]
        records = fetch_posts_for_keywords(keywords)
        aggregate_to_content_standard(records)


if __name__ == "__main__":
    main()
