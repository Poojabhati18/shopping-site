def handler(request, response):
    response.status_code = 200
    response.headers["Content-Type"] = "application/json"
    response.send({"message": "Hello from Python on Vercel!"})
