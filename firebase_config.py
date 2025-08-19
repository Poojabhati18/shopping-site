import firebase_admin
from firebase_admin import credentials, firestore

# Full path to the JSON file
cred = credentials.Certificate(r"C:/Users/digvi/shopping-site/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()
