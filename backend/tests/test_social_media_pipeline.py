import csv
import json
import sys
from pathlib import Path

import pytest
from flask import Flask
from sqlalchemy.pool import StaticPool

_TEST_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TEST_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app.config import Config
from app.db import db, init_db
from app.models import ContentStandard, ScenicSpot
from app.pipelines.social_media_fetcher import (
    aggregate_to_content_standard,
    load_posts_for_keywords,
)


@pytest.fixture
def app_context():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

    init_db(app)

    with app.app_context():
        db.create_all()
        db.session.add(
            ScenicSpot(
                id=1,
                name="希拉穆仁草原",
                city="包头",
                longitude=110.245,
                latitude=41.580,
            )
        )
        db.session.commit()
        yield app


def test_social_media_csv_import_aggregates_content_standard(app_context, tmp_path):
    csv_path = tmp_path / "social.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "keyword",
                "scenic_name",
                "post_count",
                "interaction_sum",
                "sentiment_avg",
                "window_days",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "keyword": "草原",
                "scenic_name": "希拉穆仁草原",
                "post_count": "2",
                "interaction_sum": "30",
                "sentiment_avg": "0.8",
                "window_days": "7",
            }
        )
        writer.writerow(
            {
                "keyword": "希拉穆仁草原",
                "scenic_name": "希拉穆仁草原",
                "post_count": "1",
                "interaction_sum": "15",
                "sentiment_avg": "0.5",
                "window_days": "14",
            }
        )

    records = load_posts_for_keywords(["希拉穆仁草原"], csv_path)
    updated_count = aggregate_to_content_standard(records)

    assert updated_count == 1

    row = ContentStandard.query.filter_by(
        entity_type="scenic_spot",
        entity_id=1,
        source_type="social_media",
    ).first()
    assert row is not None
    summary = json.loads(row.summary)
    assert summary["post_count"] == 3
    assert summary["interaction_sum"] == 45
    assert summary["window_days"] == 14
    assert summary["sentiment_avg"] == pytest.approx(0.7)
