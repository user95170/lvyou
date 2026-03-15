import os


class Config:
    """基础配置。

    优先从环境变量 DATABASE_URL 读取数据库连接串；
    如未设置，则使用本地 MySQL + tourism_imu 作为默认值。
    使用前请将其中的密码改为你实际的 root 或其他账号密码。
    """

    # 示例：mysql+pymysql://用户名:密码@主机:端口/数据库?charset=utf8mb4
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///E:/旅游/dev.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 高德地图 Web 服务 API key，通过环境变量 AMAP_WEB_KEY 传入。
    # 未配置时，行程规划将仅使用基于经纬度的近似距离，不调用外部服务。
    AMAP_WEB_KEY = os.getenv("AMAP_WEB_KEY")

    # 路线规划 API 版本：v3 | v5（默认 v3）。
    AMAP_API_VERSION = os.getenv("AMAP_API_VERSION", "v3")

    # AMap GET JSON 内存缓存 TTL（秒）与简易 QPS 限制（每进程）。
    AMAP_CACHE_TTL = float(os.getenv("AMAP_CACHE_TTL", "60"))
    AMAP_QPS_LIMIT = int(os.getenv("AMAP_QPS_LIMIT", "8"))

    LLM_API_KEY = os.getenv("LLM_API_KEY")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

    LLM_TIMEOUT_SECONDS = os.getenv("LLM_TIMEOUT_SECONDS")

    AGENT_MAX_INPUT_CHARS = os.getenv("AGENT_MAX_INPUT_CHARS")
    AGENT_MAX_TURNS = os.getenv("AGENT_MAX_TURNS")

    # 其他后续配置可以继续在此类中补充
