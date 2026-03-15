from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from .. import create_app
from ..db import db
from ..models import ScenicSpot, Hotel, FoodPlace


@dataclass
class DistCfg:
    rating_mu: float  # mean for Normal
    rating_sigma: float
    reviews_logn_mu: float  # mu in log-space for lognormal
    reviews_logn_sigma: float
    reviews_min: int
    reviews_max: int
    inter_logn_mu: float
    inter_logn_sigma: float
    inter_min: int
    inter_max: int
    sent_mu: float
    sent_sigma: float


CFG: Dict[str, DistCfg] = {
    # Rough priors inspired by typical OTA patterns: high average ratings, long-tailed review counts
    "scenic_spot": DistCfg(
        rating_mu=4.6,
        rating_sigma=0.18,
        reviews_logn_mu=7.7,     # exp(mu) ~ 2200
        reviews_logn_sigma=1.0,
        reviews_min=20,
        reviews_max=25000,
        inter_logn_mu=8.0,       # exp(mu) ~ 2980
        inter_logn_sigma=1.0,
        inter_min=200,
        inter_max=50000,
        sent_mu=0.84,
        sent_sigma=0.08,
    ),
    "hotel": DistCfg(
        rating_mu=4.55,
        rating_sigma=0.2,
        reviews_logn_mu=7.4,     # exp(mu) ~ 1630
        reviews_logn_sigma=1.0,
        reviews_min=20,
        reviews_max=20000,
        inter_logn_mu=7.7,       # exp(mu) ~ 2200
        inter_logn_sigma=1.0,
        inter_min=150,
        inter_max=30000,
        sent_mu=0.83,
        sent_sigma=0.09,
    ),
    "food_place": DistCfg(
        rating_mu=4.5,
        rating_sigma=0.22,
        reviews_logn_mu=5.7,     # exp(mu) ~ 300
        reviews_logn_sigma=1.0,
        reviews_min=10,
        reviews_max=4000,
        inter_logn_mu=6.3,       # exp(mu) ~ 544
        inter_logn_sigma=1.0,
        inter_min=80,
        inter_max=10000,
        sent_mu=0.80,
        sent_sigma=0.10,
    ),
}


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _normal_clip(mu: float, sigma: float, lo: float, hi: float) -> float:
    return _clip(random.normalvariate(mu, sigma), lo, hi)


def _lognormal_clip(mu: float, sigma: float, lo: int, hi: int) -> int:
    # Python's lognormvariate takes mu, sigma in normal space then exp
    x = math.exp(random.normalvariate(mu, sigma))
    return int(_clip(x, lo, hi))


def _pick_ids(ids: List[int], frac: float) -> List[int]:
    if not ids or frac <= 0:
        return []
    k = max(1, int(len(ids) * frac))
    k = min(k, len(ids))
    return random.sample(ids, k)


def _fetch_ids(offline: bool, scenic_n: int, hotel_n: int, food_n: int) -> Dict[str, List[int]]:
    if offline:
        scenic_ids = list(range(1, max(0, scenic_n) + 1))
        hotel_ids = list(range(1, max(0, hotel_n) + 1))
        food_ids = list(range(1, max(0, food_n) + 1))
    else:
        scenic_ids = [row.id for row in ScenicSpot.query.with_entities(ScenicSpot.id).all()]
        hotel_ids = [row.id for row in Hotel.query.with_entities(Hotel.id).all()]
        food_ids = [row.id for row in FoodPlace.query.with_entities(FoodPlace.id).all()]
    return {
        "scenic_spot": scenic_ids,
        "hotel": hotel_ids,
        "food_place": food_ids,
    }


def generate_csv(
    output: Path,
    ota_frac: float,
    social_frac: float,
    seed: int | None = None,
    *,
    offline: bool = False,
    scenic_n: int = 0,
    hotel_n: int = 0,
    food_n: int = 0,
    correlated: bool = False,
) -> Tuple[int, int]:
    if seed is not None:
        random.seed(seed)

    output.parent.mkdir(parents=True, exist_ok=True)

    ids_map = _fetch_ids(offline=offline, scenic_n=scenic_n, hotel_n=hotel_n, food_n=food_n)

    ota_rows = 0
    social_rows = 0

    # Pre-fetch stats when using DB + correlated mode
    stats_map: Dict[str, Dict[int, Tuple[float, float]]] = {"scenic_spot": {}, "hotel": {}, "food_place": {}}
    if not offline and correlated:
        for row in ScenicSpot.query.with_entities(ScenicSpot.id, ScenicSpot.rating_avg, ScenicSpot.rating_count).all():
            try:
                stats_map["scenic_spot"][int(row.id)] = (float(row.rating_avg or 0.0), float(row.rating_count or 0.0))
            except Exception:
                continue
        for row in Hotel.query.with_entities(Hotel.id, Hotel.rating_avg, Hotel.rating_count).all():
            try:
                stats_map["hotel"][int(row.id)] = (float(row.rating_avg or 0.0), float(row.rating_count or 0.0))
            except Exception:
                continue
        for row in FoodPlace.query.with_entities(FoodPlace.id, FoodPlace.rating_avg, FoodPlace.rating_count).all():
            try:
                stats_map["food_place"][int(row.id)] = (float(row.rating_avg or 0.0), float(row.rating_count or 0.0))
            except Exception:
                continue

    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "entity_type",
                "entity_id",
                "source_type",
                "external_rating",
                "review_count",
                "interaction_sum",
                "sentiment_avg",
            ]
        )

        for etype, ids in ids_map.items():
            cfg = CFG[etype]
            # heuristics for correlated sampling
            max_cnt_guess = 5000 if etype in ("scenic_spot", "hotel") else 800

            # OTA rows
            for eid in _pick_ids(ids, ota_frac):
                if correlated and not offline:
                    avg, cnt = stats_map.get(etype, {}).get(eid, (0.0, 0.0))
                    # external rating around internal avg (truncated to [3.5, 5.0])
                    base_mu = 0.7 * float(avg) + 1.5  # map [1,5] -> ~[2.2,5.0]
                    rating = _normal_clip(base_mu, 0.2, 3.5, 5.0)
                    # reviews log-mean boosted by relative count
                    ratio = 0.0
                    try:
                        ratio = min(1.0, math.log1p(cnt) / math.log1p(max_cnt_guess))
                    except Exception:
                        ratio = 0.0
                    reviews_mu = cfg.reviews_logn_mu + 0.6 * ratio
                    reviews = _lognormal_clip(reviews_mu, cfg.reviews_logn_sigma, cfg.reviews_min, cfg.reviews_max)
                else:
                    rating = _normal_clip(cfg.rating_mu, cfg.rating_sigma, 3.5, 5.0)
                    reviews = _lognormal_clip(
                        cfg.reviews_logn_mu, cfg.reviews_logn_sigma, cfg.reviews_min, cfg.reviews_max
                    )
                writer.writerow([etype, eid, "ota_stats", f"{rating:.1f}", reviews, "", ""])
                ota_rows += 1

            # Social rows
            for eid in _pick_ids(ids, social_frac):
                if correlated and not offline:
                    avg, cnt = stats_map.get(etype, {}).get(eid, (0.0, 0.0))
                    ratio = 0.0
                    try:
                        ratio = min(1.0, math.log1p(cnt) / math.log1p(max_cnt_guess))
                    except Exception:
                        ratio = 0.0
                    inter_mu = cfg.inter_logn_mu + 0.6 * ratio
                    interactions = _lognormal_clip(inter_mu, cfg.inter_logn_sigma, cfg.inter_min, cfg.inter_max)
                    sentiment_base = cfg.sent_mu + 0.05 * (float(avg) - 4.0)
                    sentiment = _clip(random.normalvariate(sentiment_base, cfg.sent_sigma), 0.0, 1.0)
                else:
                    interactions = _lognormal_clip(
                        cfg.inter_logn_mu, cfg.inter_logn_sigma, cfg.inter_min, cfg.inter_max
                    )
                    sentiment = _clip(random.normalvariate(cfg.sent_mu, cfg.sent_sigma), 0.0, 1.0)
                writer.writerow([etype, eid, "social_media", "", "", interactions, f"{sentiment:.2f}"])
                social_rows += 1

    return ota_rows, social_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic external features CSV for ota_stats/social_media"
    )
    parser.add_argument(
        "--ota",
        type=float,
        default=0.10,
        help="Fraction of entities per type to synthesize OTA stats for (0~1)",
    )
    parser.add_argument(
        "--social",
        type=float,
        default=0.10,
        help="Fraction of entities per type to synthesize social media stats for (0~1)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(Path("E:/旅游/data/external_features_synth.csv")),
        help="Output CSV path",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--offline", action="store_true", help="Generate without DB; use N counts below")
    parser.add_argument("--scenic-n", type=int, default=1000, help="Offline scenic_spot count")
    parser.add_argument("--hotel-n", type=int, default=1000, help="Offline hotel count")
    parser.add_argument("--food-n", type=int, default=1000, help="Offline food_place count")
    parser.add_argument("--correlated", action="store_true", help="Correlate external features with internal rating stats (DB mode)")

    args = parser.parse_args()

    out_path = Path(args.out)
    if args.offline:
        ota_rows, social_rows = generate_csv(
            out_path,
            args.ota,
            args.social,
            args.seed,
            offline=True,
            scenic_n=args.scenic_n,
            hotel_n=args.hotel_n,
            food_n=args.food_n,
            correlated=False,
        )
    else:
        app = create_app()
        with app.app_context():
            ota_rows, social_rows = generate_csv(
                out_path,
                args.ota,
                args.social,
                args.seed,
                offline=False,
                correlated=bool(args.correlated),
            )

    # Lightweight audit marker via print
    now = datetime.now(timezone.utc).isoformat()
    print(
        f"[{now}] Generated: {out_path} | OTA rows={ota_rows} | Social rows={social_rows} | ota={args.ota} social={args.social} | offline={args.offline}"
    )


if __name__ == "__main__":
    main()
