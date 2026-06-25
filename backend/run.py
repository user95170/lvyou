import os

from app import create_app


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default

app = create_app()

if __name__ == "__main__":
    # 开发调试请显式设置 FLASK_DEBUG=1；公网部署请使用生产 WSGI/ASGI 服务器。
    app.run(
        host=os.getenv("FLASK_RUN_HOST", "127.0.0.1"),
        port=_env_int("PORT", 5000),
        debug=_env_flag("FLASK_DEBUG", False),
    )
