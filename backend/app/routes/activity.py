from flask import Blueprint, jsonify, request

from ..db import db
from ..models import Activity
from ..services.demographics import (
    activity_demographic_adjustment,
    has_demographics,
    load_user_demographics,
)
from ..services.resource_ranking import build_reasons, paginate_personalized

activity_bp = Blueprint("activity", __name__, url_prefix="/api/activities")


def _parse_uid():
    raw = request.args.get("user_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _paging():
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get("page_size", 10))
    except ValueError:
        page_size = 10
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10
    if page_size > 50:
        page_size = 50
    return page, page_size


@activity_bp.get("")
def list_activities():
    """活动列表。

    支持参数：city、activity_type、keyword（name/tags）、page、page_size。
    """

    page, page_size = _paging()
    query = Activity.query

    city = request.args.get("city")
    if city:
        query = query.filter(Activity.city.like(f"%{city}%"))

    activity_type = request.args.get("activity_type")
    if activity_type:
        query = query.filter(Activity.activity_type == activity_type)

    keyword = request.args.get("keyword")
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            (Activity.name.like(like_pattern)) | (Activity.tags.like(like_pattern))
        )

    query = query.order_by(
        Activity.rating_avg.desc(),
        Activity.rating_count.desc(),
        Activity.id.desc(),
    )

    uid = _parse_uid()
    demo = load_user_demographics(uid) if uid is not None else None
    demo = demo if has_demographics(demo) else None

    items, total = paginate_personalized(
        query, page, page_size, demo, activity_demographic_adjustment
    )

    result = []
    for item in items:
        data = item.to_dict()
        reasons = build_reasons(item, demo, activity_demographic_adjustment)
        if reasons:
            data["reasons"] = reasons
        result.append(data)

    return jsonify(
        {
            "items": result,
            "pagination": {"page": page, "page_size": page_size, "total": total},
        }
    )


@activity_bp.get("/<int:item_id>")
def get_activity(item_id: int):
    item = db.session.get(Activity, item_id)
    if item is None:
        return jsonify({"error": "activity not found"}), 404
    return jsonify(item.to_dict())
