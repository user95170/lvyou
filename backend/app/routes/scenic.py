from flask import Blueprint, jsonify, request

from ..models import ScenicSpot

scenic_bp = Blueprint("scenic", __name__, url_prefix="/api/scenic-spots")


@scenic_bp.get("")
def list_scenic_spots():
    """景点列表接口。

    支持参数：
      - page: 页码，从 1 开始，默认 1
      - page_size: 每页条数，默认 10，上限 50
      - city: 按城市精确过滤
      - type: 按景点类型精确过滤（对应 scenic_spot.type 列）
      - keyword: 模糊搜索（name / tags）
    """

    # 分页参数
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

    query = ScenicSpot.query

    # 过滤条件
    city = request.args.get("city")
    if city:
        query = query.filter(ScenicSpot.city.like(f"%{city}%"))

    spot_type = request.args.get("type")
    if spot_type:
        query = query.filter(ScenicSpot.category == spot_type)

    keyword = request.args.get("keyword")
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.filter(
            (ScenicSpot.name.like(like_pattern))
            | (ScenicSpot.tags.like(like_pattern))
        )

    # 排序：优先评分高、评分人数多，其次按 id 倒序
    # 注意：MySQL 不支持 NULLS LAST 语法，这里使用普通的 desc 排序
    query = query.order_by(
        ScenicSpot.rating_avg.desc(),
        ScenicSpot.rating_count.desc(),
        ScenicSpot.id.desc(),
    )

    total = query.count()
    items = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return jsonify(
        {
            "items": [spot.to_dict() for spot in items],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }
    )
