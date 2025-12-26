import os
import logging
from dotenv import load_dotenv
import requests

logging.basicConfig(level=logging.DEBUG)
load_dotenv()

api_key = os.environ.get("CRM_API_KEY")
base_url = os.environ.get("CRM_API_BASE_URL")

# Create test file
test_content = b"This is a test EML file for debugging attachment URL extraction."
filename = "debug_attachment_url.eml"

# Prepare multipart payload
files_payload = [("files", (filename, test_content, "message/rfc822"))]

headers = {
    "Authorization": f"Bearer {api_key}",
}

data = {
    "type": "contact_note",
    "text": "[Debug: Testing attachment URL extraction]",
    "contact_id": "558",
    "status": "New"
}

print("Sending multipart request...")
response = requests.post(
    f"{base_url}/api-v1-activities",
    headers=headers,
    data=data,
    files=files_payload,
    timeout=30
)

print(f"\nStatus Code: {response.status_code}")
print(f"\nResponse Headers: {dict(response.headers)}")
print(f"\nResponse Body:")
print(response.text)

if response.status_code in [200, 201]:
    result = response.json()
    print(f"\n\nParsed JSON:")
    import json
    print(json.dumps(result, indent=2))
    
    # Try to extract attachment URL
    if result.get("data"):
        print(f"\n\nData object: {result['data']}")
        if result["data"].get("attachments"):
            print(f"\nAttachments: {result['data']['attachments']}")
            if len(result["data"]["attachments"]) > 0:
                print(f"\nFirst attachment: {result['data']['attachments'][0]}")
                print(f"\nAttachment URL (src): {result['data']['attachments'][0].get('src')}")
