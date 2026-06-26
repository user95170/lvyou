from flask import Blueprint, jsonify

from ..models import (
    Activity,
    ContentStandard,
    FoodPlace,
    Hotel,
    Rating,
    ScenicSpot,
    Specialty,
    Transportation,
    Trip,
    User,
    UserBehaviorLog,
    UserProfile,
)
from .recommend import _build_recommend_metrics_payload
from .route import _build_route_metrics_payload

monitor_bp = Blueprint("monitor", __name__, url_prefix="/api/monitor")


def _count(model) -> int:
    return int(model.query.count())


@monitor_bp.get("/overview")
def monitor_overview():
    """Return a compact read-only dashboard payload for demos and ops checks."""

    payload = {
        "health": {"status": "ok"},
        "resources": {
            "scenic_spots": _count(ScenicSpot),
            "hotels": _count(Hotel),
            "foods": _count(FoodPlace),
            "transportations": _count(Transportation),
            "activities": _count(Activity),
            "specialties": _count(Specialty),
            "content_rows": _count(ContentStandard),
        },
        "users": {
            "users": _count(User),
            "profiles": _count(UserProfile),
            "ratings": _count(Rating),
            "behavior_logs": _count(UserBehaviorLog),
            "trips": _count(Trip),
        },
        "recommendation": _build_recommend_metrics_payload(),
        "route": _build_route_metrics_payload(),
    }
    return jsonify(payload)
