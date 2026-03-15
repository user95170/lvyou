from __future__ import annotations

import argparse
import json
import logging
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")


@dataclass
class RatingRecord:
    """单条评分记录（基于 Yelp review.json 抽取的最小字段）。"""

    user_idx: int
    item_idx: int
    rating: float
    timestamp: datetime


def _default_project_root() -> Path:
    """推断项目根目录（..\..\.. 从 backend/app/pipelines 回到 E:\旅游）。"""

    return Path(__file__).resolve().parents[2].parent


def load_yelp_ratings(
    data_dir: Path,
    max_reviews: int | None = None,
) -> Tuple[List[RatingRecord], Dict[str, int], Dict[str, int]]:
    """从 Yelp Open Dataset 的 review.json 中加载评分数据.

    仅依赖 user_id / business_id / stars / date 四个字段；
    - data_dir 下应存在 review.json（逐行 JSON）。
    - 为避免一次性载入过大数据，可通过 max_reviews 控制最大读取条数。
    """

    review_path = data_dir / "review.json"
    if not review_path.exists():
        raise FileNotFoundError(
            f"未找到 Yelp review.json 文件，请先将 Yelp Open Dataset 的 review.json 放到: {review_path}"
        )

    user_index: Dict[str, int] = {}
    item_index: Dict[str, int] = {}
    records: List[RatingRecord] = []

    logger.info("开始读取 Yelp 评分数据: %s", review_path)

    with review_path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if max_reviews is not None and i >= max_reviews:
                break

            line = line.strip()
            if not line:
                continue

            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            user_id = obj.get("user_id")
            business_id = obj.get("business_id")
            stars = obj.get("stars")
            date_str = obj.get("date")

            if user_id is None or business_id is None or stars is None or date_str is None:
                continue

            try:
                rating = float(stars)
            except (TypeError, ValueError):
                continue

            try:
                ts = datetime.fromisoformat(str(date_str))
            except Exception:  # noqa: BLE001
                continue

            uidx = user_index.setdefault(user_id, len(user_index))
            iidx = item_index.setdefault(business_id, len(item_index))

            records.append(
                RatingRecord(
                    user_idx=uidx,
                    item_idx=iidx,
                    rating=rating,
                    timestamp=ts,
                )
            )

    logger.info(
        "加载完成：%d 条评分记录，%d 个用户，%d 个项目",
        len(records),
        len(user_index),
        len(item_index),
    )

    if not records:
        raise RuntimeError("Yelp 评分数据为空，请检查 review.json 或 max_reviews 限制是否过小")

    return records, user_index, item_index


def build_train_test_split(
    records: Iterable[RatingRecord],
) -> Tuple[List[RatingRecord], List[RatingRecord]]:
    """基于“每个用户最后一次评分作为测试集”的策略划分 train/test.

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
    """基于训练集计算全局热门项目（平均评分 + 评分次数）。

    返回列表元素为 (item_idx, avg_rating, count)，按 avg_rating DESC, count DESC 排序。
    """

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
            "基于 Yelp Open Dataset review.json 的离线热门推荐实验："
            "加载部分评分数据，构建 leave-one-out 划分，并评估 Popular@K 的命中率。"
        )
    )
    default_root = _default_project_root()
    default_data_dir = default_root / "data" / "public" / "yelp"

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=default_data_dir,
        help="Yelp review.json 所在目录（默认：项目根目录下 data/public/yelp）",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=200_000,
        help="最多读取的评分条数（避免一次性载入过大数据，默认 200000）",
    )
    parser.add_argument(
        "--topk",
        type=int,
        default=10,
        help="评估 Popular@K 时的 K（默认 10）",
    )

    args = parser.parse_args()

    data_dir: Path = args.data_dir
    max_reviews: int | None = args.max_reviews
    k: int = args.topk

    logger.info("项目根目录推断为: %s", default_root)
    logger.info("使用数据目录: %s", data_dir)

    records, _user_index, _item_index = load_yelp_ratings(
        data_dir,
        max_reviews=max_reviews,
    )
    train, test = build_train_test_split(records)

    popular_stats = compute_popular_items(train)
    logger.info("训练集中可用项目数: %d", len(popular_stats))

    popular_hit = evaluate_popular_hit_rate(popular_stats, test, k=k)

    logger.info("=== Yelp Popular@%d 离线评估结果 ===", k)
    logger.info("测试用户数: %d", len(test))
    logger.info(
        "Popular HitRate@%d (最后一条评分被 Top-%d 热门命中比例): %.4f",
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

    logger.info("=== Yelp MF@%d 离线评估结果 ===", k)
    logger.info(
        "MF HitRate@%d (最后一条评分被 MF Top-%d 推荐命中比例): %.4f",
        k,
        k,
        mf_hit,
    )


if __name__ == "__main__":
    main()
