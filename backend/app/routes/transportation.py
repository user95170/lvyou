from flask import Blueprint, jsonify, request

from ..db import db
from ..models import Transportation
from ..services.demographics import (
    has_demographics,
    load_user_demographics,
    transportation_demographic_adjustment,
)
from ..services.resource_ranking import build_reasons, paginate_personalized

transportation_bp = Blueprint("transportation", __name__, url_prefix="/api/transportations")


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


@transportation_bp.get("")
def list_transportations():
    """交通节点列表。

    支持参数：city、transport_type、keyword（name/tags）、page、page_size。
    """

    page, page_size = _paging()
    query = Transportation.query

    city = request.args.get("city")
    if city:
        query = query.filter(Transportation.city.like(f"%{city}%"))

    transport_type = request.args.get("transport_type")
    if transport_type:
        query = query.filter(Transportation.transport_type == transport_type)

    keyword = request.args.get("keyword")
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            (Transportation.name.like(like_pattern))
            | (Transportation.tags.like(like_pattern))
        )

    query = query.order_by(
        Transportation.rating_avg.desc(),
        Transportation.rating_count.desc(),
        Transportation.id.desc(),
    )

    uid = _parse_uid()
    demo = load_user_demographics(uid) if uid is not None else None
    demo = demo if has_demographics(demo) else None

    items, total = paginate_personalized(
        query, page, page_size, demo, transportation_demographic_adjustment
    )

    result = []
    for item in items:
        data = item.to_dict()
        reasons = build_reasons(item, demo, transportation_demographic_adjustment)
        if reasons:
            data["reasons"] = reasons
        result.append(data)

    return jsonify(
        {
            "items": result,
            "pagination": {"page": page, "page_size": page_size, "total": total},
        }
    )


@transportation_bp.get("/<int:item_id>")
def get_transportation(item_id: int):
    item = db.session.get(Transportation, item_id)
    if item is None:
        return jsonify({"error": "transportation not found"}), 404
    return jsonify(item.to_dict())
