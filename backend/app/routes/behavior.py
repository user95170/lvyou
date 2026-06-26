from flask import Blueprint, jsonify, request

from ..db import db
from ..models import UserBehaviorLog
from ..services.auth_tokens import enforce_user

behavior_bp = Blueprint("behavior", __name__, url_prefix="/api/behaviors")


@behavior_bp.post("")
def create_behavior():
    """记录用户行为日志。

    请求 JSON 示例：
    {
      "user_id": 1,                    # 可选，未登录可为空
      "target_type": "scenic_spot",  # 必填，目标类型
      "target_id": 3,                 # 必填，目标 ID
      "behavior_type": "view",      # 必填，行为类型，如 view/click/favorite
      "behavior_value": 1,            # 可选，数值型，如停留时长等
      "device": "web",              # 可选
      "ip": "127.0.0.1"             # 可选，不填则使用请求来源 IP
    }
    """

    data = request.get_json(silent=True) or {}

    user_id = data.get("user_id")
    target_type = (data.get("target_type") or "").strip()
    target_id = data.get("target_id")
    behavior_type = (data.get("behavior_type") or "").strip()
    behavior_value = data.get("behavior_value")
    device = (data.get("device") or None) or None
    ip = (data.get("ip") or None) or request.remote_addr

    if not target_type or target_id is None or not behavior_type:
        return jsonify({"error": "target_type, target_id and behavior_type are required"}), 400

    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        return jsonify({"error": "target_id must be an integer"}), 400

    # 仅当请求声明了 user_id 时才做身份一致性校验（匿名行为放行）
    if user_id is not None:
        auth_error = enforce_user(user_id)
        if auth_error is not None:
            return auth_error

    log = UserBehaviorLog(
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        behavior_type=behavior_type,
        behavior_value=behavior_value,
        device=device,
        ip=ip,
    )

    db.session.add(log)
    db.session.commit()

    return jsonify(log.to_dict()), 201
