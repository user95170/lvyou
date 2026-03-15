from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend package is importable when running from repo root
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app import create_app
from app.db import db
from app.models import ContentStandard, Rating, User, UserBehaviorLog, UserProfile
from app.pipelines.aggregate_content import aggregate_all
from app.pipelines.aggregate_scenic_cf import build_item_similarity
from app.pipelines.generate_synthetic_ratings import generate_all as generate_synthetic_ratings


def refresh() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()

        # SQLite 下 BIGINT 主键不会自增，确保关键表重建为 INTEGER 主键
        if db.engine.dialect.name == "sqlite":
            for model in (ContentStandard, Rating, UserBehaviorLog):
                try:
                    model.__table__.drop(bind=db.engine, checkfirst=True)
                    model.__table__.create(bind=db.engine, checkfirst=True)
                except Exception:
                    pass

        # 清理孤立画像（无对应 user 的 user_profile）
        user_ids = [u.id for u in User.query.all()]
        if user_ids:
            orphan_q = UserProfile.query.filter(~UserProfile.user_id.in_(user_ids))
        else:
            orphan_q = UserProfile.query
        orphan_count = orphan_q.count()
        if orphan_count:
            orphan_q.delete(synchronize_session=False)
            db.session.commit()
            print(f"[WARN] 已清理 {orphan_count} 条孤立画像记录。")

        has_ratings = (
            Rating.query.filter_by(target_type="scenic_spot").limit(1).first() is not None
        )
        if not has_ratings:
            print("[INFO] rating 表为空，生成模拟评分以启用 CF/MF/Hybrid。")
            generate_synthetic_ratings()
        else:
            print("[INFO] rating 表已有数据，跳过模拟评分生成。")

        build_item_similarity()
        aggregate_all()

        cs_count = ContentStandard.query.count()
        rating_count = Rating.query.count()
        print(f"[OK] content_standard rows: {cs_count}, ratings: {rating_count}")


if __name__ == "__main__":
    refresh()
