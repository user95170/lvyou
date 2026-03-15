from flask import Flask

from .health import health_bp
from .scenic import scenic_bp
from .hotel import hotel_bp
from .food import food_bp
from .auth import auth_bp
from .behavior import behavior_bp
from .rating import rating_bp
from .recommend import recommend_bp
from .profile import profile_bp
from .route import route_bp
from .nlu import nlu_bp
from .map_api import map_bp
from .itinerary import itinerary_bp
from .agent import agent_bp


def register_routes(app: Flask) -> None:
    """集中注册所有蓝图/路由。"""

    app.register_blueprint(health_bp)
    app.register_blueprint(scenic_bp)
    app.register_blueprint(hotel_bp)
    app.register_blueprint(food_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(behavior_bp)
    app.register_blueprint(rating_bp)
    app.register_blueprint(recommend_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(route_bp)
    app.register_blueprint(nlu_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(itinerary_bp)
    app.register_blueprint(agent_bp)
