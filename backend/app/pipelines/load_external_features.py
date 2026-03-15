from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .. import create_app
from ..db import db
from ..models import ContentStandard


@dataclass
class RowData:
    entity_type: str
    entity_id: int
    source_type: str  # ota_stats or social_media
    external_rating: Optional[float]
    review_count: Optional[int]
    interaction_sum: Optional[int]
    sentiment_avg: Optional[float]


def _parse_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


def _parse_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(float(v))
    except Exception:
        return None


def _upsert(row: RowData) -> None:
    if row.source_type not in ("ota_stats", "social_media"):
        return

    payload: Dict[str, Any] = {}
    if row.source_type == "ota_stats":
        if row.external_rating is not None:
            payload["external_rating"] = float(row.external_rating)
        if row.review_count is not None:
            payload["review_count"] = int(row.review_count)
    elif row.source_type == "social_media":
        if row.interaction_sum is not None:
            payload["interaction_sum"] = int(row.interaction_sum)
        if row.sentiment_avg is not None:
            payload["sentiment_avg"] = float(row.sentiment_avg)

    # 若无有效字段，跳过
    if not payload:
        return

    cs = ContentStandard.query.filter_by(
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        source_type=row.source_type,
    ).first()
    if cs is None:
        cs = ContentStandard(
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            source_type=row.source_type,
        )
        db.session.add(cs)

    cs.title = row.source_type
    cs.summary = json.dumps(payload, ensure_ascii=False)
    cs.last_update = datetime.now(timezone.utc)


def import_csv(input_path: Path) -> None:
    with input_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, r in enumerate(reader, start=1):
            try:
                row = RowData(
                    entity_type=(r.get("entity_type") or "").strip(),
                    entity_id=int(r.get("entity_id") or 0),
                    source_type=(r.get("source_type") or "").strip(),
                    external_rating=_parse_float(r.get("external_rating")),
                    review_count=_parse_int(r.get("review_count")),
                    interaction_sum=_parse_int(r.get("interaction_sum")),
                    sentiment_avg=_parse_float(r.get("sentiment_avg")),
                )
            except Exception:
                continue
            if not row.entity_type or row.entity_id <= 0 or not row.source_type:
                continue
            _upsert(row)
    db.session.commit()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.pipelines.load_external_features <input_csv>")
        sys.exit(2)
    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Input not found: {input_path}")
        sys.exit(2)

    app = create_app()
    with app.app_context():
        import_csv(input_path)
        print(f"Imported external features from {input_path}")


if __name__ == "__main__":
    main()
