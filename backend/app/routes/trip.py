from __future__ import annotations

from datetime import date, datetime, time, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy.orm import selectinload

from ..db import db
from ..models import FoodPlace, Hotel, ScenicSpot, Trip, TripDay, TripItem, User
from ..services.auth_tokens import enforce_user

trip_bp = Blueprint("trip", __name__, url_prefix="/api/trips")

MAX_TRIP_DAYS = 10
COORDINATE_RESOURCE_MODELS = {
    "scenic_spot": ScenicSpot,
    "food_place": FoodPlace,
    "hotel": Hotel,
}


def _parse_user_id(raw) -> tuple[int | None, str | None]:
    try:
        user_id = int(raw)
    except (TypeError, ValueError):
        return None, "valid user_id is required"

    if db.session.get(User, user_id) is None:
        return None, "user not found"

    return user_id, None


def _parse_date(value, field_name: str) -> tuple[date | None, str | None]:
    if value in (None, ""):
        return None, None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date(), None
    except ValueError:
        return None, f"{field_name} must be YYYY-MM-DD"


def _parse_time(value, field_name: str) -> tuple[time | None, str | None]:
    if value in (None, ""):
        return None, None

    text = str(value).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time(), None
        except ValueError:
            continue
    return None, f"{field_name} must be HH:MM or HH:MM:SS"


def _normalize_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _load_trip_for_user(trip_id: int, user_id: int) -> Trip | None:
    return (
        Trip.query.options(
            selectinload(Trip.trip_days).selectinload(TripDay.items)
        )
        .filter_by(id=trip_id, user_id=user_id)
        .first()
    )


def _serialize_trip_detail(trip: Trip) -> dict:
    coordinate_ids: dict[str, set[int]] = {
        item_type: set() for item_type in COORDINATE_RESOURCE_MODELS
    }
    for trip_day in trip.trip_days:
        for item in trip_day.items:
            if item.item_type in coordinate_ids and item.ref_id is not None:
                coordinate_ids[item.item_type].add(int(item.ref_id))

    coordinate_lookup: dict[tuple[str, int], tuple[float | None, float | None]] = {}
    for item_type, model in COORDINATE_RESOURCE_MODELS.items():
        item_ids = coordinate_ids[item_type]
        if not item_ids:
            continue
        resources = model.query.filter(model.id.in_(item_ids)).all()
        for resource in resources:
            coordinate_lookup[(item_type, int(resource.id))] = (
                float(resource.longitude) if resource.longitude is not None else None,
                float(resource.latitude) if resource.latitude is not None else None,
            )

    return trip.to_detail_dict(coordinate_lookup=coordinate_lookup)


def _normalize_trip_days(trip_days_payload) -> tuple[list[dict] | None, str | None]:
    if not isinstance(trip_days_payload, list) or not trip_days_payload:
        return None, "trip_days must contain 1 to 10 days"

    if len(trip_days_payload) > MAX_TRIP_DAYS:
        return None, f"trip_days must contain 1 to {MAX_TRIP_DAYS} days"

    normalized_days: list[dict] = []
    for original_index, day_payload in enumerate(trip_days_payload, start=1):
        if not isinstance(day_payload, dict):
            return None, "trip_days entries must be objects"

        day_index_raw = day_payload.get("day_index", original_index)
        try:
            day_index = int(day_index_raw)
        except (TypeError, ValueError):
            return None, "trip_days[].day_index must be an integer"

        if day_index < 1:
            return None, "trip_days[].day_index must be >= 1"

        items_payload = day_payload.get("items", [])
        if items_payload is None:
            items_payload = []
        if not isinstance(items_payload, list):
            return None, "trip_days[].items must be a list"

        items: list[dict] = []
        for item_position, item_payload in enumerate(items_payload, start=1):
            if not isinstance(item_payload, dict):
                return None, "trip_days[].items entries must be objects"

            item_type = _normalize_text(item_payload.get("item_type"))
            if not item_type:
                return None, "trip_days[].items[].item_type is required"

            title_snapshot = _normalize_text(item_payload.get("title_snapshot"))
            if not title_snapshot:
                return None, "trip_days[].items[].title_snapshot is required"

            item_index_raw = item_payload.get("item_index", item_position)
            try:
                item_index = int(item_index_raw)
            except (TypeError, ValueError):
                return None, "trip_days[].items[].item_index must be an integer"

            if item_index < 1:
                return None, "trip_days[].items[].item_index must be >= 1"

            ref_id_raw = item_payload.get("ref_id")
            ref_id = None
            if ref_id_raw not in (None, ""):
                try:
                    ref_id = int(ref_id_raw)
                except (TypeError, ValueError):
                    return None, "trip_days[].items[].ref_id must be an integer"

            start_time, error = _parse_time(
                item_payload.get("start_time"),
                "trip_days[].items[].start_time",
            )
            if error:
                return None, error

            end_time, error = _parse_time(
                item_payload.get("end_time"),
                "trip_days[].items[].end_time",
            )
            if error:
                return None, error

            items.append(
                {
                    "item_index": item_index,
                    "item_type": item_type,
                    "ref_id": ref_id,
                    "title_snapshot": title_snapshot,
                    "city_snapshot": _normalize_text(item_payload.get("city_snapshot")),
                    "address_snapshot": _normalize_text(item_payload.get("address_snapshot")),
                    "start_time": start_time,
                    "end_time": end_time,
                    "transport_mode": _normalize_text(item_payload.get("transport_mode")),
                    "note": _normalize_text(item_payload.get("note")),
                }
            )

        items.sort(key=lambda item: (item["item_index"], item["title_snapshot"]))
        for normalized_item_index, item in enumerate(items, start=1):
            item["item_index"] = normalized_item_index

        normalized_days.append(
            {
                "day_index": day_index,
                "note": _normalize_text(day_payload.get("note")),
                "items": items,
            }
        )

    normalized_days.sort(key=lambda day: day["day_index"])
    for normalized_day_index, day in enumerate(normalized_days, start=1):
        day["day_index"] = normalized_day_index

    return normalized_days, None


def _apply_trip_fields(
    trip: Trip,
    data: dict,
    *,
    require_title: bool = False,
    require_origin_city: bool = False,
) -> str | None:
    if require_title or "title" in data:
        title = _normalize_text(data.get("title"))
        if not title:
            return "title is required"
        trip.title = title

    if require_origin_city or "origin_city" in data:
        origin_city = _normalize_text(data.get("origin_city"))
        if not origin_city:
            return "origin_city is required"
        trip.origin_city = origin_city

    if "budget_level" in data:
        budget_raw = data.get("budget_level")
        if budget_raw in (None, ""):
            trip.budget_level = None
        else:
            try:
                trip.budget_level = int(budget_raw)
            except (TypeError, ValueError):
                return "budget_level must be an integer"

    if "travel_style" in data:
        trip.travel_style = _normalize_text(data.get("travel_style"))

    return None


def _replace_trip_days(trip: Trip, trip_days: list[dict]) -> None:
    trip.trip_days.clear()
    for day_payload in trip_days:
        trip_day = TripDay(
            day_index=day_payload["day_index"],
            note=day_payload["note"],
        )
        for item_payload in day_payload["items"]:
            trip_day.items.append(
                TripItem(
                    item_index=item_payload["item_index"],
                    item_type=item_payload["item_type"],
                    ref_id=item_payload["ref_id"],
                    title_snapshot=item_payload["title_snapshot"],
                    city_snapshot=item_payload["city_snapshot"],
                    address_snapshot=item_payload["address_snapshot"],
                    start_time=item_payload["start_time"],
                    end_time=item_payload["end_time"],
                    transport_mode=item_payload["transport_mode"],
                    note=item_payload["note"],
                )
            )
        trip.trip_days.append(trip_day)


def _sync_trip_schedule(trip: Trip) -> None:
    trip.days = len(trip.trip_days)

    if trip.start_date and trip.days > 0:
        for trip_day in trip.trip_days:
            trip_day.date = trip.start_date + timedelta(days=trip_day.day_index - 1)
        trip.end_date = trip.start_date + timedelta(days=trip.days - 1)
    else:
        for trip_day in trip.trip_days:
            trip_day.date = None
        trip.end_date = None


@trip_bp.get("")
def list_trips():
    user_id, error = _parse_user_id(request.args.get("user_id"))
    if error:
        return jsonify({"error": error}), 400

    trips = (
        Trip.query.options(selectinload(Trip.trip_days).selectinload(TripDay.items))
        .filter_by(user_id=user_id)
        .order_by(Trip.updated_at.desc(), Trip.id.desc())
        .all()
    )
    return jsonify({"items": [trip.to_summary_dict() for trip in trips]})


@trip_bp.get("/<int:trip_id>")
def get_trip(trip_id: int):
    user_id, error = _parse_user_id(request.args.get("user_id"))
    if error:
        return jsonify({"error": error}), 400

    trip = _load_trip_for_user(trip_id, user_id)
    if trip is None:
        return jsonify({"error": "trip not found"}), 404

    return jsonify({"trip": _serialize_trip_detail(trip)})


@trip_bp.post("")
def create_trip():
    data = request.get_json(silent=True) or {}

    user_id, error = _parse_user_id(data.get("user_id"))
    if error:
        return jsonify({"error": error}), 400

    auth_error = enforce_user(user_id)
    if auth_error is not None:
        return auth_error

    start_date, error = _parse_date(data.get("start_date"), "start_date")
    if error:
        return jsonify({"error": error}), 400

    trip_days, error = _normalize_trip_days(data.get("trip_days"))
    if error:
        return jsonify({"error": error}), 400

    trip = Trip(
        user_id=user_id,
        start_date=start_date,
        created_by=_normalize_text(data.get("created_by")) or "route_planner",
    )
    error = _apply_trip_fields(
        trip,
        data,
        require_title=True,
        require_origin_city=True,
    )
    if error:
        return jsonify({"error": error}), 400

    _replace_trip_days(trip, trip_days)
    _sync_trip_schedule(trip)

    db.session.add(trip)
    db.session.commit()

    saved_trip = _load_trip_for_user(trip.id, user_id)
    return jsonify({"trip": _serialize_trip_detail(saved_trip)}), 201


@trip_bp.put("/<int:trip_id>")
def update_trip(trip_id: int):
    data = request.get_json(silent=True) or {}

    user_id, error = _parse_user_id(data.get("user_id"))
    if error:
        return jsonify({"error": error}), 400

    auth_error = enforce_user(user_id)
    if auth_error is not None:
        return auth_error

    trip = _load_trip_for_user(trip_id, user_id)
    if trip is None:
        return jsonify({"error": "trip not found"}), 404

    if "start_date" in data:
        start_date, error = _parse_date(data.get("start_date"), "start_date")
        if error:
            return jsonify({"error": error}), 400
        trip.start_date = start_date

    error = _apply_trip_fields(trip, data)
    if error:
        return jsonify({"error": error}), 400

    if "trip_days" in data:
        trip_days, error = _normalize_trip_days(data.get("trip_days"))
        if error:
            return jsonify({"error": error}), 400
        _replace_trip_days(trip, trip_days)

    _sync_trip_schedule(trip)
    db.session.commit()

    saved_trip = _load_trip_for_user(trip.id, user_id)
    return jsonify({"trip": _serialize_trip_detail(saved_trip)})


@trip_bp.delete("/<int:trip_id>")
def delete_trip(trip_id: int):
    user_id, error = _parse_user_id(request.args.get("user_id"))
    if error:
        return jsonify({"error": error}), 400

    auth_error = enforce_user(user_id)
    if auth_error is not None:
        return auth_error

    trip = _load_trip_for_user(trip_id, user_id)
    if trip is None:
        return jsonify({"error": "trip not found"}), 404

    db.session.delete(trip)
    db.session.commit()
    return jsonify({"deleted": True, "trip_id": trip_id})
