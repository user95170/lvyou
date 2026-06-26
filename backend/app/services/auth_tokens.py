"""登录令牌（无状态签名）与渐进式鉴权工具。

设计目标：在不破坏现有流程的前提下增加安全性。
- 登录成功后签发一个带时效的签名令牌（不落库，基于 SECRET_KEY 签名）。
- 写操作可调用 enforce_user(user_id) 进行"按需鉴权"：
  - 请求未携带 Authorization 头 → 视为遗留调用，放行（返回 None）；
  - 携带且无效/过期 → 返回 401；
  - 携带且有效但与目标 user_id 不一致 → 返回 403（防止冒用他人身份）；
  - 携带且有效且一致 → 放行（返回 None）。

这样：旧客户端/测试（不带令牌）行为不变；新前端带令牌后即获得身份一致性校验。
"""

from __future__ import annotations

from typing import Optional, Tuple

from flask import current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

_SALT = "auth-token-v1"


def _serializer() -> URLSafeTimedSerializer:
    secret = current_app.config.get("SECRET_KEY") or "dev-secret-change-me"
    return URLSafeTimedSerializer(secret_key=secret, salt=_SALT)


def generate_token(user_id: int) -> str:
    """为指定用户签发登录令牌。"""
    return _serializer().dumps({"uid": int(user_id)})


def verify_token(token: str) -> Optional[int]:
    """校验令牌，返回 user_id；无效或过期返回 None。"""
    if not token:
        return None
    max_age = int(current_app.config.get("AUTH_TOKEN_MAX_AGE", 7 * 24 * 3600))
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired, Exception):
        return None
    try:
        return int(data.get("uid"))
    except (TypeError, ValueError, AttributeError):
        return None


def _bearer_token() -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return header.strip() or None


def get_authenticated_user_id() -> Tuple[Optional[int], bool]:
    """返回 (authed_uid, token_present)。

    - token_present=False：请求未带令牌（遗留模式）。
    - token_present=True 且 authed_uid=None：令牌无效/过期。
    """
    token = _bearer_token()
    if not token:
        return None, False
    return verify_token(token), True


def enforce_user(user_id: Optional[int]):
    """按需鉴权。返回错误响应（需 return），或 None 表示放行。"""
    authed_uid, token_present = get_authenticated_user_id()
    if not token_present:
        return None  # 遗留模式：不强制
    if authed_uid is None:
        return jsonify({"error": "invalid or expired token"}), 401
    if user_id is not None and int(user_id) != int(authed_uid):
        return jsonify({"error": "forbidden: token does not match user_id"}), 403
    return None
