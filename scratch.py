import asyncio
from backend.app.main import app

async def main():
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.1"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/health",
        "raw_path": b"/health",
        "query_string": b"",
        "root_path": "",
        "scheme": "http",
        "headers": [(b"host", b"test")],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    events = []

    async def send(message):
        events.append(message)

    await app(scope, receive, send)

    for e in events:
        print(e)

if __name__ == "__main__":
    asyncio.run(main())
