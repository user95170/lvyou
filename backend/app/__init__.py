from flask import Flask

from .config import Config
from .db import init_db
from .routes import register_routes


def create_app() -> Flask:
    """应用工厂，用于创建并配置 Flask 实例。"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # 初始化数据库等扩展
    init_db(app)

    # 注册路由/蓝图
    register_routes(app)

    return app
