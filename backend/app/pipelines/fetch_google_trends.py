from __future__ import annotations

import argparse
import csv
import os
import time
from pathlib import Path

import pandas as pd
from pytrends.request import TrendReq

from .. import create_app
from ..models import ScenicSpot


def _normalize_geo_text(s: str | None) -> str:
    """Normalize common Chinese geo suffixes like 市/区/县/旗/盟/自治州 等."""
    if not s:
        return ""
    t = str(s).strip()
    for suf in ["自治州", "自治县", "自治旗", "地区", "市", "区", "县", "旗", "盟"]:
        t = t.replace(suf, "")
    return t.strip()


def _build_keyword_candidates(name: str, city: str | None, district: str | None) -> list[str]:
    n = (name or "").strip()
    c = _normalize_geo_text(city)
    d = _normalize_geo_text(district)
    cand: list[str] = []
    def add(s: str) -> None:
        s2 = " ".join([p for p in s.split() if p])
        if s2 and s2 not in cand:
            cand.append(s2)
    add(n)
    if c:
        add(f"{n} {c}")
    if d:
        add(f"{n} {d}")
    if c and d:
        add(f"{n} {c} {d}")
    return cand


def _compute_decay_weights(index: pd.Index, half_life_days: float) -> pd.Series | None:
    """Return exponential decay weights aligned with DatetimeIndex.
    Newer timestamps get larger weights: w = 0.5 ** (age_days / half_life_days).
    Returns None if index is not DatetimeIndex or half_life_days <= 0.
    """
    if half_life_days is None:
        return None
    try:
        h = float(half_life_days)
    except Exception:
        h = 0.0
    if h <= 0:
        return None
    if not isinstance(index, pd.DatetimeIndex):
        return None
    try:
        t_max = pd.to_datetime(index.max())
        idx_dt = pd.to_datetime(index)
        ages_days = (t_max - idx_dt) / pd.Timedelta(days=1)
        weights = (0.5) ** (ages_days.astype(float) / h)
        return pd.Series(weights.values, index=index)
    except Exception:
        return None


def fetch_to_csv(out_path: Path, geo: str, timeframe: str, limit: int, sleep_sec: float, https_proxy: str | None = None, window2: str | None = None, blend_alpha: float = 0.7, decay_half_life_days: float = 0.0) -> tuple[int, int]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    app = create_app()
    written = 0
    tried = 0

    with app.app_context():
        q = ScenicSpot.query.with_entities(ScenicSpot.id, ScenicSpot.name, ScenicSpot.city, ScenicSpot.district)
        q = q.order_by(ScenicSpot.rating_count.desc(), ScenicSpot.rating_avg.desc(), ScenicSpot.id.desc())
        rows = q.limit(max(1, int(limit))).all()

    # Optional proxy (useful in restricted networks). If provided without scheme, try several common schemes.
    pytrends = None
    attempted = []
    schemes = ["http://", "https://", "socks5h://"]
    proxy_candidates: list[str] = []
    if https_proxy:
        if "://" in https_proxy:
            raw = https_proxy.split("://", 1)[1]
            proxy_candidates = [https_proxy] + [s + raw for s in schemes if (s + raw) != https_proxy]
        else:
            proxy_candidates = [s + https_proxy for s in schemes]

    # Try to initialize TrendReq with environment proxies so that initial cookie GET honors proxy
    # Always try DIRECT first, then proxies (helps when VPN is system-wide)
    for proxy in ([None] + proxy_candidates) if proxy_candidates else [None]:
        try:
            if proxy:
                os.environ["HTTPS_PROXY"] = proxy
                os.environ["HTTP_PROXY"] = proxy
                os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1")
                proxies = [proxy]  # pytrends expects a list of proxy strings
            else:
                # Clear to use direct connection
                for k in ("HTTPS_PROXY", "HTTP_PROXY"):
                    if k in os.environ:
                        os.environ.pop(k)
                proxies = []
            print(f"[INFO] Trying proxy: {proxies}")
            pytrends = TrendReq(
                hl="zh-CN",
                tz=480,
                timeout=(20, 60),
                retries=5,
                backoff_factor=1.0,
                proxies=proxies,
                requests_args={"verify": False},
            )
            attempted.append((proxy or "DIRECT", "OK"))
            break
        except Exception as e:
            import traceback
            traceback.print_exc()
            attempted.append((proxy or "DIRECT", f"FAIL: {type(e).__name__}: {e}"))
            pytrends = None
            continue

    if pytrends is None:
        print(f"[ERROR] Unable to initialize TrendReq after attempts: {attempted}")
        return 0, 0

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "entity_type",
            "entity_id",
            "source_type",
            "external_rating",
            "review_count",
            "interaction_sum",
            "sentiment_avg",
        ])

        for rid, name, city, district in rows:
            tried += 1
            cands = _build_keyword_candidates(str(name or ""), city, district)
            interaction_sum = 0
            # Query in batches of up to 5 keywords per request, take max sum across candidates
            def _max_sum_for_window(tf: str, apply_decay: bool) -> int:
                best = 0
                if not cands:
                    return 0
                for i in range(0, len(cands), 5):
                    batch = cands[i:i+5]
                    try:
                        pytrends.build_payload(batch, cat=0, timeframe=tf, geo=geo, gprop="")
                        df = pytrends.interest_over_time()
                        if isinstance(df, pd.DataFrame) and not df.empty:
                            for col in batch:
                                if col in df.columns:
                                    s = df[col].fillna(0)
                                    if apply_decay:
                                        w = _compute_decay_weights(df.index, float(decay_half_life_days))
                                        if isinstance(w, pd.Series) and len(w) == len(s):
                                            v = float((s * w).sum())
                                        else:
                                            v = float(s.sum())
                                    else:
                                        v = float(s.sum())
                                    best = max(best, int(round(v)))
                    except Exception:
                        continue
                return best

            if cands:
                if window2:
                    try:
                        a = float(blend_alpha)
                    except Exception:
                        a = 0.7
                    a = max(0.0, min(1.0, a))
                    v1 = _max_sum_for_window(timeframe, apply_decay=(float(decay_half_life_days) > 0.0 and str(timeframe).strip().lower().startswith("now")))
                    v2 = _max_sum_for_window(str(window2), apply_decay=False)
                    interaction_sum = int(round(a * v1 + (1.0 - a) * v2))
                else:
                    interaction_sum = _max_sum_for_window(timeframe, apply_decay=(float(decay_half_life_days) > 0.0 and str(timeframe).strip().lower().startswith("now")))

            w.writerow(["scenic_spot", int(rid), "social_media", "", "", int(interaction_sum), "0.75"])
            written += 1
            time.sleep(max(0.0, float(sleep_sec)))

    return tried, written


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch Google Trends interest_over_time as social interactions for scenic spots")
    p.add_argument("--geo", type=str, default="CN")
    p.add_argument("--window", type=str, default="today 3-m")
    p.add_argument("--window2", type=str, default=None, help="Optional second timeframe for blending, e.g. 'today 12-m'")
    p.add_argument("--blend-alpha", dest="blend_alpha", type=float, default=0.7, help="Blend weight for --window (0..1), default 0.7")
    p.add_argument("--decay-half-life-days", dest="decay_half_life_days", type=float, default=0.0, help="Exponential decay half-life (days) for the primary 'now *' window; 0 to disable")
    p.add_argument("--out", type=str, default=str(Path("E:/旅游/data/google_trends_social.csv")))
    p.add_argument("--max", dest="limit", type=int, default=120)
    p.add_argument("--sleep", dest="sleep", type=float, default=2.5)
    p.add_argument("--https-proxy", dest="https_proxy", type=str, default=None, help="HTTPS proxy, e.g. https://127.0.0.1:7890")
    args = p.parse_args()

    out_path = Path(args.out)
    tried, written = fetch_to_csv(
        out_path,
        geo=args.geo,
        timeframe=args.window,
        limit=args.limit,
        sleep_sec=args.sleep,
        https_proxy=args.https_proxy,
        window2=args.window2,
        blend_alpha=args.blend_alpha,
        decay_half_life_days=args.decay_half_life_days,
    )
    print(f"GoogleTrends done: tried={tried} written={written} -> {out_path}")


if __name__ == "__main__":
    main()
