from flask import Blueprint, jsonify, request

from ..models import FoodPlace

food_bp = Blueprint("food", __name__, url_prefix="/api/foods")


@food_bp.get("")
def list_food_places():
    """美食列表接口。

    支持参数：
      - page: 页码，从 1 开始，默认 1
      - page_size: 每页条数，默认 10，上限 50
      - city: 按城市精确过滤
      - cuisine_type: 菜系类型过滤
      - min_price, max_price: 人均价格区间
      - keyword: 模糊搜索（name / tags）
    """

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    try:
        page_size = int(request.args.get("page_size", 10))
    except ValueError:
        page_size = 10

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10
    if page_size > 50:
        page_size = 50

    query = FoodPlace.query

    city = request.args.get("city")
    if city:
        query = query.filter(FoodPlace.city.like(f"%{city}%"))

    cuisine_type = request.args.get("cuisine_type")
    if cuisine_type:
        query = query.filter(FoodPlace.cuisine_type == cuisine_type)

    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    if min_price:
        try:
            query = query.filter(FoodPlace.avg_price >= float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            query = query.filter(FoodPlace.avg_price <= float(max_price))
        except ValueError:
            pass

    keyword = request.args.get("keyword")
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            (FoodPlace.name.like(like_pattern))
            | (FoodPlace.tags.like(like_pattern))
        )

    query = query.order_by(
        FoodPlace.rating_avg.desc(),
        FoodPlace.rating_count.desc(),
        FoodPlace.id.desc(),
    )

    total = query.count()
    items = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return jsonify(
        {
            "items": [food.to_dict() for food in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }
    )
