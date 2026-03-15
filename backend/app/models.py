from __future__ import annotations

from datetime import datetime, timezone

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
