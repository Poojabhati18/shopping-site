def handler(request, response):
    try:
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response.send({"message": "Hello from Python on Vercel!"})
    except Exception as e:
        response.status_code = 500
        response.send({"error": str(e)})
