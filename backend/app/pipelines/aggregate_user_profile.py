from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from .. import create_app
from ..db import db
from ..models import Rating, ScenicSpot, FoodPlace, UserProfile


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _build_profile_for_user(user_id: int) -> None:
    ratings = Rating.query.filter_by(user_id=user_id).all()

    if not ratings:
        return

    scenic_counter: Counter[str] = Counter()
    food_counter: Counter[str] = Counter()

    for r in ratings:
        if r.target_type == "scenic_spot":
            spot = ScenicSpot.query.get(r.target_id)
            if spot is None or spot.category is None:
                continue
            scenic_counter[spot.category] += int(r.score or 0)
        elif r.target_type == "food_place":
            food = FoodPlace.query.get(r.target_id)
            if food is None or food.cuisine_type is None:
                continue
            food_counter[food.cuisine_type] += int(r.score or 0)

    prefer_scenic = ",".join(t for t, _ in scenic_counter.most_common(5)) or None
    prefer_food = ",".join(t for t, _ in food_counter.most_common(5)) or None
    travel_frequency = len(ratings)

    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.session.add(profile)

    profile.prefer_scenic_types = prefer_scenic
    profile.prefer_food_types = prefer_food
    profile.travel_frequency = travel_frequency
    profile.updated_at = _utcnow()


def aggregate_all() -> None:
    user_ids = [uid for (uid,) in db.session.query(Rating.user_id).distinct() if uid is not None]
    for uid in user_ids:
        _build_profile_for_user(uid)
    db.session.commit()


def main() -> None:
    app = create_app()
    with app.app_context():
        aggregate_all()


if __name__ == "__main__":
    main()
