import json
import sys
from pathlib import Path
import pytest

# Add backend package root to sys.path so that `import app` resolves
_TEST_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TEST_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from app import create_app
from app.routes import route as route_module


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_v3_drive_success(client, monkeypatch):
    app = client.application
    app.config["AMAP_WEB_KEY"] = "k"
    app.config["AMAP_API_VERSION"] = "v3"

    def stub_http_get_json(url, timeout=6.0, use_cache=True):
        if "/v3/direction/driving" in url:
            return {
                "status": "1",
                "route": {"paths": [{"distance": "10000", "duration": "600"}]},
            }
        return None

    monkeypatch.setattr(route_module, "_http_get_json", stub_http_get_json)

    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 116.41, "lat": 39.91},
            "mode": "drive",
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))
    assert "options" in data and len(data["options"]) >= 1
    assert data["options"][0]["duration_min"] == 10
    assert data["options"][0]["distance_km"] == 10.0


def test_v5_transit_city_infer(client, monkeypatch):
    app = client.application
    app.config["AMAP_WEB_KEY"] = "k"
    app.config["AMAP_API_VERSION"] = "v5"

    def stub_guess_citycode(lng, lat, key):
        return "010"

    def stub_http_get_json(url, timeout=6.0, use_cache=True):
        if "/v5/direction/transit/integrated" in url:
            return {
                "status": "1",
                "route": {"transits": [{"duration": "1200"}, {"duration": "1800"}]},
            }
        return None

    monkeypatch.setattr(route_module, "_amap_guess_citycode", stub_guess_citycode)
    monkeypatch.setattr(route_module, "_http_get_json", stub_http_get_json)

    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 116.41, "lat": 39.91},
            "mode": "transit",
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))
    assert "options" in data and len(data["options"]) == 2
    assert data["options"][0]["duration_min"] == 20


def test_fallback_to_v3_distance_when_main_fail(client, monkeypatch):
    app = client.application
    app.config["AMAP_WEB_KEY"] = "k"
    app.config["AMAP_API_VERSION"] = "v3"

    def stub_http_get_json(url, timeout=6.0, use_cache=True):
        if "/v3/direction/driving" in url:
            return {"status": "0", "info": "OVER_DIRECTION_RANGE"}
        if "/v3/distance" in url:
            return {
                "status": "1",
                "results": [{"distance": "5000", "duration": "600"}],
            }
        return None

    monkeypatch.setattr(route_module, "_http_get_json", stub_http_get_json)

    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 116.41, "lat": 39.91},
            "mode": "drive",
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))
    assert "options" in data and len(data["options"]) == 3
    labels = [o["label"] for o in data["options"]]
    assert "最快" in labels and "步行优先" in labels


def test_haversine_fallback_without_key(client):
    app = client.application
    app.config["AMAP_WEB_KEY"] = None

    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 116.41, "lat": 39.91},
            "mode": "walk",
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))
    assert "options" in data and len(data["options"]) == 3
    assert all(int(o["duration_min"]) >= 1 for o in data["options"])


def test_v3_transit_cityd_cross_city(client, monkeypatch):
    app = client.application
    app.config["AMAP_WEB_KEY"] = "k"
    app.config["AMAP_API_VERSION"] = "v3"

    called_urls = []

    def stub_guess_citycode(lng, lat, key):
        if abs(lng - 116.4) < 1e-6:
            return "010"
        return "021"

    def stub_http_get_json(url, timeout=6.0, use_cache=True):
        called_urls.append(url)
        if "/v3/direction/transit/integrated" in url:
            return {"status": "1", "route": {"transits": [{"duration": "900"}]}}
        return None

    monkeypatch.setattr(route_module, "_amap_guess_citycode", stub_guess_citycode)
    monkeypatch.setattr(route_module, "_http_get_json", stub_http_get_json)

    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 121.47, "lat": 31.23},
            "mode": "transit",
        },
    )
    assert resp.status_code == 200
    assert any("/v3/direction/transit/integrated" in u for u in called_urls)
    q = "&".join(called_urls[-1].split("?")[1].split("&"))
    assert "city=010" in q
    assert "cityd=021" in q


def test_metrics_endpoint_summary_fields(client):
    resp = client.get("/api/route/metrics")
    assert resp.status_code == 200
    data = json.loads(resp.data.decode("utf-8"))
    assert "summary" in data
    summary = data["summary"]
    assert isinstance(summary, dict)
    for k in [
        "amap_success_total",
        "amap_fail_total",
        "route_options_total",
        "source_breakdown",
        "amap_cache_hit",
        "amap_cache_miss",
        "amap_rate_limited_skips",
        "fallback_haversine",
    ]:
        assert k in summary


def test_v5_drive_waypoints_array_serialization(client, monkeypatch):
    app = client.application
    app.config["AMAP_WEB_KEY"] = "k"
    app.config["AMAP_API_VERSION"] = "v5"

    called_url = {"u": None}

    def stub_http_get_json(url, timeout=6.0, use_cache=True):
        called_url["u"] = url
        if "/v5/direction/driving" in url:
            return {
                "status": "1",
                "route": {"paths": [{"distance": "12000", "duration": "720"}]},
            }
        return None

    monkeypatch.setattr(route_module, "_http_get_json", stub_http_get_json)

    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 116.41, "lat": 39.91},
            "mode": "drive",
            "api_version": "v5",
            "waypoints": [
                {"lng": 116.401, "lat": 39.901},
                [116.402, 39.902],
                "116.403,39.903",
            ],
        },
    )
    assert resp.status_code == 200
    assert called_url["u"] is not None and "/v5/direction/driving" in called_url["u"]
    q = "&".join(called_url["u"].split("?")[1].split("&"))
    assert "waypoints=116.401%2C39.901%3B116.402%2C39.902%3B116.403%2C39.903" in q


def test_v5_drive_waypoints_too_many(client):
    app = client.application
    app.config["AMAP_WEB_KEY"] = "k"
    app.config["AMAP_API_VERSION"] = "v5"

    wps = [[116.4 + i * 0.001, 39.9 + i * 0.001] for i in range(17)]
    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 116.41, "lat": 39.91},
            "mode": "drive",
            "api_version": "v5",
            "waypoints": wps,
        },
    )
    assert resp.status_code == 400
    data = json.loads(resp.data.decode("utf-8"))
    assert data.get("error") == "waypoints exceed 16"


def test_v5_transit_ad_params_and_flags_passthrough(client, monkeypatch):
    app = client.application
    app.config["AMAP_WEB_KEY"] = "k"
    app.config["AMAP_API_VERSION"] = "v5"

    called_urls = []

    def stub_http_get_json(url, timeout=6.0, use_cache=True):
        called_urls.append(url)
        if "/v5/direction/transit/integrated" in url:
            return {
                "status": "1",
                "route": {"transits": [{"duration": "600"}]},
            }
        return None

    monkeypatch.setattr(route_module, "_http_get_json", stub_http_get_json)

    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 116.41, "lat": 39.91},
            "mode": "transit",
            "api_version": "v5",
            "city1": "010",
            "city2": "010",
            "ad1": "110105",
            "ad2": "110108",
            "transit_strategy": "0",
            "alternative_route": 3,
            "multiexport": 1,
            "nightflag": 1,
        },
    )
    assert resp.status_code == 200
    assert any("/v5/direction/transit/integrated" in u for u in called_urls)
    q = "&".join(called_urls[-1].split("?")[1].split("&"))
    assert "city1=010" in q and "city2=010" in q
    assert "ad1=110105" in q and "ad2=110108" in q
    assert "AlternativeRoute=3" in q
    assert "multiexport=1" in q and "nightflag=1" in q


def test_v5_transit_invalid_flags_sanitized(client, monkeypatch):
    app = client.application
    app.config["AMAP_WEB_KEY"] = "k"
    app.config["AMAP_API_VERSION"] = "v5"

    called_urls = []

    def stub_http_get_json(url, timeout=6.0, use_cache=True):
        called_urls.append(url)
        if "/v5/direction/transit/integrated" in url:
            return {
                "status": "1",
                "route": {"transits": [{"duration": "600"}]},
            }
        return None

    monkeypatch.setattr(route_module, "_http_get_json", stub_http_get_json)

    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 116.41, "lat": 39.91},
            "mode": "transit",
            "api_version": "v5",
            "city1": "010",
            "city2": "010",
            "alternative_route": 11,
            "multiexport": 2,
            "nightflag": -1,
        },
    )
    assert resp.status_code == 200
    q = "&".join(called_urls[-1].split("?")[1].split("&"))
    assert "/v5/direction/transit/integrated" in called_urls[-1]
    assert "AlternativeRoute=" not in q
    assert "multiexport=2" not in q
    assert "nightflag=-1" not in q


def test_request_drive_strategy_override_v5(client, monkeypatch):
    app = client.application
    app.config["AMAP_WEB_KEY"] = "k"
    app.config["AMAP_API_VERSION"] = "v5"

    seen = {}

    def stub_http_get_json(url, timeout=6.0, use_cache=True):
        seen["url"] = url
        if "/v5/direction/driving" in url:
            return {
                "status": "1",
                "route": {"paths": [{"distance": "1000", "duration": "120"}]},
            }
        return None

    monkeypatch.setattr(route_module, "_http_get_json", stub_http_get_json)

    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 116.41, "lat": 39.91},
            "mode": "drive",
            "drive_strategy": "33",
        },
    )
    assert resp.status_code == 200
    assert "/v5/direction/driving" in seen.get("url", "")
    assert "strategy=33" in seen.get("url", "")


def test_request_transit_strategy_override_v3(client, monkeypatch):
    app = client.application
    app.config["AMAP_WEB_KEY"] = "k"
    app.config["AMAP_API_VERSION"] = "v3"

    def stub_guess_citycode(lng, lat, key):
        return "010"

    seen = {}

    def stub_http_get_json(url, timeout=6.0, use_cache=True):
        seen["url"] = url
        if "/v3/direction/transit/integrated" in url:
            return {
                "status": "1",
                "route": {"transits": [{"duration": "600"}]},
            }
        return None

    monkeypatch.setattr(route_module, "_amap_guess_citycode", stub_guess_citycode)
    monkeypatch.setattr(route_module, "_http_get_json", stub_http_get_json)

    resp = client.post(
        "/api/route/options",
        json={
            "origin": {"lng": 116.4, "lat": 39.9},
            "destination": {"lng": 116.41, "lat": 39.91},
            "mode": "transit",
            "transit_strategy": "3",
        },
    )
    assert resp.status_code == 200
    assert "/v3/direction/transit/integrated" in seen.get("url", "")
    assert "strategy=3" in seen.get("url", "")
