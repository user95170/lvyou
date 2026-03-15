from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

if "DATABASE_URL" not in os.environ:
    default_db = (_BACKEND_DIR / "e2e.db").resolve().as_posix()
    os.environ["DATABASE_URL"] = f"sqlite:///{default_db}"

from app import create_app
from app.db import db
from app.models import ContentStandard, FoodPlace, Hotel, ScenicSpot


def seed_database() -> None:
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        scenic_spots = [
            ScenicSpot(
                id=1,
                name="大召寺",
                city="呼和浩特",
                address="玉泉区大召前街",
                longitude=111.654,
                latitude=40.807,
                category="culture",
                tags="历史,寺庙",
                description="呼和浩特代表性人文景点",
                rating_avg=4.8,
                rating_count=220,
            ),
            ScenicSpot(
                id=2,
                name="内蒙古博物院",
                city="呼和浩特",
                address="新城区新华东街",
                longitude=111.720,
                latitude=40.842,
                category="museum",
                tags="博物馆,历史",
                description="适合亲子和人文游览",
                rating_avg=4.7,
                rating_count=180,
            ),
            ScenicSpot(
                id=3,
                name="敕勒川草原",
                city="呼和浩特",
                address="土默特左旗",
                longitude=111.218,
                latitude=40.567,
                category="grassland",
                tags="草原,自然",
                description="草原风光体验景点",
                rating_avg=4.9,
                rating_count=260,
            ),
            ScenicSpot(
                id=4,
                name="希拉穆仁草原",
                city="包头",
                address="达尔罕茂明安联合旗",
                longitude=110.245,
                latitude=41.580,
                category="grassland",
                tags="草原,自然",
                description="经典草原旅游目的地",
                rating_avg=4.6,
                rating_count=150,
            ),
        ]

        hotels = [
            Hotel(
                id=1,
                name="呼和浩特香格里拉大酒店",
                city="呼和浩特",
                address="新城区锡林郭勒南路",
                longitude=111.667,
                latitude=40.819,
                star_level="5-star",
                avg_price=780,
                rating_avg=4.7,
                rating_count=96,
                tags="亲子,商旅",
            ),
            Hotel(
                id=2,
                name="包头万达嘉华酒店",
                city="包头",
                address="青山区钢铁大街",
                longitude=109.840,
                latitude=40.657,
                star_level="4-star",
                avg_price=520,
                rating_avg=4.5,
                rating_count=82,
                tags="商务,购物",
            ),
        ]

        foods = [
            FoodPlace(
                id=1,
                name="格日勒阿妈奶茶馆",
                city="呼和浩特",
                address="赛罕区大学东街",
                longitude=111.693,
                latitude=40.813,
                cuisine_type="蒙餐",
                avg_price=68,
                rating_avg=4.6,
                rating_count=120,
                tags="奶茶,牛肉",
            ),
            FoodPlace(
                id=2,
                name="草原牧歌烤羊店",
                city="呼和浩特",
                address="新城区海拉尔东街",
                longitude=111.731,
                latitude=40.839,
                cuisine_type="烧烤",
                avg_price=96,
                rating_avg=4.5,
                rating_count=110,
                tags="烧烤,羊肉",
            ),
        ]

        content_rows = [
            ContentStandard(
                entity_type="scenic_spot",
                entity_id=1,
                source_type="item_cf_similarity",
                summary=json.dumps(
                    {
                        "neighbors": [
                            {"id": 2, "sim": 0.93},
                            {"id": 3, "sim": 0.89},
                        ]
                    },
                    ensure_ascii=False,
                ),
            ),
            ContentStandard(
                entity_type="scenic_spot",
                entity_id=3,
                source_type="item_cf_similarity",
                summary=json.dumps(
                    {
                        "neighbors": [
                            {"id": 1, "sim": 0.95},
                            {"id": 2, "sim": 0.91},
                        ]
                    },
                    ensure_ascii=False,
                ),
            ),
            ContentStandard(
                entity_type="scenic_spot",
                entity_id=1,
                source_type="internal_rating",
                popularity_score=4.9,
                summary=json.dumps({"rating_avg": 4.8, "rating_count": 220}, ensure_ascii=False),
            ),
            ContentStandard(
                entity_type="scenic_spot",
                entity_id=3,
                source_type="ota_stats",
                popularity_score=4.8,
                summary=json.dumps({"external_rating": 4.9, "review_count": 1800}, ensure_ascii=False),
            ),
        ]

        db.session.add_all(scenic_spots + hotels + foods + content_rows)
        db.session.commit()


def main() -> None:
    seed_database()
    app = create_app()
    port = int(os.getenv("PORT", "5100"))
    host = os.getenv("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
