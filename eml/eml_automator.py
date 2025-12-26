import os
import email
import logging
from dotenv import load_dotenv

# --- Environment Configuration (CRITICAL: Load before other imports) ---
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from email_reply_parser import EmailReplyParser
from bs4 import BeautifulSoup

from crm_client import RealTimeXClient
from intelligence import IntelligenceLayer, AnalysisResult
from persistence import PersistenceLayer

# --- Production Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Configuration (Loaded from Environment) ---
CRM_API_BASE_URL = os.environ.get("CRM_API_BASE_URL")
CRM_API_KEY = os.environ.get("CRM_API_KEY")

class EMLProcessor:
    def __init__(self, crm_client: RealTimeXClient, intelligence: IntelligenceLayer, persistence: PersistenceLayer):
        self.crm = crm_client
        self.ai = intelligence
        self.db = persistence

    def parse_eml(self, file_path: str):
        try:
            with open(file_path, 'rb') as f:
                msg = BytesParser(policy=policy.default).parse(f)
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise
        
        headers = {
            "Subject": msg.get('subject', ''),
            "From": msg.get('from', ''),
            "To": msg.get('to', ''),
            "Cc": msg.get('cc', ''),
            "Bcc": msg.get('bcc', ''),
            "Date": msg.get('date', ''),
            "Message-ID": msg.get('message-id', '')
        }
        
        body = ""
        html_body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                charset = part.get_content_charset() or 'utf-8'
                try:
                    payload = part.get_payload(decode=True).decode(charset, errors='ignore')
                    if content_type == 'text/plain':
                        body = payload
                    elif content_type == 'text/html':
                        html_body = payload
                except:
                    continue
        else:
            charset = msg.get_content_charset() or 'utf-8'
            payload = msg.get_payload(decode=True).decode(charset, errors='ignore')
            if msg.get_content_type() == 'text/html':
                html_body = payload
            else:
                body = payload
        
        # Prefer HTML for structural conversion if available, otherwise use plain body
        if html_body:
            # We still do a quick BS4 pass to remove scripts/styles before passing to AI
            soup = BeautifulSoup(html_body, "html.parser")
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            # We return the partially cleaned HTML to allow IntelligenceLayer._smart_clean to use markdownify
            return headers, str(soup)
        
        cleaned_body = EmailReplyParser.read(body).text
        return headers, cleaned_body

    def process(self, file_path: str, force: bool = False):
        headers, body = self.parse_eml(file_path)
        message_id = headers.get("Message-ID")
        
        if not force and self.db.is_already_processed(message_id):
            logger.info(f"Skipping already processed email: {message_id}")
            return

        analysis = self.ai.analyze_text(body, context_date=headers.get("Date", "Unknown"))
        if not analysis:
            logger.warning("Intelligence layer failed to return analysis. Proceeding with caution.")
        
        # Parse participants
        participants_raw = []
        sender_raw = getaddresses([headers.get("From", "")])[0]
        participants_raw.append(sender_raw)
        for h in ["To", "Cc", "Bcc"]:
            participants_raw.extend(getaddresses([headers.get(h, "")]))
        
        seen_emails = set()
        participants = []
        for name, addr in participants_raw:
            if addr and addr not in seen_emails:
                participants.append((name, addr))
                seen_emails.add(addr)
        
        logger.info(f"Parsed Participants: {participants}")
        
        primary_company_id = None
        resolved_contacts = []
        company_cache = {}
        contact_cache = {}
        
        for name, email_addr in participants:
            domain = email_addr.split("@")[-1] if "@" in email_addr else ""
            company_name = domain
            company_kwargs = {}
            is_sender = (email_addr == sender_raw[1])
            
            if analysis and is_sender:
                if analysis.company_search_query and not (analysis.company_details and analysis.company_details.sector):
                    search_results = self.ai.web_search_company(analysis.company_search_query)
                    if search_results:
                        if not analysis.company_details:
                            analysis.company_details = search_results
                        else:
                            for field in search_results.model_fields:
                                if not getattr(analysis.company_details, field):
                                    setattr(analysis.company_details, field, getattr(search_results, field))

                if analysis.company_details:
                    company_name = analysis.company_details.name or company_name
                    company_kwargs = analysis.company_details.model_dump(exclude={"name", "website"})

            # Upsert Company
            company_id = None
            if domain:
                if domain in company_cache:
                    company_id = company_cache[domain]
                else:
                    company_id = self.crm.upsert_company(company_name, website=domain, **company_kwargs)
                    if company_id:
                        company_cache[domain] = company_id
            
            if company_id and not primary_company_id:
                primary_company_id = company_id
            
            # Upsert Contact
            cid = None
            contact_kwargs = {}
            first_name = ""
            last_name = ""
            if name:
                parts = name.split(" ", 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""

            if analysis and is_sender:
                raw_info = analysis.sender_info.model_dump(exclude={"company"})
                if raw_info.get("phone"):
                    contact_kwargs["phone_jsonb"] = [{"number": raw_info["phone"], "type": "Work"}]
                for field in ["title", "background", "linkedin_url", "gender"]:
                    if raw_info.get(field):
                        contact_kwargs[field] = raw_info[field]

            if email_addr in contact_cache:
                cid = contact_cache[email_addr]
            else:
                cid = self.crm.upsert_contact(
                    email_addr, 
                    first_name=first_name, 
                    last_name=last_name, 
                    company_id=company_id or primary_company_id,
                    **contact_kwargs
                )
                if cid:
                    contact_cache[email_addr] = cid
            
            if cid:
                resolved_contacts.append((email_addr, cid))

        # Action Logic
        if not resolved_contacts:
            logger.warning("No contacts resolved. Cannot link activities.")
            return

        # primary contact is first recipient or sender
        primary_contact_id = None
        for email, cid in resolved_contacts:
            if email != sender_raw[1]:
                primary_contact_id = cid
                break
        if not primary_contact_id:
            primary_contact_id = resolved_contacts[0][1]

        # Extract email timestamp for accurate activity dating
        email_date = headers.get('Date', None)
        
        # Upload EML once and get the attachment URL
        eml_attachment_url = None
        filename = os.path.basename(file_path)
        
        try:
            with open(file_path, "rb") as f:
                file_content = f.read()
            
            # Upload via multipart to get URL back
            files_payload = [("files", (filename, file_content, "message/rfc822"))]
            
            # Create a temporary note to upload the file and get URL
            temp_response = self.crm._upload_and_get_attachment_url(files_payload)
            if temp_response:
                eml_attachment_url = temp_response
        except Exception as e:
            logger.error(f"Failed to upload EML attachment: {e}")
        
        # Create notes for ALL participants
        all_contact_ids = [cid for _, cid in resolved_contacts if cid]
        
        for contact_id in all_contact_ids:
            is_sender = (contact_id == primary_contact_id)
            
            # Personalize note text based on role
            if is_sender:
                activity_text = f"📧 **Email Sent**\n\nSubject: {headers.get('Subject')}\n\n"
            else:
                activity_text = f"📨 **Email Received**\n\nSubject: {headers.get('Subject')}\n\n"
            
            if analysis:
                activity_text += f"**Sentiment**: {analysis.sentiment} 🟢  |  **Intent**: {analysis.intent} 🎯\n\n"
                activity_text += f"{analysis.summary}\n\n"
            
            activity_text += "[Original EML file attached below]"
            
            # Create note with shared attachment URL
            note_kwargs = {
                "contact_id": contact_id,
                "status": "New"
            }
            
            if email_date:
                note_kwargs["date"] = email_date
            
            if eml_attachment_url:
                note_kwargs["attachments"] = [{
                    "url": eml_attachment_url,
                    "name": filename,
                    "type": "message/rfc822"
                }]
            
            self.crm.log_activity(activity_text, **note_kwargs)
        
        # Optional: Create company-level note if primary company exists
        if primary_company_id and analysis:
            company_note = f"📧 **Email Activity**\n\nSubject: {headers.get('Subject')}\n\n"
            company_note += f"Participants: {len(all_contact_ids)} contacts\n\n"
            company_note += f"{analysis.summary}\n\n"
            company_note += "[Original EML file attached below]"
            
            company_kwargs = {
                "activity_type": "company_note",
                "company_id": primary_company_id,
            }
            
            if email_date:
                company_kwargs["date"] = email_date
                
            if eml_attachment_url:
                company_kwargs["attachments"] = [{
                    "url": eml_attachment_url,
                    "name": filename,
                    "type": "message/rfc822"
                }]
            
            self.crm.log_activity(company_note, **company_kwargs)
        
        # Tasks (only for primary contact)
        if primary_contact_id and analysis and analysis.suggested_tasks:
            for task in analysis.suggested_tasks:
                self.crm.create_task(primary_contact_id, task.description, task.due_date, task.priority, status=task.status)
        
        # Deal
        if analysis and analysis.deal_info and analysis.intent in ["Sales", "Demo"] and primary_company_id:
            deal_kwargs = analysis.deal_info.model_dump(exclude={"name", "amount", "stage"})
            self.crm.create_deal(
                primary_company_id, 
                [cid for _, cid in resolved_contacts], 
                analysis.deal_info.name, 
                    analysis.deal_info.amount or 0, 
                    analysis.deal_info.stage,
                    **deal_kwargs
                )
            
            self.db.mark_as_processed(message_id)
            logger.info(f"Successfully finished processing for EML.")

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Process EML files and sync to RealTimeX CRM.")
    parser.add_argument("eml_path", help="Path to the .eml file to process")
    parser.add_argument("--api-key", help="RealTimeX API Key (overrides CRM_API_KEY env)")
    parser.add_argument("--base-url", help="RealTimeX Base URL (overrides CRM_API_BASE_URL env)")
    parser.add_argument("--db-path", help="Path to SQLite persistence DB (overrides PERSISTENCE_DB_PATH env)")
    parser.add_argument("--llm-url", help="LLM Base URL (overrides LLM_BASE_URL env)")
    parser.add_argument("--llm-model", help="LLM Model name (overrides LLM_MODEL env)")
    parser.add_argument("--env-file", help="Path to custom .env file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging (DEBUG level)")
    parser.add_argument("--force", "-f", action="store_true", help="Force reprocessing even if EML was already processed")
    
    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # If custom env file is provided, load it now (overwriting existing env vars if needed)
    if args.env_file:
        if os.path.exists(args.env_file):
            load_dotenv(args.env_file, override=True)
            # Re-read global config that are evaluated here
            CRM_API_BASE_URL = os.environ.get("CRM_API_BASE_URL")
            CRM_API_KEY = os.environ.get("CRM_API_KEY")
        else:
            logger.warning(f"Specified --env-file not found: {args.env_file}")

    # Priority: Flag > EnvVar > Default
    final_api_key = args.api_key or CRM_API_KEY
    final_base_url = args.base_url or CRM_API_BASE_URL
    final_llm_url = args.llm_url or os.environ.get("LLM_BASE_URL")
    final_llm_model = args.llm_model or os.environ.get("LLM_MODEL")

    if not final_api_key:
        logger.error("CRM_API_KEY not set via environment variable or --api-key flag. Exiting.")
        sys.exit(1)
    
    try:
        client = RealTimeXClient(final_api_key, final_base_url)
        intelligence = IntelligenceLayer(
            api_key=os.environ.get("LLM_API_KEY"),
            base_url=final_llm_url,
            model=final_llm_model
        )
        persistence = PersistenceLayer()
        
        processor = EMLProcessor(client, intelligence, persistence)
        processor.process(args.eml_path, force=args.force)
    except Exception as e:
        logger.critical(f"Fatal error during processing: {e}", exc_info=True)
        sys.exit(1)
