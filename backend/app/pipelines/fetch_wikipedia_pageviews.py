from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from urllib.request import urlopen, Request

from .. import create_app
from ..db import db
from ..models import ContentStandard, ScenicSpot, Hotel, FoodPlace


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _http_json(url: str, headers: Optional[dict] = None) -> dict:
    req = Request(url, headers=headers or {"User-Agent": "imu-tourism/1.0"})
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def _search_article(lang: str, name: str, city: Optional[str], district: Optional[str], etype: str) -> Optional[str]:
    # Build candidate queries with fallbacks by entity type
    base = [name]
    geo = [t for t in [district, city] if t]
    candidates: list[str] = []
    # name + geo
    if geo:
        candidates.append(" ".join(base + geo))
    candidates.append(name)
    # type-specific suffix
    if etype == "hotel":
        if lang == "zh":
            candidates.extend([f"{name} 酒店", f"{name} 宾馆"])
        else:
            candidates.append(f"{name} hotel")
    elif etype == "food_place":
        if lang == "zh":
            candidates.extend([f"{name} 餐厅", f"{name} 饭店", f"{name} 美食"])
        else:
            candidates.append(f"{name} restaurant")

    for query in candidates:
        q = quote(query)
        # Try intitle first (more precise)
        url1 = (
            f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch=intitle:{q}"
            f"&srwhat=title&srnamespace=0&srlimit=1&format=json"
        )
        try:
            data = _http_json(url1)
            hits = (data.get("query") or {}).get("search") or []
            if hits:
                title = hits[0].get("title")
                if title:
                    return title.replace(" ", "_")
        except Exception:
            pass
        # Fallback to default search
        url2 = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&srnamespace=0&srlimit=1&format=json"
        try:
            data = _http_json(url2)
            hits = (data.get("query") or {}).get("search") or []
            if hits:
                title = hits[0].get("title")
                if title:
                    return title.replace(" ", "_")
        except Exception:
            continue
    return None


def _brand_alias_patterns(etype: str) -> list[tuple[str, str]]:
    if etype == "hotel":
        return [
            ("万豪", "Marriott"),
            ("Marriott", "Marriott"),
            ("希尔顿", "Hilton"),
            ("Hilton", "Hilton"),
            ("洲际", "InterContinental"),
            ("IHG", "InterContinental"),
            ("InterContinental", "InterContinental"),
            ("凯悦", "Hyatt"),
            ("Hyatt", "Hyatt"),
            ("香格里拉", "Shangri-La"),
            ("Shangri-La", "Shangri-La"),
            ("喜来登", "Sheraton"),
            ("Sheraton", "Sheraton"),
            ("雅高", "Accor"),
            ("Accor", "Accor"),
        ]
    if etype == "food_place":
        return [
            ("麦当劳", "McDonald's"),
            ("McDonald's", "McDonald's"),
            ("肯德基", "KFC"),
            ("KFC", "KFC"),
            ("Kentucky Fried Chicken", "KFC"),
            ("星巴克", "Starbucks"),
            ("Starbucks", "Starbucks"),
            ("必胜客", "Pizza Hut"),
            ("Pizza Hut", "Pizza Hut"),
            ("海底捞", "Haidilao"),
            ("Haidilao", "Haidilao"),
            ("德克士", "Dicos"),
            ("Dicos", "Dicos"),
            ("汉堡王", "Burger King"),
            ("Burger King", "Burger King"),
        ]
    return []


def _match_brand_label(etype: str, name: str, tags: str = "", src: str = "", addr: str = "") -> Optional[str]:
    hay = " ".join([str(name or ""), str(tags or ""), str(src or ""), str(addr or "")]).lower()
    for alias, label in _brand_alias_patterns(etype):
        if alias.lower() in hay:
            return label
    return None


def _resolve_brand_via_wikidata(brand_label: str, lang: str) -> Optional[tuple[str, str, str]]:
    lang_for_wd = "zh" if lang == "zh" else "en"
    qids = _wikidata_search(brand_label, lang=lang_for_wd, limit=3)
    for qid in qids:
        sitelink = _wikidata_get_sitelink_title(qid, lang_pref=lang)
        if sitelink and sitelink[1]:
            project, title = sitelink
            return project, title, qid
    return None


def _wikidata_is_instance_of(qid: str, allowed: set[str]) -> bool:
    """Return True if the item has P31 (instance of) in allowed QIDs."""
    url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&props=claims&format=json"
    try:
        data = _http_json(url)
    except Exception:
        return False
    ent = (data.get("entities") or {}).get(qid) or {}
    claims = ent.get("claims") or {}
    p31_list = claims.get("P31") or []
    for cl in p31_list:
        mainsnak = cl.get("mainsnak") or {}
        dv = (mainsnak.get("datavalue") or {}).get("value") or {}
        target_id = dv.get("id")
        if isinstance(target_id, str) and target_id in allowed:
            return True
    return False


def _sum_pageviews(project: str, article: str, start: str, end: str) -> int:
    a = quote(article, safe="")
    # try user agents first
    url1 = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/all-access/user/{a}/daily/{start}/{end}"
    s = 0
    try:
        data = _http_json(url1, headers={"User-Agent": "imu-tourism/1.0"})
        items = (data.get("items") or [])
        for it in items:
            try:
                s += int(it.get("views") or 0)
            except Exception:
                continue
    except Exception:
        s = 0
    # fallback to all-agents if user has no data
    if int(s) <= 0:
        url2 = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/all-access/all-agents/{a}/daily/{start}/{end}"
        try:
            data = _http_json(url2, headers={"User-Agent": "imu-tourism/1.0"})
            items = (data.get("items") or [])
            s = 0
            for it in items:
                try:
                    s += int(it.get("views") or 0)
                except Exception:
                    continue
        except Exception:
            return 0
    return int(s)


def _wikidata_search(query: str, lang: str = "zh", limit: int = 3) -> list[str]:
    q = quote(query)
    url = (
        f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={q}&language={lang}"
        f"&type=item&format=json&limit={int(limit)}"
    )
    try:
        data = _http_json(url)
    except Exception:
        return []
    res = []
    for it in data.get("search", []) or []:
        qid = it.get("id")
        if qid:
            res.append(str(qid))
    return res


def _wikidata_get_sitelink_title(qid: str, lang_pref: str = "zh") -> Optional[tuple[str, str]]:
    url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&props=sitelinks/urls&format=json"
    try:
        data = _http_json(url)
    except Exception:
        return None
    ent = (data.get("entities") or {}).get(qid) or {}
    sitelinks = ent.get("sitelinks") or {}
    # Prefer zh, then en
    if lang_pref == "zh" and sitelinks.get("zhwiki"):
        return ("zh.wikipedia.org", sitelinks["zhwiki"].get("title") or "")
    if sitelinks.get("enwiki"):
        return ("en.wikipedia.org", sitelinks["enwiki"].get("title") or "")
    if sitelinks.get("zhwiki"):
        return ("zh.wikipedia.org", sitelinks["zhwiki"].get("title") or "")
    return None


def _resolve_title_via_wikidata(lang: str, name: str, city: Optional[str], district: Optional[str], etype: str) -> Optional[tuple[str, str]]:
    base = [name]
    geo = [t for t in [district, city] if t]
    candidates: list[str] = []
    if geo:
        candidates.append(" ".join(base + geo))
        candidates.append(" ".join(geo + base))
    candidates.append(name)
    if etype == "hotel":
        if lang == "zh":
            candidates.extend([f"{name} 酒店", f"{name} 宾馆"])
        else:
            candidates.append(f"{name} hotel")
    elif etype == "food_place":
        if lang == "zh":
            candidates.extend([f"{name} 餐厅", f"{name} 饭店", f"{name} 美食"])
        else:
            candidates.append(f"{name} restaurant")

    lang_for_wd = "zh" if lang == "zh" else "en"
    allowed_map: dict[str, set[str]] = {
        "hotel": {"Q27686"},       # instance of: hotel
        "food_place": {"Q11707"},  # instance of: restaurant
    }
    for query in candidates:
        qids = _wikidata_search(query, lang=lang_for_wd, limit=3)
        for qid in qids:
            allowed = allowed_map.get(etype)
            if allowed and not _wikidata_is_instance_of(qid, allowed):
                continue
            # Geo filter: prefer China or matching city/district
            if not _wikidata_pass_geo_filter(qid, city or "", district or ""):
                continue
            res = _wikidata_get_sitelink_title(qid, lang_pref=lang)
            if res and res[1]:
                return res  # (project, title)
    return None


def _wikidata_get_claim_ids(qid: str, prop: str) -> list[str]:
    url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&props=claims&format=json"
    try:
        data = _http_json(url)
    except Exception:
        return []
    ent = (data.get("entities") or {}).get(qid) or {}
    claims = ent.get("claims") or {}
    lst = []
    for cl in claims.get(prop, []) or []:
        dv = ((cl.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {}
        tid = dv.get("id")
        if isinstance(tid, str):
            lst.append(tid)
    return lst


def _wikidata_get_labels(qids: list[str]) -> dict[str, dict[str, str]]:
    if not qids:
        return {}
    ids = "|".join(qids[:50])
    url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={ids}&props=labels&format=json"
    try:
        data = _http_json(url)
    except Exception:
        return {}
    ents = data.get("entities") or {}
    out: dict[str, dict[str, str]] = {}
    for k, v in ents.items():
        labels = (v or {}).get("labels") or {}
        out[k] = {
            "zh": ((labels.get("zh") or {}).get("value") or ""),
            "en": ((labels.get("en") or {}).get("value") or ""),
        }
    return out


def _norm(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "")


def _geo_match(city: str, district: str, labels: dict[str, dict[str, str]]) -> bool:
    c = _norm(city)
    d = _norm(district)
    if not c and not d:
        return False
    for lab in labels.values():
        zh = _norm(lab.get("zh", ""))
        en = _norm(lab.get("en", ""))
        if c and (c in zh or c in en or zh in c or en in c):
            return True
        if d and (d in zh or d in en or zh in d or en in d):
            return True
    return False


def _wikidata_pass_geo_filter(qid: str, city: str, district: str) -> bool:
    # Country filter: China Q148
    p17 = _wikidata_get_claim_ids(qid, "P17")
    if "Q148" in p17:  # China
        return True
    # P131 administrative entity labels match city/district
    p131 = _wikidata_get_claim_ids(qid, "P131")
    if not p131:
        return False
    labels = _wikidata_get_labels(p131)
    return _geo_match(city, district, labels)


def _upsert_interaction(
    entity_type: str,
    entity_id: int,
    interaction_sum: int,
    *,
    brand_based: bool = False,
    brand_label: Optional[str] = None,
    brand_qid: Optional[str] = None,
    source_project: Optional[str] = None,
    source_title: Optional[str] = None,
) -> None:
    if interaction_sum <= 0:
        return
    row = ContentStandard.query.filter_by(
        entity_type=entity_type, entity_id=entity_id, source_type="social_media"
    ).first()
    if row is None:
        row = ContentStandard(entity_type=entity_type, entity_id=entity_id, source_type="social_media")
        db.session.add(row)
    payload = {"interaction_sum": int(interaction_sum)}
    if brand_based:
        payload["brand_based"] = True
        if brand_label:
            payload["brand_label"] = brand_label
        if brand_qid:
            payload["brand_qid"] = brand_qid
    if source_project:
        payload["project"] = source_project
    if source_title:
        payload["article_title"] = source_title
    row.title = "social_media"
    row.summary = json.dumps(payload, ensure_ascii=False)
    row.last_update = _utcnow()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Wikipedia pageviews and write to ContentStandard")
    parser.add_argument("--lang", type=str, default="zh")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=0.1)
    parser.add_argument("--fallback-en", action="store_true", help="If zh search fails, try en.wikipedia.org")
    parser.add_argument(
        "--entity",
        type=str,
        default="scenic_spot",
        choices=["scenic_spot", "hotel", "food_place", "all"],
        help="Target entity type to import pageviews for",
    )
    args = parser.parse_args()

    today = _utcnow().date()
    # Wikimedia pageviews are available for complete days only; end at yesterday (UTC)
    end_dt = today - timedelta(days=1)
    start_dt = end_dt - timedelta(days=max(1, args.days) - 1)
    start = start_dt.strftime("%Y%m%d")
    end = end_dt.strftime("%Y%m%d")
    project = f"{args.lang}.wikipedia.org"

    app = create_app()
    with app.app_context():
        entities: list[tuple[str, int, str, str, str, str, str, str]] = []  # (etype, id, name, city, district, tags, source, address)
        types_to_run = [args.entity] if args.entity != "all" else ["scenic_spot", "hotel", "food_place"]

        for et in types_to_run:
            if et == "scenic_spot":
                q = (
                    ScenicSpot.query.with_entities(
                        ScenicSpot.id,
                        ScenicSpot.name,
                        ScenicSpot.city,
                        ScenicSpot.district,
                        ScenicSpot.tags,
                        ScenicSpot.rating_count,
                        ScenicSpot.address,
                    )
                    .order_by(ScenicSpot.rating_count.desc())
                    .limit(args.limit)
                    .all()
                )
                for i, n, c, d, tags, _rc, addr in q:
                    entities.append((et, int(i), str(n or ""), str(c or ""), str(d or ""), str(tags or ""), "", str(addr or "")))
            elif et == "hotel":
                q = (
                    Hotel.query.with_entities(
                        Hotel.id,
                        Hotel.name,
                        Hotel.city,
                        Hotel.district,
                        Hotel.tags,
                        Hotel.source,
                        Hotel.rating_count,
                        Hotel.address,
                    )
                    .order_by(Hotel.rating_count.desc())
                    .limit(args.limit)
                    .all()
                )
                for i, n, c, d, tags, src, _rc, addr in q:
                    entities.append((et, int(i), str(n or ""), str(c or ""), str(d or ""), str(tags or ""), str(src or ""), str(addr or "")))
            elif et == "food_place":
                q = (
                    FoodPlace.query.with_entities(
                        FoodPlace.id,
                        FoodPlace.name,
                        FoodPlace.city,
                        FoodPlace.district,
                        FoodPlace.tags,
                        FoodPlace.source,
                        FoodPlace.rating_count,
                        FoodPlace.address,
                    )
                    .order_by(FoodPlace.rating_count.desc())
                    .limit(args.limit)
                    .all()
                )
                for i, n, c, d, tags, src, _rc, addr in q:
                    entities.append((et, int(i), str(n or ""), str(c or ""), str(d or ""), str(tags or ""), str(src or ""), str(addr or "")))

        processed = 0
        dbg_hit_title_zh = 0
        dbg_hit_title_en = 0
        dbg_hit_wd = 0
        dbg_hit_brand = 0
        dbg_views_pos = 0
        for etype, eid, name, city, district, tags, src, addr in entities:
            title = _search_article(args.lang, name, city or None, district or None, etype)
            views = 0
            if title:
                views = _sum_pageviews(project, title, start, end)
                if views > 0:
                    dbg_hit_title_zh += 1
            if views <= 0:
                # try direct en wiki search if enabled
                if args.fallback_en:
                    en_title = _search_article("en", name, city or None, district or None, etype)
                    if en_title:
                        views = _sum_pageviews("en.wikipedia.org", en_title, start, end)
                        if views > 0:
                            dbg_hit_title_en += 1
            if views <= 0:
                # Wikidata fallback
                res = _resolve_title_via_wikidata(args.lang, name, city or None, district or None, etype)
                if res and res[1]:
                    pj, t = res
                    views = _sum_pageviews(pj, t, start, end)
                    if views > 0:
                        dbg_hit_wd += 1
            brand_used = False
            brand_label = None
            brand_qid = None
            brand_project = None
            brand_title = None
            if views <= 0 and etype in ("hotel", "food_place"):
                brand_label = _match_brand_label(etype, name, tags, src, addr)
                if brand_label:
                    bres = _resolve_brand_via_wikidata(brand_label, args.lang)
                    if bres:
                        brand_project, brand_title, brand_qid = bres
                        views = _sum_pageviews(brand_project, brand_title, start, end)
                        brand_used = views > 0
                        if brand_used:
                            dbg_hit_brand += 1
            if views <= 0:
                time.sleep(args.sleep)
                continue
            if views > 0:
                dbg_views_pos += 1
            _upsert_interaction(
                etype,
                int(eid),
                int(views),
                brand_based=brand_used,
                brand_label=brand_label,
                brand_qid=brand_qid,
                source_project=(brand_project or (project if title else None)),
                source_title=(brand_title or (title if title else None)),
            )
            processed += 1
            time.sleep(args.sleep)
        db.session.commit()
        print(
            f"Fetched Wikipedia pageviews for {processed} entities; days={args.days}; types={','.join(types_to_run)}\n"
            f"  hits zh-title={dbg_hit_title_zh}, en-title={dbg_hit_title_en}, wikidata={dbg_hit_wd}, brand={dbg_hit_brand}, views>0={dbg_views_pos}"
        )


if __name__ == "__main__":
    main()
