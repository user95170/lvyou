from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Tuple

from .. import create_app
from ..db import db
from ..models import Rating, ScenicSpot, User, UserProfile


NUM_SYNTHETIC_USERS = 30
MIN_RATINGS_PER_USER = 20
MAX_RATINGS_PER_USER = 50
LATENT_DIM = 8
GLOBAL_MEAN = 3.5
LATENT_SCALE = 0.5
NOISE_STD = 0.3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _random_datetime(days_back: int = 180) -> datetime:
    now = _utcnow()
    delta_days = random.randint(0, days_back)
    delta_seconds = random.randint(0, 24 * 3600 - 1)
    return now - timedelta(days=delta_days, seconds=delta_seconds)


def _init_latent_vectors(ids: Iterable[int], k: int) -> Dict[int, List[float]]:
    return {i: [random.gauss(0.0, 1.0) for _ in range(k)] for i in ids}


def _ensure_synthetic_users(categories: List[str]) -> List[User]:
    """确保存在一批用于实验的模拟用户。

    - 通过 User.register_source = "synthetic" 标记。
    - 如已存在，则直接复用；不足时补齐到 NUM_SYNTHETIC_USERS 个。
    - 为新建用户同步创建简单的 UserProfile 画像（偏好类型等）。
    """

    synthetic_users = User.query.filter_by(register_source="synthetic").all()
    if len(synthetic_users) >= NUM_SYNTHETIC_USERS:
        return synthetic_users

    existing_usernames = {u.username for u in User.query.all()}
    created: List[User] = []
    idx = 1

    travel_styles = ["轻松休闲", "深度体验", "亲子游", "拍照打卡"]
    budget_levels = [1, 2, 3, 4]

    while len(synthetic_users) + len(created) < NUM_SYNTHETIC_USERS:
        username = f"synthetic_user_{idx}"
        idx += 1
        if username in existing_usernames:
            continue

        user = User(
            username=username,
            email=None,
            phone=None,
            gender=random.choice(["male", "female", "unknown"]),
            age=random.randint(18, 60),
            home_region=random.choice(["内蒙古", "北京", "上海", "广东", "江苏"]),
            register_source="synthetic",
        )
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()  # 获取 user.id

        if categories:
            k = random.randint(1, min(3, len(categories)))
            prefer = random.sample(categories, k=k)
            prefer_str = ",".join(prefer)
        else:
            prefer_str = None

        profile = UserProfile(
            user_id=user.id,
            prefer_scenic_types=prefer_str,
            travel_style=random.choice(travel_styles),
            budget_level=random.choice(budget_levels),
            travel_frequency=random.randint(1, 10),
        )
        db.session.add(profile)

        created.append(user)
        existing_usernames.add(username)

    return synthetic_users + created


def _clear_old_synthetic_ratings() -> None:
    """删除历史上标记为模拟数据的景点评分，便于重复实验。"""

    Rating.query.filter(Rating.target_type == "scenic_spot").filter(
        Rating.comment == "[synthetic]"
    ).delete(synchronize_session=False)


def _generate_ratings_for_users(users: List[User], scenic_spots: List[ScenicSpot]) -> None:
    if not users or not scenic_spots:
        return

    # 预备：景点信息与类别列表
    scenic_by_id = {s.id: s for s in scenic_spots}
    scenic_ids = list(scenic_by_id.keys())

    # 用现有 rating_count 构造一个简单的受欢迎度权重，近似热门/长尾分布
    scenic_weights: List[float] = []
    for s in scenic_spots:
        try:
            cnt = float(s.rating_count or 0)
        except (TypeError, ValueError):
            cnt = 0.0
        scenic_weights.append(1.0 + cnt)

    # 用户画像映射
    profiles = {p.user_id: p for p in UserProfile.query.all()}

    # 初始化潜在因子
    user_ids = [u.id for u in users]
    user_factors = _init_latent_vectors(user_ids, LATENT_DIM)
    item_factors = _init_latent_vectors(scenic_ids, LATENT_DIM)

    for user in users:
        uid = user.id
        if uid is None:
            continue

        n_ratings = random.randint(MIN_RATINGS_PER_USER, MAX_RATINGS_PER_USER)
        # popularity 加权采样，放大热门景点被选中的概率
        sampled_ids = random.choices(scenic_ids, weights=scenic_weights, k=n_ratings * 2)
        # 去重，保留前 n_ratings 个不同的景点
        seen = set()
        user_scenics: List[int] = []
        for sid in sampled_ids:
            if sid in seen:
                continue
            seen.add(sid)
            user_scenics.append(sid)
            if len(user_scenics) >= n_ratings:
                break

        profile = profiles.get(uid)
        prefer_types: List[str] = []
        if profile and profile.prefer_scenic_types:
            parts = []
            for sep in [",", ";"]:
                parts.extend([t.strip() for t in profile.prefer_scenic_types.split(sep)])
            prefer_types = [t for t in parts if t]

        for sid in user_scenics:
            spot = scenic_by_id.get(sid)
            if spot is None:
                continue

            # 潜在因子打分
            pu = user_factors[uid]
            qi = item_factors[sid]
            dot = sum(p * q for p, q in zip(pu, qi))

            score = GLOBAL_MEAN + LATENT_SCALE * dot

            # 简单的类型偏好加成
            if spot.category and prefer_types and spot.category in prefer_types:
                score += 0.6

            # 简单的地域加成：家乡与景点城市相同
            if user.home_region and spot.city and user.home_region in spot.city:
                score += 0.3

            # 噪声
            score += random.gauss(0.0, NOISE_STD)

            # 限制在 [1, 5] 区间并四舍五入到整数
            score = max(1.0, min(5.0, score))
            int_score = int(round(score))
            if int_score < 1:
                int_score = 1
            elif int_score > 5:
                int_score = 5

            rating = Rating(
                user_id=uid,
                target_type="scenic_spot",
                target_id=sid,
                score=int_score,
                comment="[synthetic]",
                created_at=_random_datetime(days_back=180),
            )
            db.session.add(rating)


def generate_all() -> None:
    random.seed(42)

    scenic_spots = ScenicSpot.query.all()
    if not scenic_spots:
        print("[WARN] 没有景点数据，无法生成评分。")
        return

    categories = sorted({s.category for s in scenic_spots if s.category})

    # 确保存在一批 synthetic 用户
    synthetic_users = _ensure_synthetic_users(categories)

    # 所有用户（真实 + synthetic）都参与评分生成
    all_users = User.query.all()

    # 清理历史模拟评分
    _clear_old_synthetic_ratings()

    _generate_ratings_for_users(all_users, scenic_spots)
    db.session.commit()
    print(f"[OK] 已为 {len(all_users)} 个用户生成模拟景点评分（包含 synthetic 用户 {len(synthetic_users)} 个）。")


def main() -> None:
    app = create_app()
    with app.app_context():
        generate_all()


if __name__ == "__main__":
    main()
