from app import create_app

app = create_app()

if __name__ == "__main__":
    # 开发环境直接运行，生产环境可使用 WSGI/ASGI 服务器
    app.run(host="0.0.0.0", port=5000, debug=True)
