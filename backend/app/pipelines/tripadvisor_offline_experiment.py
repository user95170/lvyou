from __future__ import annotations

import argparse
import csv
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


@dataclass
class RatingRecord:
    """单条评分记录（基于 TripAdvisor 酒店评论数据抽取的最小字段）。"""

    user_idx: int
    item_idx: int
    rating: float
    timestamp: datetime


def _default_project_root() -> Path:
    """推断项目根目录（..\\..\\.. 从 backend/app/pipelines 回到项目根）。"""

    return Path(__file__).resolve().parents[2].parent


def _parse_datetime(value: str) -> Optional[datetime]:
    text = (value or "").strip()
    if not text:
        return None

    # 优先尝试 ISO 格式，例如 2025-05-01T10:20:30
    try:
        return datetime.fromisoformat(text)
    except Exception:  # noqa: BLE001
        pass

    # 其次尝试常见日期格式
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except Exception:  # noqa: BLE001
            continue

    logger.warning("无法解析日期字段 %r，已跳过该条记录", value)
    return None


def load_tripadvisor_ratings(
    csv_path: Path,
    user_col: str,
    item_col: str,
    rating_col: str,
    date_col: str,
    max_reviews: Optional[int] = None,
) -> Tuple[List[RatingRecord], Dict[str, int], Dict[str, int]]:
    """从 TripAdvisor 酒店评论 CSV 中加载评分数据。

    通过列名参数指定用户、酒店、评分与日期列；
    默认与示例文件 `hotel_reviews.csv` 的列名对应：
      - user_col: user_id
      - item_col: hotel_id
      - rating_col: rating
      - date_col: date

    返回：
      - records: RatingRecord 列表
      - user_index: 原始 user_id -> 索引
      - item_index: 原始 item_id -> 索引
    """

    if not csv_path.exists():
        raise FileNotFoundError(
            f"找不到 TripAdvisor 酒店评论 CSV 文件: {csv_path}"
        )

    logger.info("开始读取 TripAdvisor 酒店评论数据: %s", csv_path)

    user_index: Dict[str, int] = {}
    item_index: Dict[str, int] = {}
    records: List[RatingRecord] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise RuntimeError("CSV 文件缺少表头行，无法导入评论数据")

        field_set = set(reader.fieldnames)
        required = {user_col, item_col, rating_col, date_col}
        missing = required - field_set
        if missing:
            raise RuntimeError(
                "CSV 文件缺少必要列: " + ", ".join(sorted(missing))
            )

        for i, row in enumerate(reader):
            if max_reviews is not None and i >= max_reviews:
                break

            user_id = (row.get(user_col) or "").strip()
            item_id = (row.get(item_col) or "").strip()
            rating_raw = (row.get(rating_col) or "").strip()
            date_raw = (row.get(date_col) or "").strip()

            if not user_id or not item_id or not rating_raw or not date_raw:
                continue

            try:
                rating = float(rating_raw)
            except ValueError:
                logger.warning("第 %d 行评分无法解析: %r", i + 2, rating_raw)
                continue

            ts = _parse_datetime(date_raw)
            if ts is None:
                # 已在 _parse_datetime 中记录 warning
                continue

            uidx = user_index.setdefault(user_id, len(user_index))
            iidx = item_index.setdefault(item_id, len(item_index))

            records.append(
                RatingRecord(
                    user_idx=uidx,
                    item_idx=iidx,
                    rating=rating,
                    timestamp=ts,
                )
            )

    logger.info(
        "加载完成：%d 条评分记录，%d 个用户，%d 家酒店",
        len(records),
        len(user_index),
        len(item_index),
    )

    if not records:
        raise RuntimeError("TripAdvisor 评分数据为空，请检查 CSV 内容或列名配置是否正确")

    return records, user_index, item_index


def build_train_test_split(
    records: Iterable[RatingRecord],
) -> Tuple[List[RatingRecord], List[RatingRecord]]:
    """基于“每个用户最后一次评分作为测试集”的策略划分 train/test。

    - 对每个 user_idx，选择时间戳最大的那条记录作为 test；
    - 其余记录作为 train。
    """

    last_by_user: Dict[int, RatingRecord] = {}

    all_records: List[RatingRecord] = list(records)
    for r in all_records:
        prev = last_by_user.get(r.user_idx)
        if prev is None or r.timestamp > prev.timestamp:
            last_by_user[r.user_idx] = r

    test_records_set = {id(rec) for rec in last_by_user.values()}

    train: List[RatingRecord] = []
    test: List[RatingRecord] = []

    for r in all_records:
        if id(r) in test_records_set:
            test.append(r)
        else:
            train.append(r)

    logger.info(
        "划分完成：训练集 %d 条，测试集 %d 条（用户数 %d）",
        len(train),
        len(test),
        len(last_by_user),
    )

    return train, test


def compute_popular_items(
    train: Iterable[RatingRecord],
) -> List[Tuple[int, float, int]]:
    """基于训练集计算全局热门酒店（平均评分 + 评分次数）。

    返回列表元素为 (item_idx, avg_rating, count)，按 avg_rating DESC, count DESC 排序。
    """

    from collections import defaultdict

    sum_rating: Dict[int, float] = defaultdict(float)
    cnt_rating: Dict[int, int] = defaultdict(int)

    for r in train:
        sum_rating[r.item_idx] += r.rating
        cnt_rating[r.item_idx] += 1

    stats: List[Tuple[int, float, int]] = []
    for item_idx, cnt in cnt_rating.items():
        if cnt <= 0:
            continue
        avg = sum_rating[item_idx] / cnt
        stats.append((item_idx, avg, cnt))

    stats.sort(key=lambda t: (-t[1], -t[2], t[0]))
    return stats


def evaluate_popular_hit_rate(
    popular_items: List[Tuple[int, float, int]],
    test: Iterable[RatingRecord],
    k: int,
) -> float:
    """在 leave-one-out 测试集上评估 Popular@K 的命中率（HitRate@K）。"""

    if k <= 0:
        raise ValueError("k 必须为正整数")

    top_k_item_indices = {item_idx for item_idx, _avg, _cnt in popular_items[:k]}

    test_list = list(test)
    if not test_list:
        raise RuntimeError("测试集为空，无法评估 Popular@K")

    hits = 0
    for r in test_list:
        if r.item_idx in top_k_item_indices:
            hits += 1

    hit_rate = hits / len(test_list)
    return hit_rate


def train_mf_model(
    train: Iterable[RatingRecord],
    n_factors: int = 8,
    n_epochs: int = 20,
    lr: float = 0.02,
    reg: float = 0.05,
) -> Tuple[float, Dict[int, float], Dict[int, float], Dict[int, List[float]], Dict[int, List[float]]]:
    """基于评分记录的带偏置矩阵分解（Biased MF）训练。"""

    train_list = list(train)
    if not train_list:
        raise RuntimeError("训练集为空，无法训练 MF 模型")

    user_factors: Dict[int, List[float]] = {}
    item_factors: Dict[int, List[float]] = {}
    user_biases: Dict[int, float] = {}
    item_biases: Dict[int, float] = {}

    rating_sum = 0.0
    for r in train_list:
        rating_sum += float(r.rating)
    global_mean = rating_sum / float(len(train_list))

    def _init_vector() -> List[float]:
        return [0.1 * (random.random() - 0.5) for _ in range(n_factors)]

    for r in train_list:
        uid = r.user_idx
        iid = r.item_idx
        if uid not in user_factors:
            user_factors[uid] = _init_vector()
            user_biases[uid] = 0.0
        if iid not in item_factors:
            item_factors[iid] = _init_vector()
            item_biases[iid] = 0.0

    for _ in range(n_epochs):
        random.shuffle(train_list)
        for r in train_list:
            uid = r.user_idx
            iid = r.item_idx
            rating = float(r.rating)

            pu = user_factors.get(uid)
            qi = item_factors.get(iid)
            if pu is None or qi is None:
                continue

            bu = user_biases.get(uid, 0.0)
            bi = item_biases.get(iid, 0.0)

            pred = global_mean + bu + bi + sum(p * q for p, q in zip(pu, qi))
            err = rating - pred

            user_biases[uid] = bu + lr * (err - reg * bu)
            item_biases[iid] = bi + lr * (err - reg * bi)

            for k_idx in range(n_factors):
                p_k = pu[k_idx]
                q_k = qi[k_idx]
                pu[k_idx] += lr * (err * q_k - reg * p_k)
                qi[k_idx] += lr * (err * p_k - reg * q_k)

    return global_mean, user_biases, item_biases, user_factors, item_factors


def evaluate_mf_hit_rate(
    train: Iterable[RatingRecord],
    test: Iterable[RatingRecord],
    global_mean: float,
    user_biases: Dict[int, float],
    item_biases: Dict[int, float],
    user_factors: Dict[int, List[float]],
    item_factors: Dict[int, List[float]],
    k: int,
) -> float:
    """在 leave-one-out 测试集上评估 MF@K 的命中率（HitRate@K）。"""

    if k <= 0:
        raise ValueError("k 必须为正整数")

    train_list = list(train)
    test_list = list(test)
    if not test_list:
        raise RuntimeError("测试集为空，无法评估 MF@K")

    history_by_user: Dict[int, set[int]] = {}
    all_item_indices: set[int] = set()

    for r in train_list:
        uid = r.user_idx
        iid = r.item_idx
        all_item_indices.add(iid)
        history_by_user.setdefault(uid, set()).add(iid)

    all_items = sorted(all_item_indices)

    hits = 0
    total = 0

    for r in test_list:
        uid = r.user_idx
        true_iid = r.item_idx

        pu = user_factors.get(uid)
        if pu is None:
            continue

        history = history_by_user.get(uid, set())
        candidates: List[Tuple[int, float]] = []

        bu = user_biases.get(uid, 0.0)

        for iid in all_items:
            if iid in history:
                continue
            qi = item_factors.get(iid)
            if qi is None:
                continue
            bi = item_biases.get(iid, 0.0)
            score = global_mean + bu + bi + sum(p * q for p, q in zip(pu, qi))
            candidates.append((iid, score))

        if not candidates:
            continue

        candidates.sort(key=lambda t: (-t[1], t[0]))
        top_k = {iid for iid, _ in candidates[:k]}

        total += 1
        if true_iid in top_k:
            hits += 1

    if total == 0:
        logger.warning("没有可评估的用户，无法计算 MF@K 命中率，本次返回 0.0")
        return 0.0

    return hits / float(total)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "基于 TripAdvisor 酒店评论 CSV 的离线热门推荐实验："
            "加载部分评分数据，构建 leave-one-out 划分，并评估 Popular@K 的命中率。"
        )
    )

    default_root = _default_project_root()
    default_csv = default_root / "data" / "public" / "tripadvisor" / "hotel_reviews.csv"

    parser.add_argument(
        "--csv",
        type=Path,
        default=default_csv,
        help=(
            "TripAdvisor 酒店评论 CSV 文件路径（默认：项目根目录 data/public/tripadvisor/hotel_reviews.csv）"
        ),
    )
    parser.add_argument(
        "--user-col",
        type=str,
        default="user_id",
        help="用户 ID 列名，默认 user_id",
    )
    parser.add_argument(
        "--item-col",
        type=str,
        default="hotel_id",
        help="酒店 ID 列名，默认 hotel_id",
    )
    parser.add_argument(
        "--rating-col",
        type=str,
        default="rating",
        help="评分列名，默认 rating",
    )
    parser.add_argument(
        "--date-col",
        type=str,
        default="date",
        help="时间列名，默认 date",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=50_000,
        help="最多读取的评分条数（避免一次性载入过大数据，默认 50000）",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="评估 Popular@K 时的 K（默认 10）",
    )

    args = parser.parse_args()

    csv_path: Path = args.csv
    user_col: str = args.user_col
    item_col: str = args.item_col
    rating_col: str = args.rating_col
    date_col: str = args.date_col
    max_reviews: Optional[int] = args.max_reviews
    k: int = args.topk

    logger.info("项目根目录推断为: %s", default_root)
    logger.info("使用 CSV 文件: %s", csv_path)

    records, _user_index, _item_index = load_tripadvisor_ratings(
        csv_path,
        user_col=user_col,
        item_col=item_col,
        rating_col=rating_col,
        date_col=date_col,
        max_reviews=max_reviews,
    )
    train, test = build_train_test_split(records)

    popular_stats = compute_popular_items(train)
    logger.info("训练集中可用酒店数: %d", len(popular_stats))

    popular_hit = evaluate_popular_hit_rate(popular_stats, test, k=k)

    logger.info("=== TripAdvisor Popular@%d 离线评估结果 ===", k)
    logger.info("测试用户数: %d", len(test))
    logger.info(
        "Popular HitRate@%d (最后一条评分被 Top-%d 热门酒店命中比例): %.4f",
        k,
        k,
        popular_hit,
    )

    global_mean, user_biases, item_biases, user_factors, item_factors = train_mf_model(train)
    mf_hit = evaluate_mf_hit_rate(
        train,
        test,
        global_mean,
        user_biases,
        item_biases,
        user_factors,
        item_factors,
        k=k,
    )

    logger.info("=== TripAdvisor MF@%d 离线评估结果 ===", k)
    logger.info(
        "MF HitRate@%d (最后一条评分被 MF Top-%d 推荐命中比例): %.4f",
        k,
        k,
        mf_hit,
    )


if __name__ == "__main__":
    main()
