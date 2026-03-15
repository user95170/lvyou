from flask import Blueprint, jsonify, request
import re

nlu_bp = Blueprint("nlu", __name__, url_prefix="/api/nlu")


@nlu_bp.post("/parse")
def parse_nlu():
    data = request.get_json(silent=True) or {}
    text = str(data.get("text") or "").strip()

    intent = "plan_trip" if text else "unknown"
    slots = {}

    if text:
        m = re.search(r"(\d+)\s*天", text)
        if m:
            try:
                slots["days"] = int(m.group(1))
            except Exception:
                pass

        # 预算：提取金额并映射到档位（1=节省，2=适中，3=高档）
        m = re.search(r"预算\s*([0-9]+)", text)
        if m:
            try:
                amount = int(m.group(1))
                slots["budget_amount"] = amount
                if amount <= 1500:
                    slots["budget_level"] = 1
                elif amount <= 4000:
                    slots["budget_level"] = 2
                else:
                    slots["budget_level"] = 3
            except Exception:
                pass

        # 文字描述预算档位
        if any(k in text for k in ["省钱", "节省", "经济", "便宜"]):
            slots["budget_level"] = 1
        if any(k in text for k in ["适中", "一般", "中等"]):
            slots["budget_level"] = 2
        if any(k in text for k in ["高档", "高端", "豪华"]):
            slots["budget_level"] = 3

        if "自驾" in text:
            slots["transport_mode"] = "drive"
        elif ("公交" in text) or ("地铁" in text):
            slots["transport_mode"] = "transit"
        elif "步行" in text:
            slots["transport_mode"] = "walk"

        m = re.search(r"去([\u4e00-\u9fa5]{1,12})", text)
        if m:
            slots["destination"] = m.group(1)

        interests = []
        for kw in [
            "人文历史",
            "人文",
            "美食",
            "自然",
            "草原",
            "沙漠",
            "湖泊",
            "博物馆",
        ]:
            if kw in text:
                interests.append(kw)
        if interests:
            slots["interests"] = interests

        # 简单旅行风格推断
        if any(k in text for k in ["亲子", "家庭"]):
            slots["travel_style"] = "family"
        elif any(k in text for k in ["摄影", "打卡"]):
            slots["travel_style"] = "photography"
        elif any(k in text for k in ["探险", "越野", "徒步"]):
            slots["travel_style"] = "adventure"
        elif any(k in text for k in ["人文", "博物馆"]):
            slots["travel_style"] = "culture"
        elif any(k in text for k in ["放松", "休闲", "度假"]):
            slots["travel_style"] = "relax"

    return jsonify({"intent": intent, "slots": slots})
