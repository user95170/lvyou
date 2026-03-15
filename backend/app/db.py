from flask_sqlalchemy import SQLAlchemy

# 全局单例的 SQLAlchemy 实例

db = SQLAlchemy()


def init_db(app) -> None:
    """在传入的 app 上初始化数据库扩展。"""

    db.init_app(app)
