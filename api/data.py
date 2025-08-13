import requests
import os

API_KEY = os.getenv("AIzaSyCcBgBPogs47iWDn3M-J4-nRe_qxwWe1c8")

def handler(request, response):
    try:
        city = request.path_params.get("city")
        if not city:
            response.status_code = 400
            response.send({"error": "City not provided"})
            return

        url = f"https://api.weatherapi.com/v1/current.json?key={API_KEY}&q={city}"
        res = requests.get(url)
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response.send(res.json())
    except Exception as e:
        response.status_code = 500
        response.send({"error": str(e)})
