import requests
import os

HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY")

def create_contact(email, phone=None):
    url = "https://api.hubapi.com/crm/v3/objects/contacts"

    headers = {
        "Authorization": f"Bearer {HUBSPOT_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "properties": {
            "email": email,
            "phone": phone
        }
    }

    response = requests.post(url, json=data, headers=headers)

    print("HubSpot response:", response.status_code, response.text)

    return response.json()