import os
import requests
import logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

class RealTimeXClient:
    def __init__(self, api_key: str, base_url: str):
        if not api_key:
            raise ValueError("CRM_API_KEY must be provided")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.base_url = base_url.rstrip("/")
        self.public_domains = {"gmail.com", "outlook.com", "yahoo.com", "hotmail.com", "icloud.com", "me.com", "msn.com"}

    def is_public_domain(self, domain: str) -> bool:
        return domain.lower() in self.public_domains

    def upsert_company(self, name: str, website: Optional[str] = None, **kwargs):
        if website and self.is_public_domain(website):
            return None
        
        url = f"{self.base_url}/api-v1-companies"
        
        # Define allowed fields based on API schema and SQL definitions
        allowed_fields = {
            "name", "sector", "size", "linkedin_url", "website", "phone_number", 
            "address", "zipcode", "city", "stateAbbr", "sales_id", "context_links", 
            "country", "description", "revenue", "tax_identifier"
        }
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_fields}

        # Cross-run deduplication: Search by website/domain first
        if website:
            try:
                search_response = requests.get(
                    f"{url}?website={website}",
                    headers=self.headers,
                    timeout=10
                )
                if search_response.status_code == 200:
                    data = search_response.json().get("data", [])
                    if data and len(data) > 0:
                        company_id = data[0].get("id")
                        if filtered_kwargs:
                            try:
                                requests.patch(f"{url}/{company_id}", headers=self.headers, json=filtered_kwargs, timeout=10)
                            except Exception as e:
                                logger.error(f"Failed to update existing company {company_id}: {e}")
                        return company_id
            except Exception as e:
                logger.warning(f"Website search failed during upsert: {e}")

        # Fallback: Search by name
        try:
            search_response = requests.get(
                f"{url}?name={name}",
                headers=self.headers,
                timeout=10
            )
            if search_response.status_code == 200:
                data = search_response.json().get("data", [])
                if data and len(data) > 0:
                    company_id = data[0].get("id")
                    if filtered_kwargs:
                        try:
                            requests.patch(f"{url}/{company_id}", headers=self.headers, json=filtered_kwargs, timeout=10)
                        except Exception as e:
                            logger.error(f"Failed to update existing company {company_id} by name: {e}")
                        return company_id
        except Exception as e:
            logger.warning(f"Name search failed: {e}")

        payload = {"name": name}
        if website:
            payload["website"] = website
        payload.update(filtered_kwargs)
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code in [200, 201]:
                return response.json().get("data", {}).get("id")
        except Exception as e:
            print(f"Error upserting company: {e}")
        
        return None 

    def upsert_contact(self, email_addr: str, first_name: Optional[str] = None, last_name: Optional[str] = None, company_id: Optional[int] = None, **kwargs):
        url = f"{self.base_url}/api-v1-contacts"
        
        # Define allowed fields based on API schema and SQL definitions
        allowed_fields = {
            "first_name", "last_name", "gender", "title", "background", 
            "status", "tags", "company_id", "sales_id", "linkedin_url", 
            "email_jsonb", "phone_jsonb", "has_newsletter"
        }
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in allowed_fields}

        try:
            search_response = requests.get(
                f"{url}?email={email_addr}",
                headers=self.headers,
                timeout=10
            )
            if search_response.status_code == 200:
                data = search_response.json().get("data", [])
                if data and len(data) > 0:
                    contact_id = data[0].get("id")
                    update_payload = {}
                    if first_name: update_payload["first_name"] = first_name
                    if last_name: update_payload["last_name"] = last_name
                    if company_id: update_payload["company_id"] = company_id
                    update_payload.update(filtered_kwargs)
                    if update_payload:
                        try:
                            requests.patch(f"{url}/{contact_id}", headers=self.headers, json=update_payload, timeout=10)
                        except Exception as e:
                            logger.error(f"Failed to update existing contact {contact_id}: {e}")
                    return contact_id
        except Exception as e:
            logger.warning(f"Email search failed: {e}")

        payload = {
            "first_name": first_name,
            "last_name": last_name,
            "email_jsonb": [{"email": email_addr, "type": "Work"}],
            "company_id": company_id
        }
        payload.update(filtered_kwargs)
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code in [200, 201]:
                return response.json().get("data", {}).get("id")
            else:
                logger.error(f"Contact creation failed with {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Error upserting contact: {e}")
        return None

    def log_activity(self, contact_id: int, text: str, activity_type: str = "contact_note", **kwargs):
        # Specific fields for activity based on contactNotes/companyNotes/dealNotes SQL
        allowed_fields = {"type", "contact_id", "deal_id", "company_id", "text", "sales_id", "status", "date"}
        payload = {
            "type": activity_type,
            "contact_id": contact_id,
            "text": text
        }
        # Add any other allowed fields from kwargs
        for k, v in kwargs.items():
            if k in allowed_fields:
                payload[k] = v

        try:
            response = requests.post(
                f"{self.base_url}/api-v1-activities",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            return response.status_code in [200, 201]
        except Exception as e:
            print(f"Error logging activity: {e}")
            return False

    def create_task(self, contact_id: int, description: str, due_date: Optional[str] = None, priority: str = "Medium", **kwargs):
        # Specific fields for task based on tasks SQL
        allowed_fields = {"type", "contact_id", "text", "due_date", "sales_id", "done_date"}
        payload = {
            "type": "task",
            "contact_id": contact_id,
            "text": description,
            "due_date": due_date
        }
        # Add priority if it's mapped in the API even if not in raw SQL
        if priority:
            payload["priority"] = priority

        # Add any other allowed fields from kwargs
        for k, v in kwargs.items():
            if k in allowed_fields:
                payload[k] = v

        try:
            response = requests.post(
                f"{self.base_url}/api-v1-activities",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            return response.status_code in [200, 201]
        except Exception as e:
            print(f"Error creating task: {e}")
            return False

    def create_deal(self, company_id: int, contact_ids: List[int], name: str, amount: float = 0, stage: str = "discovery", **kwargs):
        # Specific fields for deal based on deals SQL
        allowed_fields = {
            "name", "company_id", "contact_ids", "category", "stage", 
            "description", "amount", "expected_closing_date", "sales_id", "index"
        }
        payload = {
            "name": name,
            "amount": amount,
            "stage": stage,
            "company_id": company_id,
            "contact_ids": contact_ids
        }
        # Add any other allowed fields from kwargs
        for k, v in kwargs.items():
            if k in allowed_fields:
                payload[k] = v

        try:
            response = requests.post(
                f"{self.base_url}/api-v1-deals",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            if response.status_code in [200, 201]:
                return response.json().get("data", {}).get("id")
        except Exception as e:
            print(f"Error creating deal: {e}")
        return None
