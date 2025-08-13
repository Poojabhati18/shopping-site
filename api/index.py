from pathlib import Path

def handler(request, response):
    try:
        # Serve index.html
        file_path = Path(__file__).parent.parent / "templates" / "index.html"
        html = file_path.read_text(encoding="utf-8")
        response.headers["Content-Type"] = "text/html"
        response.status_code = 200
        response.send(html)
    except Exception as e:
        response.status_code = 500
        response.send(f"Error: {e}")
