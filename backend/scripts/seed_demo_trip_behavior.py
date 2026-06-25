"""演示数据灌入脚本：为 dev.db 补充行程（trip）与行为日志（behavior）样例。

用途：
    主系统的真实库通常只有景点/酒店/美食与评分数据，trip 与 user_behavior_log
    在没有人工操作时为空。本脚本生成少量可读的演示数据，便于现场演示
    "我的行程 CRUD" 与 "行为分析闭环"，以及监控面板的非零指标。

特点：
    - 幂等：通过 created_by="demo_seed" 与 device="demo_seed" 标记识别，重复运行不会重复插入。
    - 仅依赖库中已存在的景点/酒店/美食，做快照引用，缺数据时自动跳过对应条目。

运行方式：
    cd backend
    python -m scripts.seed_demo_trip_behavior
"""

from __future__ import annotations

from datetime import date, time, timedelta

from app import create_app
from app.db import db
from app.models import (
    FoodPlace,
    Hotel,
    ScenicSpot,
    Trip,
    TripDay,
    TripItem,
    User,
    UserBehaviorLog,
)

TRIP_SEED_MARKER = "demo_seed"
BEHAVIOR_SEED_MARKER = "demo_seed"


def _pick_user() -> User | None:
    user = User.query.filter_by(username="demo").first()
    if user is not None:
        return user
    return User.query.order_by(User.id.asc()).first()


def _spot_to_item(spot: ScenicSpot, item_index: int, **kwargs) -> TripItem:
    return TripItem(
        item_index=item_index,
        item_type="scenic_spot",
        ref_id=spot.id,
        title_snapshot=spot.name,
        city_snapshot=spot.city,
        address_snapshot=spot.address,
        **kwargs,
    )


def _seed_trips(user: User) -> int:
    existing = Trip.query.filter_by(user_id=user.id, created_by=TRIP_SEED_MARKER).count()
    if existing:
        print(f"trips already seeded for user_id={user.id}, skip ({existing} trips)")
        return 0

    spots = (
        ScenicSpot.query.filter(ScenicSpot.city.isnot(None))
        .order_by(ScenicSpot.rating_count.desc().nullslast(), ScenicSpot.id.asc())
        .limit(20)
        .all()
    )
    if len(spots) < 3:
        print("not enough scenic spots in db, skip trip seeding")
        return 0

    city = spots[0].city
    city_spots = [s for s in spots if s.city == city] or spots
    hotel = Hotel.query.filter_by(city=city).first() or Hotel.query.first()
    food = FoodPlace.query.filter_by(city=city).first() or FoodPlace.query.first()

    created = 0

    # 1) 单日行程（模拟从 /route 保存）
    single = Trip(
        user_id=user.id,
        title=f"{city}一日精华游(演示)",
        start_date=date.today(),
        end_date=date.today(),
        days=1,
        origin_city=city,
        budget_level=2,
        travel_style="休闲",
        created_by=TRIP_SEED_MARKER,
    )
    day1 = TripDay(day_index=1, date=date.today(), note="市区景点串联")
    picks = city_spots[:3]
    for idx, spot in enumerate(picks, start=1):
        day1.items.append(
            _spot_to_item(
                spot,
                idx,
                start_time=time(9 + idx, 0),
                end_time=time(10 + idx, 30),
                transport_mode="drive",
            )
        )
    single.trip_days.append(day1)
    db.session.add(single)
    created += 1

    # 2) 多日行程（模拟从 /profile 保存 Agent 草案）
    multi = Trip(
        user_id=user.id,
        title=f"{city}三日深度游(演示)",
        start_date=date.today() + timedelta(days=7),
        end_date=date.today() + timedelta(days=9),
        days=3,
        origin_city=city,
        budget_level=3,
        travel_style="亲子",
        created_by=TRIP_SEED_MARKER,
    )
    spot_cursor = 0
    for d in range(3):
        day = TripDay(
            day_index=d + 1,
            date=date.today() + timedelta(days=7 + d),
            note=f"第{d + 1}天行程",
        )
        item_index = 1
        for _ in range(2):
            if spot_cursor < len(city_spots):
                spot = city_spots[spot_cursor]
                spot_cursor += 1
                day.items.append(
                    _spot_to_item(
                        spot,
                        item_index,
                        start_time=time(9, 0),
                        end_time=time(11, 0),
                        transport_mode="drive",
                    )
                )
                item_index += 1
        if d == 0 and food is not None:
            day.items.append(
                TripItem(
                    item_index=item_index,
                    item_type="food_place",
                    ref_id=food.id,
                    title_snapshot=food.name,
                    city_snapshot=food.city,
                    address_snapshot=food.address,
                    start_time=time(12, 0),
                    end_time=time(13, 0),
                    note="午餐",
                )
            )
            item_index += 1
        if hotel is not None:
            day.items.append(
                TripItem(
                    item_index=item_index,
                    item_type="hotel",
                    ref_id=hotel.id,
                    title_snapshot=hotel.name,
                    city_snapshot=hotel.city,
                    address_snapshot=hotel.address,
                    start_time=time(20, 0),
                    note="入住",
                )
            )
        multi.trip_days.append(day)
    db.session.add(multi)
    created += 1

    db.session.commit()
    print(f"created {created} demo trips for user_id={user.id}")
    return created


def _seed_behaviors(user: User) -> int:
    existing = UserBehaviorLog.query.filter_by(device=BEHAVIOR_SEED_MARKER).count()
    if existing:
        print(f"behavior logs already seeded, skip ({existing} logs)")
        return 0

    spots = ScenicSpot.query.order_by(ScenicSpot.id.asc()).limit(8).all()
    foods = FoodPlace.query.order_by(FoodPlace.id.asc()).limit(3).all()
    if not spots:
        print("no scenic spots in db, skip behavior seeding")
        return 0

    base = db.func.now()  # noqa: F841 - 占位，实际使用默认 occurred_at
    created = 0
    for i, spot in enumerate(spots):
        # 浏览
        db.session.add(
            UserBehaviorLog(
                user_id=user.id,
                target_type="scenic_spot",
                target_id=spot.id,
                behavior_type="view",
                behavior_value=1,
                device=BEHAVIOR_SEED_MARKER,
            )
        )
        created += 1
        # 部分景点产生点击
        if i % 2 == 0:
            db.session.add(
                UserBehaviorLog(
                    user_id=user.id,
                    target_type="scenic_spot",
                    target_id=spot.id,
                    behavior_type="click",
                    behavior_value=1,
                    device=BEHAVIOR_SEED_MARKER,
                )
            )
            created += 1

    for food in foods:
        db.session.add(
            UserBehaviorLog(
                user_id=user.id,
                target_type="food_place",
                target_id=food.id,
                behavior_type="view",
                behavior_value=1,
                device=BEHAVIOR_SEED_MARKER,
            )
        )
        created += 1

    db.session.commit()
    print(f"created {created} demo behavior logs for user_id={user.id}")
    return created


def seed() -> None:
    app = create_app()
    with app.app_context():
        user = _pick_user()
        if user is None:
            print("no user in db, please register or run seed_dev.py first")
            return
        _seed_trips(user)
        _seed_behaviors(user)
        print("demo trip/behavior seeding done")


if __name__ == "__main__":
    seed()
