"""清理非内蒙古数据：按需求文件《3》第七条，系统仅面向内蒙古自治区。

删除 scenic_spot / hotel / food_place 中明显属于内蒙古以外的城市记录
（当前主要为早期 seed 引入的北京示例数据）。幂等：可重复执行。

运行：
    cd backend
    python -m scripts.cleanup_non_im_data
"""

from __future__ import annotations

from app import create_app
from app.db import db
from app.models import FoodPlace, Hotel, ScenicSpot

# 内蒙古 12 盟市关键词（含/不含“市/盟”后缀均可匹配）
IM_KEYWORDS = [
    "呼和浩特", "包头", "鄂尔多斯", "赤峰", "通辽", "呼伦贝尔",
    "乌兰察布", "乌海", "兴安", "锡林郭勒", "巴彦淖尔", "阿拉善",
]


def _is_inner_mongolia(city: str | None) -> bool:
    if not city:
        return False
    return any(k in city for k in IM_KEYWORDS)


def cleanup() -> None:
    app = create_app()
    with app.app_context():
        removed = {}
        for label, model in [("scenic", ScenicSpot), ("hotel", Hotel), ("food", FoodPlace)]:
            rows = model.query.all()
            to_delete = [r for r in rows if not _is_inner_mongolia(r.city)]
            for r in to_delete:
                db.session.delete(r)
            removed[label] = (len(to_delete), [f"{r.name}({r.city})" for r in to_delete][:10])
        db.session.commit()
        for label, (count, sample) in removed.items():
            print(f"{label}: removed {count} non-IM rows; sample={sample}")


if __name__ == "__main__":
    cleanup()
