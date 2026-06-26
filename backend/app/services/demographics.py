"""人口特征（性别/年龄/地域）驱动的个性化评分与匹配理由。

本模块为推荐侧提供可复用、可测试的"用户原始特征 → 资源匹配加权 + 匹配理由"逻辑，
对应需求文件《3》中关于性别、年龄、地域以及交叉特征的细粒度个性化要求。

设计原则：
- 加权幅度保持温和（多在 0.04–0.18 之间），用于在同等评分/热度下做个性化"微调"，
  不会盖过基础口碑与多源得分。
- 同时返回人类可读的匹配理由，便于前端在推荐卡片上解释"为何推荐给你"。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

VALID_GENDERS = {"unknown", "male", "female"}

# 地域 → 口味/菜系标签映射，用于美食个性化与"家乡口味"提示。
# 每一项：(地域关键词列表, 口味/菜系标签列表, 提示文案)
REGION_TASTE_MAP: List[Tuple[List[str], List[str], str]] = [
    (["湖南", "湘"], ["辣", "辣味", "香辣", "湘菜", "剁椒"], "符合您的家乡口味（偏辣）"),
    (["四川", "重庆", "川", "渝"], ["辣", "麻辣", "川菜", "火锅", "水煮"], "符合您的家乡口味（偏麻辣）"),
    (["广东", "广州", "深圳", "粤"], ["清淡", "粤菜", "早茶", "海鲜", "煲汤"], "符合您的家乡口味（清淡粤式）"),
    (["江苏", "浙江", "上海", "苏", "沪", "杭"], ["清淡", "本帮", "江浙", "甜", "蟹"], "符合您的家乡口味（清淡江浙）"),
    (["山东", "鲁"], ["鲁菜", "面食", "海鲜", "葱"], "符合您的家乡口味（鲁式）"),
    (["陕西", "山西", "西安", "晋", "陕"], ["面食", "面", "馍", "醋", "凉皮"], "符合您的家乡口味（面食）"),
    (["内蒙古", "内蒙", "蒙"], ["蒙餐", "牛羊肉", "手把肉", "奶茶", "莜面", "烧烤"], "符合您的家乡口味（蒙式）"),
    (["东北", "辽宁", "吉林", "黑龙江", "辽", "吉", "黑"], ["东北菜", "炖", "锅包肉", "烧烤"], "符合您的家乡口味（东北风味）"),
    (["新疆", "疆"], ["新疆菜", "羊肉", "拌面", "烤串", "馕"], "符合您的家乡口味（西北风味）"),
    (["广西", "桂"], ["米粉", "螺蛳粉", "酸", "桂菜"], "符合您的家乡口味（桂式）"),
    (["云南", "贵州", "滇", "黔"], ["酸辣", "米线", "菌", "酸汤"], "符合您的家乡口味（云贵风味）"),
]

INNER_MONGOLIA_KEYWORDS = ["内蒙古", "内蒙", "蒙"]
LOCAL_FOOD_TAGS = ["蒙餐", "牛羊肉", "手把肉", "烤全羊", "奶茶", "莜面", "蒙古", "羊"]

# 景点标签词典
_QUIET = ["博物馆", "公园", "寺", "庙", "古迹", "文化", "湿地", "湖", "草原", "故居", "陵"]
_LIVELY = ["娱乐", "夜", "酒吧", "购物", "网红", "乐园", "演出", "商圈"]
_PHOTO = ["网红", "打卡", "花", "草原", "湖", "日落", "摄影", "古镇"]
_OUTDOOR = ["户外", "探险", "徒步", "登山", "沙漠", "滑雪", "骑行", "草原", "森林"]

# 美食标签词典
_SPICY = ["辣", "麻辣", "香辣", "重口", "剁椒"]
_LIGHT = ["清淡", "养生", "粥", "汤", "蒸", "煲"]
_NIGHT = ["烧烤", "夜宵", "小吃", "网红", "串"]
_FEMALE_FOOD = ["甜", "网红", "下午茶", "氛围", "甜品", "咖啡"]

# 活动标签词典
_ACT_SENIOR = ["中老年", "文化", "安静", "休闲", "展览", "民俗"]
_ACT_YOUNG = ["年轻人", "夜", "音乐", "户外", "冰雪", "演出", "赛事", "娱乐"]
_ACT_FAMILY = ["亲子", "家庭"]
_ACT_NOISY = ["夜", "音乐", "赛事", "娱乐"]

# 交通标签词典
_TRANS_CONVENIENT = ["接驳", "直达", "便捷", "枢纽", "地铁", "换乘"]

# 特产标签词典
_SPEC_GIFT = ["伴手礼", "必买", "地道", "特色"]
_SPEC_FEMALE = ["手工艺", "银器", "饰品", "礼品"]


def parse_demographics_payload(
    data: Dict[str, Any]
) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[str]]:
    """解析请求体中的可选人口特征字段。

    返回 (gender, age, home_region, error)：
      - 三个值为 None 表示"未提供该字段"（调用方据此决定是否更新）；
      - error 非 None 表示校验失败，调用方应返回 400。
    """

    gender: Optional[str] = None
    age: Optional[int] = None
    home_region: Optional[str] = None

    if "gender" in data and data.get("gender") not in (None, ""):
        g = str(data.get("gender")).strip().lower()
        if g not in VALID_GENDERS:
            return None, None, None, "gender must be one of unknown/male/female"
        gender = g

    if "age" in data and data.get("age") not in (None, ""):
        try:
            age_val = int(data.get("age"))
        except (TypeError, ValueError):
            return None, None, None, "age must be an integer"
        if age_val < 1 or age_val > 120:
            return None, None, None, "age must be between 1 and 120"
        age = age_val

    if "home_region" in data and data.get("home_region") not in (None, ""):
        region = str(data.get("home_region")).strip()
        if len(region) > 100:
            return None, None, None, "home_region too long"
        home_region = region or None

    return gender, age, home_region, None


def age_group(age: Optional[int]) -> str:
    """将年龄映射为人群分组。"""
    if age is None:
        return "unknown"
    try:
        value = int(age)
    except (TypeError, ValueError):
        return "unknown"
    if value < 18:
        return "teen"
    if value < 30:
        return "young"
    if value < 50:
        return "adult"
    return "senior"


def load_user_demographics(uid: Optional[int]) -> Dict[str, Any]:
    """从 User 读取性别/年龄/地域，返回结构化人口画像（不含偏好类型）。"""
    out: Dict[str, Any] = {
        "gender": None,
        "age": None,
        "home_region": None,
        "age_group": "unknown",
    }
    if not uid:
        return out
    from ..models import User  # 局部导入避免循环依赖

    user = User.query.filter_by(id=uid).first()
    if user is None:
        return out
    out["gender"] = (user.gender or "unknown").lower()
    try:
        out["age"] = int(user.age) if user.age is not None else None
    except (TypeError, ValueError):
        out["age"] = None
    out["home_region"] = (user.home_region or "").strip() or None
    out["age_group"] = age_group(out["age"])
    return out


def has_demographics(demo: Optional[Dict[str, Any]]) -> bool:
    if not demo:
        return False
    if demo.get("home_region"):
        return True
    if demo.get("age") is not None:
        return True
    gender = (demo.get("gender") or "unknown").lower()
    return gender in ("male", "female")


def _contains_any(text: Optional[str], keywords: List[str]) -> bool:
    if not text:
        return False
    return any(k and k in text for k in keywords)


def _dedup(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def region_taste_tags(home_region: Optional[str]) -> Tuple[List[str], Optional[str]]:
    """根据地域返回 (口味/菜系标签列表, 家乡口味提示文案)。无匹配返回 ([], None)。"""
    if not home_region:
        return [], None
    for keywords, tastes, reason in REGION_TASTE_MAP:
        if _contains_any(home_region, keywords):
            return tastes, reason
    return [], None


def scenic_demographic_adjustment(spot: Any, demo: Optional[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """计算景点的人口特征加权与匹配理由。返回 (得分增量, 理由列表)。"""
    delta = 0.0
    reasons: List[str] = []
    if not demo:
        return delta, reasons

    category = getattr(spot, "category", None) or ""
    tags = getattr(spot, "tags", None) or ""
    text = f"{category} {tags}"

    ag = demo.get("age_group") or "unknown"
    gender = (demo.get("gender") or "unknown").lower()
    senior = ag == "senior"
    young = ag in ("teen", "young")
    female = gender == "female"
    male = gender == "male"

    if senior and _contains_any(text, _QUIET):
        delta += 0.08
        reasons.append("适合偏安静、舒适的行程节奏")
    if senior and _contains_any(text, _LIVELY):
        delta -= 0.08
    if young and _contains_any(text, _LIVELY + _OUTDOOR):
        delta += 0.06
        reasons.append("适合年轻人的活力玩法")

    if female and _contains_any(text, _PHOTO):
        delta += 0.05
        reasons.append("适合拍照打卡")
    if male and _contains_any(text, _OUTDOOR):
        delta += 0.04

    # 交叉特征：年长女性 → 安静、文化、人少
    if senior and female and _contains_any(text, _QUIET):
        delta += 0.05
        reasons.append("为偏好安静舒适的您优选")
    # 交叉特征：年轻男性 → 户外、探险
    if young and male and _contains_any(text, _OUTDOOR):
        delta += 0.04

    return delta, _dedup(reasons)


def food_demographic_adjustment(food: Any, demo: Optional[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """计算美食的人口特征加权与匹配理由。返回 (得分增量, 理由列表)。"""
    delta = 0.0
    reasons: List[str] = []
    if not demo:
        return delta, reasons

    cuisine = getattr(food, "cuisine_type", None) or ""
    tags = getattr(food, "tags", None) or ""
    text = f"{cuisine} {tags}"

    ag = demo.get("age_group") or "unknown"
    gender = (demo.get("gender") or "unknown").lower()
    home_region = demo.get("home_region")
    senior = ag == "senior"
    young = ag in ("teen", "young")
    female = gender == "female"

    # 家乡口味（地域 → 口味/菜系）
    tastes, taste_reason = region_taste_tags(home_region)
    if tastes and _contains_any(text, tastes):
        delta += 0.18
        if taste_reason:
            reasons.append(taste_reason)

    # 外地游客 → 内蒙古地道风味（用户非内蒙古籍时）
    if home_region and not _contains_any(home_region, INNER_MONGOLIA_KEYWORDS):
        if _contains_any(text, LOCAL_FOOD_TAGS):
            delta += 0.06
            reasons.append("内蒙古地道风味，值得一试")

    # 年龄
    if senior:
        if _contains_any(text, _LIGHT):
            delta += 0.05
            reasons.append("口味清淡，适合舒缓的用餐节奏")
        if _contains_any(text, _SPICY):
            delta -= 0.04
    if young and _contains_any(text, _NIGHT):
        delta += 0.05
        reasons.append("年轻人喜爱的热门小吃")

    # 性别
    if female and _contains_any(text, _FEMALE_FOOD):
        delta += 0.04
        reasons.append("氛围感餐厅，适合拍照")

    return delta, _dedup(reasons)


def activity_demographic_adjustment(activity: Any, demo: Optional[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """活动的人口特征加权与匹配理由（适配人群差异）。"""
    delta = 0.0
    reasons: List[str] = []
    if not demo:
        return delta, reasons

    text = " ".join(
        str(getattr(activity, f, "") or "")
        for f in ("activity_type", "tags", "description")
    )
    ag = demo.get("age_group") or "unknown"
    senior = ag == "senior"
    young = ag in ("teen", "young")

    if senior and _contains_any(text, _ACT_SENIOR):
        delta += 0.08
        reasons.append("适合中老年的文化休闲活动")
    if senior and _contains_any(text, _ACT_NOISY):
        delta -= 0.06
    if young and _contains_any(text, _ACT_YOUNG):
        delta += 0.07
        reasons.append("适合年轻人的活力活动")
    if _contains_any(text, _ACT_FAMILY):
        delta += 0.04
        reasons.append("适合亲子家庭参与")

    return delta, _dedup(reasons)


def transportation_demographic_adjustment(item: Any, demo: Optional[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """交通节点的人口特征加权（为中老年突出便捷/少换乘）。"""
    delta = 0.0
    reasons: List[str] = []
    if not demo:
        return delta, reasons

    text = " ".join(
        str(getattr(item, f, "") or "")
        for f in ("transport_type", "tags", "description")
    )
    senior = (demo.get("age_group") or "unknown") == "senior"
    if senior and _contains_any(text, _TRANS_CONVENIENT):
        delta += 0.06
        reasons.append("出行便捷，适合长辈（少换乘）")

    return delta, _dedup(reasons)


def specialty_demographic_adjustment(item: Any, demo: Optional[Dict[str, Any]]) -> Tuple[float, List[str]]:
    """特产的人口特征加权（地域关联：家乡口味 / 外地必买）。"""
    delta = 0.0
    reasons: List[str] = []
    if not demo:
        return delta, reasons

    text = " ".join(
        str(getattr(item, f, "") or "")
        for f in ("category", "tags", "name", "description")
    )
    home_region = demo.get("home_region")
    gender = (demo.get("gender") or "unknown").lower()

    # 外地游客 → 内蒙古特色伴手礼
    if home_region and not _contains_any(home_region, INNER_MONGOLIA_KEYWORDS):
        if _contains_any(text, _SPEC_GIFT):
            delta += 0.06
            reasons.append("内蒙古特色伴手礼，适合带回")

    # 家乡口味（地域 → 口味/菜系）应用到食品类特产
    tastes, taste_reason = region_taste_tags(home_region)
    if tastes and _contains_any(text, tastes):
        delta += 0.08
        if taste_reason:
            reasons.append(taste_reason)

    if gender == "female" and _contains_any(text, _SPEC_FEMALE):
        delta += 0.04
        reasons.append("精美手工艺，适合馈赠")

    return delta, _dedup(reasons)
