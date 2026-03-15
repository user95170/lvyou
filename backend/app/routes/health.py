from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.get("/health")
def health_check():
    """健康检查接口，用于快速验证后端是否可用。"""

    return jsonify({"status": "ok"})
