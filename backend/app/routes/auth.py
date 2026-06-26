from flask import Blueprint, jsonify, request

from ..db import db
from ..models import User
from ..services.demographics import parse_demographics_payload as _parse_demographics
from ..services.auth_tokens import generate_token

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/register")
def register():
    """用户注册接口。

    请求 JSON 示例：
    {
      "username": "zhangsan",
      "password": "123456",
      "email": "zhangsan@example.com",  # 可选
      "phone": "13800000000"            # 可选
    }
    """

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    email = (data.get("email") or None) or None
    phone = (data.get("phone") or None) or None

    if not username or not password:
        return (
            jsonify({"error": "username and password are required"}),
            400,
        )

    # 简单长度校验
    if len(username) < 3 or len(password) < 6:
        return (
            jsonify({"error": "username must be >=3 chars and password >=6 chars"}),
            400,
        )

    # 可选人口特征（性别/年龄/地域），用于细粒度个性化推荐
    gender, age, home_region, demo_error = _parse_demographics(data)
    if demo_error is not None:
        return jsonify({"error": demo_error}), 400

    # 唯一性检查
    if User.query.filter_by(username=username).first() is not None:
        return jsonify({"error": "username already exists"}), 400

    if email and User.query.filter_by(email=email).first() is not None:
        return jsonify({"error": "email already exists"}), 400

    user = User(
        username=username,
        email=email,
        phone=phone,
        register_source="web",
    )
    if gender is not None:
        user.gender = gender
    if age is not None:
        user.age = age
    if home_region is not None:
        user.home_region = home_region
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    return (
        jsonify(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
                "gender": user.gender,
                "age": user.age,
                "home_region": user.home_region,
                "created_at": user.created_at.isoformat()
                if user.created_at
                else None,
            }
        ),
        201,
    )


@auth_bp.post("/login")
def login():
    """用户登录接口。

    请求 JSON 示例：
    {
      "username": "zhangsan",
      "password": "123456"
    }

    当前仅做账号密码校验并返回用户信息，
    后续可在此基础上增加 token / 会话管理。
    """

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return (
            jsonify({"error": "username and password are required"}),
            400,
        )

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return jsonify({"error": "invalid username or password"}), 400

    return jsonify(
        {
            "message": "login_success",
            "token": generate_token(user.id),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
            },
        }
    )
