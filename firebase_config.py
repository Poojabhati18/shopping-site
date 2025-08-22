import os
import json
import firebase_admin
from firebase_admin import credentials, firestore

def _init_app():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    service_account_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
    if service_account_json:
        try:
            # Fix PEM newlines
            service_account_json = service_account_json.replace('\\n', '\n')
            # Parse JSON
            cred_dict = json.loads(service_account_json)
            cred = credentials.Certificate(cred_dict)
            return firebase_admin.initialize_app(cred)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON in Firebase env variable: {e}")
        except Exception as e:
            raise RuntimeError(f"Invalid Firebase credentials from env: {e}")

    # Fallback to local JSON
    local_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")
    if os.path.exists(local_path):
        try:
            cred = credentials.Certificate(local_path)
            return firebase_admin.initialize_app(cred)
        except Exception as e:
            raise RuntimeError(f"Failed to load local Firebase JSON file: {e}")

    raise RuntimeError(
        "Firebase credentials not found. Set GOOGLE_APPLICATION_CREDENTIALS_JSON "
        "or place serviceAccountKey.json in the project directory."
    )

firebase_app = _init_app()
db = firestore.client()
