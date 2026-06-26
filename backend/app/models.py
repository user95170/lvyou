from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import BigInteger, Integer

from .db import db
from werkzeug.security import check_password_hash, generate_password_hash


def _utcnow() -> datetime:
    # Use timezone-aware UTC and drop tzinfo for DB compatibility
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ScenicSpot(db.Model):
    """景点表 scenic_spot 对应的 ORM 模型。

    只包含当前接口需要的字段，后续可以按需要扩展。
    """

    __tablename__ = "scenic_spot"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100))
    district = db.Column(db.String(100))
    address = db.Column(db.String(255))
    longitude = db.Column(db.Numeric(10, 6))
    latitude = db.Column(db.Numeric(10, 6))
    # 数据库中列名为 type，这里用 category 映射以避免与内置 type 混淆
    category = db.Column("type", db.String(100))
    tags = db.Column(db.Text)
    opening_hours = db.Column(db.String(200))
    ticket_price = db.Column(db.Numeric(10, 2))
    rating_avg = db.Column(db.Numeric(3, 2))
    rating_count = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)
    images = db.Column(db.Text)
    status = db.Column(db.SmallInteger, default=1)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    def to_dict(self) -> dict:
        """转为可 JSON 序列化的字典，供接口返回使用。"""

        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "type": self.category,
            "tags": self.tags,
            "opening_hours": self.opening_hours,
            "ticket_price": float(self.ticket_price)
            if self.ticket_price is not None
            else None,
            "rating_avg": float(self.rating_avg) if self.rating_avg is not None else None,
            "rating_count": self.rating_count,
            "description": self.description,
            "images": self.images,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Hotel(db.Model):
    __tablename__ = "hotel"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100))
    district = db.Column(db.String(100))
    address = db.Column(db.String(255))
    longitude = db.Column(db.Numeric(10, 6))
    latitude = db.Column(db.Numeric(10, 6))
    star_level = db.Column(db.String(50))
    avg_price = db.Column(db.Numeric(10, 2))
    rating_avg = db.Column(db.Numeric(3, 2))
    rating_count = db.Column(db.Integer, default=0)
    tags = db.Column(db.Text)
    source = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "star_level": self.star_level,
            "avg_price": float(self.avg_price) if self.avg_price is not None else None,
            "rating_avg": float(self.rating_avg) if self.rating_avg is not None else None,
            "rating_count": self.rating_count,
            "tags": self.tags,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class User(db.Model):
    """用户表 user 对应的 ORM 模型。"""

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(20))
    gender = db.Column(db.Enum("unknown", "male", "female", name="gender_enum"), default="unknown")
    age = db.Column(db.Integer)
    home_region = db.Column(db.String(100))
    register_source = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class UserProfile(db.Model):
    """用户画像表 user_profile 对应的 ORM 模型。"""

    __tablename__ = "user_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    cluster_id = db.Column(db.Integer)
    prefer_scenic_types = db.Column(db.Text)
    prefer_food_types = db.Column(db.Text)
    travel_style = db.Column(db.String(50))
    budget_level = db.Column(db.Integer)
    travel_frequency = db.Column(db.Integer)
    feature_vector = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "cluster_id": self.cluster_id,
            "prefer_scenic_types": self.prefer_scenic_types,
            "prefer_food_types": self.prefer_food_types,
            "travel_style": self.travel_style,
            "budget_level": self.budget_level,
            "travel_frequency": self.travel_frequency,
            "feature_vector": self.feature_vector,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FoodPlace(db.Model):
    __tablename__ = "food_place"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100))
    district = db.Column(db.String(100))
    address = db.Column(db.String(255))
    longitude = db.Column(db.Numeric(10, 6))
    latitude = db.Column(db.Numeric(10, 6))
    cuisine_type = db.Column(db.String(100))
    avg_price = db.Column(db.Numeric(10, 2))
    rating_avg = db.Column(db.Numeric(3, 2))
    rating_count = db.Column(db.Integer, default=0)
    tags = db.Column(db.Text)
    source = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "cuisine_type": self.cuisine_type,
            "avg_price": float(self.avg_price) if self.avg_price is not None else None,
            "rating_avg": float(self.rating_avg) if self.rating_avg is not None else None,
            "rating_count": self.rating_count,
            "tags": self.tags,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Trip(db.Model):
    __tablename__ = "trip"

    id = db.Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    days = db.Column(db.Integer)
    origin_city = db.Column(db.String(100))
    budget_level = db.Column(db.Integer)
    travel_style = db.Column(db.String(50))
    created_by = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=_utcnow,
        onupdate=_utcnow,
    )

    trip_days = db.relationship(
        "TripDay",
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="TripDay.day_index",
    )

    def item_count(self) -> int:
        return sum(len(day.items) for day in self.trip_days)

    def to_summary_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "days": self.days,
            "origin_city": self.origin_city,
            "budget_level": self.budget_level,
            "travel_style": self.travel_style,
            "created_by": self.created_by,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "item_count": self.item_count(),
        }

    def to_detail_dict(self, coordinate_lookup: dict | None = None) -> dict:
        data = self.to_summary_dict()
        data.update(
            {
                "user_id": self.user_id,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "trip_days": [
                    day.to_dict(coordinate_lookup=coordinate_lookup)
                    for day in self.trip_days
                ],
            }
        )
        return data


class TripDay(db.Model):
    __tablename__ = "trip_day"

    id = db.Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    trip_id = db.Column(
        BigInteger().with_variant(Integer, "sqlite"),
        db.ForeignKey("trip.id"),
        nullable=False,
        index=True,
    )
    day_index = db.Column(db.Integer, nullable=False)
    date = db.Column(db.Date)
    note = db.Column(db.String(255))

    trip = db.relationship("Trip", back_populates="trip_days")
    items = db.relationship(
        "TripItem",
        back_populates="trip_day",
        cascade="all, delete-orphan",
        order_by="TripItem.item_index",
    )

    def to_dict(self, coordinate_lookup: dict | None = None) -> dict:
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "day_index": self.day_index,
            "date": self.date.isoformat() if self.date else None,
            "note": self.note,
            "items": [
                item.to_dict(coordinate_lookup=coordinate_lookup)
                for item in self.items
            ],
        }


class TripItem(db.Model):
    __tablename__ = "trip_item"

    id = db.Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    trip_day_id = db.Column(
        BigInteger().with_variant(Integer, "sqlite"),
        db.ForeignKey("trip_day.id"),
        nullable=False,
        index=True,
    )
    item_index = db.Column(db.Integer, nullable=False)
    item_type = db.Column(db.String(50), nullable=False)
    ref_id = db.Column(db.Integer)
    title_snapshot = db.Column(db.String(255), nullable=False)
    city_snapshot = db.Column(db.String(100))
    address_snapshot = db.Column(db.String(255))
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    transport_mode = db.Column(db.String(20))
    note = db.Column(db.String(255))

    trip_day = db.relationship("TripDay", back_populates="items")

    @staticmethod
    def _serialize_time(value: time | None) -> str | None:
        if value is None:
            return None
        return value.strftime("%H:%M")

    def to_dict(self, coordinate_lookup: dict | None = None) -> dict:
        longitude = None
        latitude = None
        if coordinate_lookup and self.ref_id is not None:
            longitude, latitude = coordinate_lookup.get(
                (self.item_type, self.ref_id),
                (None, None),
            )
        return {
            "id": self.id,
            "trip_day_id": self.trip_day_id,
            "item_index": self.item_index,
            "item_type": self.item_type,
            "ref_id": self.ref_id,
            "title_snapshot": self.title_snapshot,
            "city_snapshot": self.city_snapshot,
            "address_snapshot": self.address_snapshot,
            "start_time": self._serialize_time(self.start_time),
            "end_time": self._serialize_time(self.end_time),
            "transport_mode": self.transport_mode,
            "note": self.note,
            "longitude": longitude,
            "latitude": latitude,
        }


class UserBehaviorLog(db.Model):
    """用户行为日志 user_behavior_log 对应的 ORM 模型。"""

    __tablename__ = "user_behavior_log"

    id = db.Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    behavior_type = db.Column(db.String(50), nullable=False)
    behavior_value = db.Column(db.Numeric(10, 2))
    device = db.Column(db.String(100))
    ip = db.Column(db.String(45))
    occurred_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "behavior_type": self.behavior_type,
            "behavior_value": float(self.behavior_value)
            if self.behavior_value is not None
            else None,
            "device": self.device,
            "ip": self.ip,
            "occurred_at": self.occurred_at.isoformat() if self.occurred_at else None,
        }


class Rating(db.Model):
    """通用评分表 rating 对应的 ORM 模型。"""

    __tablename__ = "rating"

    id = db.Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "score": self.score,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ContentStandard(db.Model):
    """标准化内容表 content_standard 对应的 ORM 模型。

    用于聚合各类内容（景点/酒店/美食等）的综合信息和指标，
    例如受欢迎度评分、情感得分等，便于推荐和分析使用。
    """

    __tablename__ = "content_standard"

    id = db.Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    source_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255))
    summary = db.Column(db.Text)
    sentiment_score = db.Column(db.Numeric(4, 3))
    popularity_score = db.Column(db.Numeric(6, 3))
    last_update = db.Column(
        db.DateTime,
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "source_type": self.source_type,
            "title": self.title,
            "summary": self.summary,
            "sentiment_score": float(self.sentiment_score)
            if self.sentiment_score is not None
            else None,
            "popularity_score": float(self.popularity_score)
            if self.popularity_score is not None
            else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
        }


class Transportation(db.Model):
    """交通节点表 transportation（车站/机场/地铁站/接驳点等）。"""

    __tablename__ = "transportation"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), index=True)
    district = db.Column(db.String(100))
    address = db.Column(db.String(255))
    longitude = db.Column(db.Numeric(10, 6))
    latitude = db.Column(db.Numeric(10, 6))
    transport_type = db.Column(db.String(50))  # 车站/机场/地铁站/接驳车/换乘点
    phone = db.Column(db.String(50))  # 客服热线
    operating_hours = db.Column(db.String(200))  # 运营/首末班时间
    price_info = db.Column(db.String(200))  # 预期消费（车费/打车估算）
    rating_avg = db.Column(db.Numeric(3, 2))
    rating_count = db.Column(db.Integer, default=0)
    tags = db.Column(db.Text)
    description = db.Column(db.Text)
    source = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "transport_type": self.transport_type,
            "phone": self.phone,
            "operating_hours": self.operating_hours,
            "price_info": self.price_info,
            "rating_avg": float(self.rating_avg) if self.rating_avg is not None else None,
            "rating_count": self.rating_count,
            "tags": self.tags,
            "description": self.description,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Activity(db.Model):
    """活动表 activity（节庆/演出/临时展览等）。"""

    __tablename__ = "activity"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), index=True)
    district = db.Column(db.String(100))
    address = db.Column(db.String(255))
    longitude = db.Column(db.Numeric(10, 6))
    latitude = db.Column(db.Numeric(10, 6))
    activity_type = db.Column(db.String(50))  # 节庆/演出/展览/赛事
    phone = db.Column(db.String(50))
    hold_time = db.Column(db.String(200))  # 举办时间段
    price_info = db.Column(db.String(200))  # 门票/参与费用
    rating_avg = db.Column(db.Numeric(3, 2))
    rating_count = db.Column(db.Integer, default=0)
    tags = db.Column(db.Text)  # 适配人群等标签
    description = db.Column(db.Text)  # 简介与参与说明
    source = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "activity_type": self.activity_type,
            "phone": self.phone,
            "hold_time": self.hold_time,
            "price_info": self.price_info,
            "rating_avg": float(self.rating_avg) if self.rating_avg is not None else None,
            "rating_count": self.rating_count,
            "tags": self.tags,
            "description": self.description,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Specialty(db.Model):
    """特产表 specialty（特色商品/购物点）。"""

    __tablename__ = "specialty"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)  # 商品或店铺
    city = db.Column(db.String(100), index=True)
    district = db.Column(db.String(100))
    address = db.Column(db.String(255))
    longitude = db.Column(db.Numeric(10, 6))
    latitude = db.Column(db.Numeric(10, 6))
    category = db.Column(db.String(50))  # 商品类别：奶制品/手工艺/食品等
    phone = db.Column(db.String(50))
    business_hours = db.Column(db.String(200))
    price_info = db.Column(db.String(200))  # 价格区间
    rating_avg = db.Column(db.Numeric(3, 2))
    rating_count = db.Column(db.Integer, default=0)
    tags = db.Column(db.Text)
    description = db.Column(db.Text)  # 商品特色与推荐说明
    source = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "category": self.category,
            "phone": self.phone,
            "business_hours": self.business_hours,
            "price_info": self.price_info,
            "rating_avg": float(self.rating_avg) if self.rating_avg is not None else None,
            "rating_count": self.rating_count,
            "tags": self.tags,
            "description": self.description,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
