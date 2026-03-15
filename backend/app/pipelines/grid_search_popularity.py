from __future__ import annotations

import argparse
import csv
import itertools
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from .. import create_app
from .train_popularity_model import train_and_save_model
from . import aggregate_content as agg


@dataclass
class Combo:
    w_base: float
    w_ota: float
    w_social_heat: float
    w_sentiment: float
    m_percentile: float
    log_transform: bool
    social_percentile: float


def _run_eval(backend_dir: Path) -> Tuple[Dict[str, float], Dict[str, float]]:
    """Run evaluate_recommendation module and parse WR & ML-Popular lines.
    Returns: (wr_metrics, ml_metrics) where each has keys p5, p10, ndcg5, ndcg10
    """
    proc = subprocess.run(
        [sys.executable, "-m", "app.pipelines.evaluate_recommendation"],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")

    # Robust regex for metrics lines
    def parse_line(label: str) -> Dict[str, float] | None:
        # Accept both English and Chinese around separators
        m = re.search(
            rf"{label}.*?P@5=([0-9.]+).*?P@10=([0-9.]+).*?NDCG@5=([0-9.]+).*?NDCG@10=([0-9.]+)",
            out,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not m:
            return None
        return {
            "p5": float(m.group(1)),
            "p10": float(m.group(2)),
            "ndcg5": float(m.group(3)),
            "ndcg10": float(m.group(4)),
        }

    wr = parse_line(r"(?:Popular\s*-?\s*WR|热门推荐\s*-?\s*WR)") or {}
    ml = parse_line(r"(?:ML\s*-?\s*Popular)") or {}
    return wr, ml


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid search for ML-Popular weights, m_percentile and social_percentile")
    parser.add_argument("--out", type=str, default=str(Path("E:/旅游/data/grid_search_popularity_results.csv")))
    parser.add_argument("--w-base", type=float, nargs="*", default=[1.0])
    parser.add_argument("--w-ota", type=float, nargs="*", default=[0.8, 1.0, 1.2])
    parser.add_argument("--w-social-heat", type=float, nargs="*", default=[0.5, 1.0])
    parser.add_argument("--w-sentiment", type=float, nargs="*", default=[2.0])
    parser.add_argument("--m-percentile", type=float, nargs="*", default=[0.50, 0.60])
    parser.add_argument("--log-transform", action="store_true")
    parser.add_argument("--social-percentile", type=float, nargs="*", default=[0.95])

    args = parser.parse_args()

    combos: List[Combo] = []
    for w_base, w_ota, w_sh, w_sent, m, sp in itertools.product(
        args.w_base, args.w_ota, args.w_social_heat, args.w_sentiment, args.m_percentile, args.social_percentile
    ):
        combos.append(
            Combo(
                w_base=float(w_base),
                w_ota=float(w_ota),
                w_social_heat=float(w_sh),
                w_sentiment=float(w_sent),
                m_percentile=float(m),
                log_transform=bool(args.log_transform),
                social_percentile=float(sp),
            )
        )

    backend_dir = Path(__file__).resolve().parents[3] / "backend"

    app = create_app()
    results: List[Dict[str, object]] = []
    with app.app_context():
        for i, c in enumerate(combos, start=1):
            print(
                f"[{i}/{len(combos)}] Train w_base={c.w_base} w_ota={c.w_ota} w_social_heat={c.w_social_heat} "
                f"w_sentiment={c.w_sentiment} m={c.m_percentile} sp={c.social_percentile} log={c.log_transform}"
            )
            train_and_save_model(
                w_base=c.w_base,
                w_ota=c.w_ota,
                w_social_heat=c.w_social_heat,
                w_sentiment=c.w_sentiment,
                m_percentile=c.m_percentile,
                log_transform=c.log_transform,
                social_percentile=c.social_percentile,
            )
            # Aggregate with the latest model
            agg.aggregate_all()

            # Evaluate (run as a subprocess to reuse the existing CLI output)
            wr, ml = _run_eval(backend_dir)

            row: Dict[str, object] = {
                "w_base": c.w_base,
                "w_ota": c.w_ota,
                "w_social_heat": c.w_social_heat,
                "w_sentiment": c.w_sentiment,
                "m_percentile": c.m_percentile,
                "social_percentile": c.social_percentile,
                "log_transform": c.log_transform,
                "wr_p5": wr.get("p5"),
                "wr_p10": wr.get("p10"),
                "wr_ndcg5": wr.get("ndcg5"),
                "wr_ndcg10": wr.get("ndcg10"),
                "ml_p5": ml.get("p5"),
                "ml_p10": ml.get("p10"),
                "ml_ndcg5": ml.get("ndcg5"),
                "ml_ndcg10": ml.get("ndcg10"),
            }
            results.append(row)

    # Save CSV
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "w_base",
                "w_ota",
                "w_social_heat",
                "w_sentiment",
                "m_percentile",
                "social_percentile",
                "log_transform",
                "wr_p5",
                "wr_p10",
                "wr_ndcg5",
                "wr_ndcg10",
                "ml_p5",
                "ml_p10",
                "ml_ndcg5",
                "ml_ndcg10",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    now = datetime.now(timezone.utc).isoformat()
    print(f"[{now}] Grid search finished. Results saved to: {out_path}")


if __name__ == "__main__":
    main()
