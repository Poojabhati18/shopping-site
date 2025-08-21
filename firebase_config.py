import os, json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load environment variables (for local development; Render ignores .env)
load_dotenv()

# Get the Firebase credentials from environment
firebase_creds = os.getenv("FIREBASE_CREDENTIALS")
if not firebase_creds:
    raise Exception("FIREBASE_CREDENTIALS environment variable not found")

# Convert JSON string into dict
cred_dict = json.loads(firebase_creds)

# Fix private_key newlines in case they are escaped incorrectly
if "private_key" in cred_dict:
    cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

# Initialize Firebase only once
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

# Firestore client
db = firestore.client()
