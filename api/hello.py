import sys

def handler(request, response):
    try:
        print("Function invoked", file=sys.stderr)
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response.send({"message": "Hello from Python on Vercel!"})
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        response.status_code = 500
        response.send({"error": str(e)})
