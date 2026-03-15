from __future__ import annotations

import json
from collections import defaultdict
from math import sqrt

from .. import create_app
from ..db import db
from ..models import Rating, ContentStandard


def build_item_similarity() -> None:
    """基于评分记录计算景点间的 item-based 协同过滤相似度。

    结果以邻居列表的形式写入 content_standard 表：
      - entity_type = "scenic_spot"
      - source_type = "item_cf_similarity"
      - summary = {"neighbors": [{"id": scenic_id, "sim": similarity}, ...]}
    """

    ratings = Rating.query.filter_by(target_type="scenic_spot").all()
    if not ratings:
        return

    # user_id -> List[(spot_id, score)]
    user_ratings: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for r in ratings:
        if r.user_id is None:
            continue
        try:
            score = float(r.score)
        except (TypeError, ValueError):
            continue
        user_ratings[r.user_id].append((int(r.target_id), score))

    # (i, j) with i < j -> [sum_xy, sum_x2, sum_y2, count]
    pair_stats: dict[tuple[int, int], list[float]] = {}

    for uid, items in user_ratings.items():
        if len(items) < 2:
            continue
        # 简单去重：同一用户对同一景点多条评分时只取最后一条
        latest: dict[int, float] = {}
        for sid, score in items:
            latest[sid] = score
        ids_scores = list(latest.items())
        n = len(ids_scores)
        if n < 2:
            continue

        for i in range(n):
            sid_i, score_i = ids_scores[i]
            for j in range(i + 1, n):
                sid_j, score_j = ids_scores[j]
                if sid_i == sid_j:
                    continue
                a, b = (sid_i, sid_j) if sid_i < sid_j else (sid_j, sid_i)
                key = (a, b)
                stats = pair_stats.get(key)
                if stats is None:
                    stats = [0.0, 0.0, 0.0, 0.0]
                    pair_stats[key] = stats
                stats[0] += score_i * score_j  # sum_xy
                stats[1] += score_i * score_i  # sum_x2
                stats[2] += score_j * score_j  # sum_y2
                stats[3] += 1.0  # count

    # 计算余弦相似度并构建邻居列表
    neighbors: dict[int, list[tuple[int, float]]] = defaultdict(list)
    min_count = 2  # 至少 2 个共同评分用户

    for (sid_a, sid_b), (sum_xy, sum_x2, sum_y2, count) in pair_stats.items():
        if count < min_count:
            continue
        denom = sqrt(sum_x2) * sqrt(sum_y2)
        if denom <= 0:
            continue
        sim = sum_xy / denom
        if sim <= 0:
            continue
        neighbors[sid_a].append((sid_b, sim))
        neighbors[sid_b].append((sid_a, sim))

    # 将每个景点的前若干相似邻居写入 content_standard
    top_k = 20
    for sid, sims in neighbors.items():
        sims.sort(key=lambda x: x[1], reverse=True)
        top = [
            {"id": other_id, "sim": round(float(score), 4)}
            for other_id, score in sims[:top_k]
        ]
        summary_obj = {"neighbors": top}
        summary_text = json.dumps(summary_obj, ensure_ascii=False)

        row = (
            ContentStandard.query.filter_by(
                entity_type="scenic_spot",
                entity_id=sid,
                source_type="item_cf_similarity",
            ).first()
        )
        if row is None:
            row = ContentStandard(
                entity_type="scenic_spot",
                entity_id=sid,
                source_type="item_cf_similarity",
            )
            db.session.add(row)

        row.title = "item_based_cf_neighbors"
        row.summary = summary_text

    db.session.commit()


def main() -> None:
    app = create_app()
    with app.app_context():
        build_item_similarity()


if __name__ == "__main__":
    main()
