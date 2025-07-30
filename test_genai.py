# test_env_key.py

import os
from dotenv import load_dotenv
import google.genai as genai

# Load API key from .env
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Debug output
print(f"Loaded key (repr): {repr(api_key)}")
print(f"Key length: {len(api_key) if api_key else 'None'}")
print(f"Starts with 'A' or 'I'? {'Yes' if api_key and (api_key.startswith('A') or api_key.startswith('I')) else 'No'}")

# Safety check
if not api_key:
    raise ValueError("API key not found in environment")

# Initialize the Gemini client
client = genai.Client(api_key=api_key)

# Generate content using Gemini
try:
    response = client.models.generate_content(
        model="gemini-2.0-flash-001",
        contents="I am interested in your product"
    )
    print("Response:\n", response.text)
except Exception as e:
    print("Error while calling Gemini:", e)
