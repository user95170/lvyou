"""交通/活动/特产等简单资源的个性化排序与匹配理由工具。

在用户提供人口特征（性别/年龄/地域）时，对候选资源做温和的重排，
并生成可读的匹配理由；无特征时退回按评分的默认顺序。
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Tuple


def base_score(obj: Any) -> float:
    """基于评分与评分数的基础分。"""
    base = 0.0
    rating_avg = getattr(obj, "rating_avg", None)
    if rating_avg is not None:
        try:
            base += float(rating_avg) / 5.0
        except (TypeError, ValueError):
            pass
    try:
        rc = int(getattr(obj, "rating_count", 0) or 0)
    except (TypeError, ValueError):
        rc = 0
    if rc >= 200:
        base += 0.1
    elif rc >= 50:
        base += 0.05
    return base


def build_reasons(
    obj: Any,
    demo: Optional[dict],
    adjust_fn: Optional[Callable[[Any, dict], Tuple[float, List[str]]]],
) -> List[str]:
    reasons: List[str] = []
    rating_avg = getattr(obj, "rating_avg", None)
    try:
        if rating_avg is not None and float(rating_avg) >= 4.5 and int(getattr(obj, "rating_count", 0) or 0) >= 50:
            reasons.append("本站评分较高")
    except (TypeError, ValueError):
        pass
    if demo and adjust_fn is not None:
        _, demo_reasons = adjust_fn(obj, demo)
        for r in demo_reasons:
            if r not in reasons:
                reasons.append(r)
    return reasons


def paginate_personalized(
    query: Any,
    page: int,
    page_size: int,
    demo: Optional[dict],
    adjust_fn: Optional[Callable[[Any, dict], Tuple[float, List[str]]]],
) -> Tuple[List[Any], int]:
    """返回 (当前页条目, 总数)。

    当 demo 非空时，在候选池内按 base+人口特征加权重排再分页；
    否则沿用数据库的默认排序与分页。
    """
    total = query.count()
    if demo and adjust_fn is not None:
        pool_limit = min(200, max(page_size * 5, page_size))
        pool = query.limit(pool_limit).all()

        def sort_key(obj: Any):
            score = base_score(obj) + adjust_fn(obj, demo)[0]
            try:
                rc = int(getattr(obj, "rating_count", 0) or 0)
            except (TypeError, ValueError):
                rc = 0
            return (-score, -rc, -(obj.id or 0))

        pool.sort(key=sort_key)
        start = (page - 1) * page_size
        items = pool[start : start + page_size]
    else:
        items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total
