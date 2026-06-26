from flask import Blueprint, jsonify, request

from ..db import db
from ..models import Specialty
from ..services.demographics import (
    has_demographics,
    load_user_demographics,
    specialty_demographic_adjustment,
)
from ..services.resource_ranking import build_reasons, paginate_personalized

specialty_bp = Blueprint("specialty", __name__, url_prefix="/api/specialties")


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


@specialty_bp.get("")
def list_specialties():
    """特产列表。

    支持参数：city、category、keyword（name/tags）、page、page_size。
    """

    page, page_size = _paging()
    query = Specialty.query

    city = request.args.get("city")
    if city:
        query = query.filter(Specialty.city.like(f"%{city}%"))

    category = request.args.get("category")
    if category:
        query = query.filter(Specialty.category == category)

    keyword = request.args.get("keyword")
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            (Specialty.name.like(like_pattern)) | (Specialty.tags.like(like_pattern))
        )

    query = query.order_by(
        Specialty.rating_avg.desc(),
        Specialty.rating_count.desc(),
        Specialty.id.desc(),
    )

    uid = _parse_uid()
    demo = load_user_demographics(uid) if uid is not None else None
    demo = demo if has_demographics(demo) else None

    items, total = paginate_personalized(
        query, page, page_size, demo, specialty_demographic_adjustment
    )

    result = []
    for item in items:
        data = item.to_dict()
        reasons = build_reasons(item, demo, specialty_demographic_adjustment)
        if reasons:
            data["reasons"] = reasons
        result.append(data)

    return jsonify(
        {
            "items": result,
            "pagination": {"page": page, "page_size": page_size, "total": total},
        }
    )


@specialty_bp.get("/<int:item_id>")
def get_specialty(item_id: int):
    item = db.session.get(Specialty, item_id)
    if item is None:
        return jsonify({"error": "specialty not found"}), 404
    return jsonify(item.to_dict())
