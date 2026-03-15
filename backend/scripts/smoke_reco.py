from app import create_app


def main():
    app = create_app()
    app.testing = True
    ctx = app.app_context()
    ctx.push()
    try:
        client = app.test_client()
        paths = [
            "/api/recommend/scenic-spots?limit=5",
            "/api/recommend/hotels?limit=5",
            "/api/recommend/foods?limit=5",
        ]
        for p in paths:
            resp = client.get(p)
            print("PATH", p, "STATUS", resp.status_code)
            try:
                data = resp.get_json()
            except Exception as e:
                print("NO_JSON", e, resp.data[:200])
                continue
            items = data.get("items", [])
            print("COUNT", len(items))
            for it in items[:5]:
                print(
                    it.get("id"),
                    it.get("name"),
                    it.get("rating_avg"),
                    it.get("rating_count"),
                )
    finally:
        ctx.pop()


if __name__ == "__main__":
    main()
