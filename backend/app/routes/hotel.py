from flask import Blueprint, jsonify, request

from ..models import Hotel

hotel_bp = Blueprint("hotel", __name__, url_prefix="/api/hotels")


@hotel_bp.get("")
def list_hotels():
    """酒店列表接口。

    支持参数：
      - page: 页码，从 1 开始，默认 1
      - page_size: 每页条数，默认 10，上限 50
      - city: 按城市精确过滤
      - star_level: 星级过滤（如 经济型/舒适型/豪华型 或 3星/4星）
      - min_price, max_price: 价格区间过滤（元/晚）
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

    query = Hotel.query

    city = request.args.get("city")
    if city:
        query = query.filter(Hotel.city == city)

    star_level = request.args.get("star_level")
    if star_level:
        query = query.filter(Hotel.star_level == star_level)

    # 价格区间
    min_price = request.args.get("min_price")
    max_price = request.args.get("max_price")
    if min_price:
        try:
            query = query.filter(Hotel.avg_price >= float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            query = query.filter(Hotel.avg_price <= float(max_price))
        except ValueError:
            pass

    keyword = request.args.get("keyword")
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            (Hotel.name.like(like_pattern))
            | (Hotel.tags.like(like_pattern))
        )

    # 排序：评分高、评分人数多、id 倒序
    query = query.order_by(
        Hotel.rating_avg.desc(),
        Hotel.rating_count.desc(),
        Hotel.id.desc(),
    )

    total = query.count()
    items = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return jsonify(
        {
            "items": [hotel.to_dict() for hotel in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }
    )
