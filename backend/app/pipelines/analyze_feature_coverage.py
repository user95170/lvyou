from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from .. import create_app
from ..db import db
from ..models import ContentStandard, ScenicSpot, Hotel, FoodPlace


def _safe_parse_summary(summary: str) -> Dict[str, Any]:
    if not summary:
        return {}
    try:
        return json.loads(summary)
    except Exception:
        try:
            return json.loads(summary.replace("'", '"'))
        except Exception:
            return {}


def _percentiles(values: List[float], qs: List[float]) -> Dict[float, float]:
    if not values:
        return {q: 0.0 for q in qs}
    xs = sorted(values)
    n = len(xs)
    out: Dict[float, float] = {}
    for q in qs:
        if q <= 0:
            out[q] = float(xs[0])
        elif q >= 1:
            out[q] = float(xs[-1])
        else:
            idx = int(q * (n - 1))
            out[q] = float(xs[idx])
    return out


def _coverage_and_stats_for_entity(entity_type: str, Model) -> Dict[str, Any]:
    total = db.session.query(Model).count()

    # OTA coverage & stats
    ota_rows = (
        db.session.query(ContentStandard)
        .filter(
            ContentStandard.entity_type == entity_type,
            ContentStandard.source_type.in_(["ota_stats", "ota"]),
        )
        .all()
    )

    seen_ota_ids = set()
    ota_rating_vals: List[float] = []
    ota_review_vals: List[float] = []

    for row in ota_rows:
        if not row.summary:
            continue
        payload = _safe_parse_summary(row.summary)
        if not payload:
            continue
        seen_ota_ids.add(row.entity_id)
        # rating
        for k in ("external_rating", "rating"):
            v = payload.get(k)
            if v is not None:
                try:
                    ota_rating_vals.append(float(v))
                    break
                except Exception:
                    pass
        # review_count
        for k in ("review_count", "external_review_count"):
            v = payload.get(k)
            if v is not None:
                try:
                    ota_review_vals.append(float(int(v)))
                    break
                except Exception:
                    pass

    # Social coverage & stats
    social_rows = (
        db.session.query(ContentStandard)
        .filter(
            ContentStandard.entity_type == entity_type,
            ContentStandard.source_type == "social_media",
        )
        .all()
    )

    seen_social_ids = set()
    social_inter_vals: List[float] = []
    social_sent_vals: List[float] = []

    for row in social_rows:
        if not row.summary:
            continue
        payload = _safe_parse_summary(row.summary)
        if not payload:
            continue
        seen_social_ids.add(row.entity_id)
        # interactions
        for k in ("interaction_sum", "interactions", "social_interactions"):
            v = payload.get(k)
            if v is not None:
                try:
                    social_inter_vals.append(float(int(v)))
                    break
                except Exception:
                    pass
        # sentiment
        for k in ("sentiment_avg", "sentiment"):
            v = payload.get(k)
            if v is not None:
                try:
                    social_sent_vals.append(float(v))
                    break
                except Exception:
                    pass

    def _summ(vals: List[float]) -> Dict[str, float]:
        if not vals:
            return {
                "count": 0.0,
                "mean": 0.0,
                "p50": 0.0,
                "p75": 0.0,
                "p90": 0.0,
                "max": 0.0,
            }
        qs = _percentiles(vals, [0.5, 0.75, 0.9])
        return {
            "count": float(len(vals)),
            "mean": float(sum(vals) / len(vals)),
            "p50": qs[0.5],
            "p75": qs[0.75],
            "p90": qs[0.9],
            "max": float(max(vals)),
        }

    result = {
        "total": total,
        "ota_covered": len(seen_ota_ids),
        "social_covered": len(seen_social_ids),
        "ota_rating": _summ(ota_rating_vals),
        "ota_reviews": _summ(ota_review_vals),
        "social_interactions": _summ(social_inter_vals),
        "social_sentiment": _summ(social_sent_vals),
    }
    return result


def main() -> None:
    app = create_app()
    with app.app_context():
        mapping = {
            "scenic_spot": ScenicSpot,
            "hotel": Hotel,
            "food_place": FoodPlace,
        }
        print("=== Feature Coverage Report ===")
        for et, Model in mapping.items():
            stats = _coverage_and_stats_for_entity(et, Model)
            total = stats["total"] or 0
            def _pct(x: int) -> str:
                return f"{(100.0 * (x or 0) / total):.1f}%" if total > 0 else "0.0%"
            print(f"-- {et} -- total={total}")
            print(f"OTA covered: {stats['ota_covered']} ({_pct(stats['ota_covered'])})")
            print(f"Social covered: {stats['social_covered']} ({_pct(stats['social_covered'])})")
            print("OTA rating   :", stats["ota_rating"])
            print("OTA reviews  :", stats["ota_reviews"])
            print("Social inter :", stats["social_interactions"])
            print("Social sent  :", stats["social_sentiment"])
            print()


if __name__ == "__main__":
    main()
