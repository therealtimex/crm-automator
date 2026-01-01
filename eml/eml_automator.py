# /// script
# dependencies = [
#     "openai>=1.0.0",
#     "instructor",
#     "python-dotenv",
#     "requests",
#     "beautifulsoup4",
#     "email-reply-parser",
#     "markdownify",
#     "ddgs",
#     "tqdm",
# ]
# ///

import os
import email
import logging
import base64
import json
from tqdm import tqdm
from dotenv import load_dotenv

from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
from email_reply_parser import EmailReplyParser
from bs4 import BeautifulSoup

try:
    from crm_client import RealTimeXClient
    from intelligence import IntelligenceLayer, AnalysisResult
    from persistence import PersistenceLayer
    from filters import EmailFilterOrchestrator, log_suppressed_email
except ImportError:
    from eml.crm_client import RealTimeXClient
    from eml.intelligence import IntelligenceLayer, AnalysisResult
    from eml.persistence import PersistenceLayer
    from eml.filters import EmailFilterOrchestrator, log_suppressed_email

# --- Production Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EMLProcessor:
    def __init__(self, crm_client: RealTimeXClient, intelligence: IntelligenceLayer, persistence: PersistenceLayer):
        self.crm = crm_client
        self.ai = intelligence
        self.db = persistence
        # Load internal domains and specific emails for filtering (comma-separated lists)
        self.internal_domains = [d.strip().lower() for d in os.environ.get("INTERNAL_DOMAINS", "").split(",") if d.strip()]
        self.internal_emails = [e.strip().lower() for e in os.environ.get("INTERNAL_EMAILS", "").split(",") if e.strip()]

        # Initialize email filter orchestrator
        # Reuse the LLM client from intelligence layer for classification
        self.filter_orchestrator = EmailFilterOrchestrator(
            llm_client=intelligence.client.client if hasattr(intelligence, 'client') else None,
            llm_model=os.environ.get("CLASSIFICATION_MODEL", "gpt-4o-mini")
        )

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
            "Message-ID": msg.get('message-id', ''),
            "X-EESA-Category": msg.get('X-EESA-Category'),
            "X-EESA-Summary": msg.get('X-EESA-Summary'),
            "X-EESA-Processed-At": msg.get('X-EESA-Processed-At'),
            "X-EESA-Raw-JSON": msg.get('X-EESA-Raw-JSON')
        }
        
        body = ""
        html_body = ""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition"))
                filename = part.get_filename()
                
                if filename:
                    attachments.append(filename)
                
                # Check for body content
                if "attachment" not in disposition:
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            decoded_payload = payload.decode(charset, errors='ignore')
                            if content_type == 'text/plain':
                                body = decoded_payload
                            elif content_type == 'text/html':
                                html_body = decoded_payload
                    except:
                        continue
        else:
            charset = msg_charset = msg.get_content_charset() or 'utf-8'
            payload = msg.get_payload(decode=True).decode(charset, errors='ignore')
            if msg.get_content_type() == 'text/html':
                html_body = payload
            else:
                body = payload
        
        content_to_analyze = ""
        # Prefer HTML for structural conversion if available, otherwise use plain body
        if html_body:
            # We still do a quick BS4 pass to remove scripts/styles before passing to AI
            soup = BeautifulSoup(html_body, "html.parser")
            for script_or_style in soup(["script", "style"]):
                script_or_style.decompose()
            content_to_analyze = str(soup)
        else:
            content_to_analyze = EmailReplyParser.read(body).text
            
        return headers, content_to_analyze, attachments

    def process(self, file_path: str, force: bool = False):
        from pathlib import Path
        headers, body, attachments = self.parse_eml(file_path)
        message_id = headers.get("Message-ID")

        if not force and self.db.is_already_processed(message_id):
            logger.info(f"Skipping already processed email: {message_id}")
            return

        # === EMAIL FILTERING: Check if email should be processed ===
        # Re-parse for filtering (need Message object for filters)
        with open(file_path, 'rb') as f:
            from email.parser import BytesParser
            from email import policy as email_policy
            email_msg = BytesParser(policy=email_policy.default).parse(f)

        # Check if email should be processed
        decision = self.filter_orchestrator.should_process(email_msg, body)

        if not decision.should_process:
            # Log suppressed email (using SQLite via persistence layer)
            log_suppressed_email(
                Path(file_path),
                email_msg,
                decision.reason,
                decision.category.value if decision.category else None,
                persistence_layer=self.db
            )
            logger.info(f"⊘ Suppressed: {Path(file_path).name} (reason: {decision.reason})")
            return

        logger.info(f"✓ Processing: {Path(file_path).name} (reason: {decision.reason})")

        # Prepare metadata for intelligence layer
        metadata = {
            "From": headers.get('From', 'Unknown'),
            "To": headers.get('To', 'Unknown'),
            "Subject": headers.get('Subject', 'No Subject'),
        }
        if headers.get('Cc'): metadata["Cc"] = headers.get('Cc')
        if attachments:
            metadata["Attachments"] = ", ".join(attachments)

        # Check for EESA metadata to skip LLM analysis
        analysis = None
        eesa_raw_json = headers.get("X-EESA-Raw-JSON")
        if eesa_raw_json:
            try:
                eesa_data = json.loads(base64.b64decode(eesa_raw_json))
                logger.info(f"Found EESA metadata for {message_id}, skipping LLM analysis.")
                analysis = self.ai.hydrate_from_eesa(eesa_data, metadata=metadata)
            except Exception as e:
                logger.warning(f"Failed to decode EESA metadata: {e}. Falling back to LLM analysis.")
        
        if not analysis:
            analysis = self.ai.analyze_text(body, context_date=headers.get("Date", "Unknown"), metadata=metadata)
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
        
        # Prepare extraction mapping
        extracted_info_map = {}
        if analysis:
            # Map primary contact
            if analysis.primary_contact and analysis.primary_contact.email:
                extracted_info_map[analysis.primary_contact.email.lower()] = analysis.primary_contact
            
            # Map others
            for other in analysis.additional_contacts:
                if other.email:
                    extracted_info_map[other.email.lower()] = other

        primary_company_id = None
        resolved_contacts = []
        company_cache = {}
        contact_cache = {}
        
        for name, email_addr in participants:
            email_lower = email_addr.lower()
            domain = email_addr.split("@")[-1] if "@" in email_addr else ""
            is_internal = (domain.lower() in self.internal_domains) or (email_lower in self.internal_emails)
            
            company_name = domain
            company_kwargs = {}
            is_sender = (email_addr == sender_raw[1])
            
            # Skip CRM record creation for internal domains
            if is_internal:
                logger.info(f"Skipping CRM record creation for internal domain participant: {email_addr}")
                continue

            # Get extracted info for this specific participant
            part_info = extracted_info_map.get(email_lower)
            # Fallback for sender if email mapping failed
            if not part_info and is_sender and analysis:
                part_info = analysis.primary_contact

            if part_info:
                # Company Enrichment
                if analysis.company_search_query and not (analysis.company_details and analysis.company_details.sector):
                    # We only search once per email
                    search_results = self.ai.web_search_company(analysis.company_search_query)
                    if search_results:
                        if not analysis.company_details:
                            analysis.company_details = search_results
                        else:
                            for field in search_results.__class__.model_fields:
                                if not getattr(analysis.company_details, field):
                                    setattr(analysis.company_details, field, getattr(search_results, field))

                if analysis.company_details and (is_sender or (part_info and part_info.company)):
                    company_name = analysis.company_details.name or company_name
                    company_kwargs = analysis.company_details.model_dump(exclude={"name", "website", "email"})

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

            # Prepare Contact details
            contact_kwargs = {}
            if part_info:
                # Use extracted first/last names if available, fall back to header-parsed
                if part_info.first_name:
                    first_name = part_info.first_name
                if part_info.last_name:
                    last_name = part_info.last_name
                
                # Exclude fields we handle separately or that don't go to contact
                contact_kwargs = part_info.model_dump(exclude={"email", "first_name", "last_name", "company"})

            contact_id = self.crm.upsert_contact(
                email_addr,
                first_name=first_name,
                last_name=last_name,
                company_id=company_id or primary_company_id,
                **contact_kwargs
            )
            if contact_id:
                contact_cache[email_addr] = contact_id
                resolved_contacts.append((email_addr, contact_id))


        # Action Logic
        if not resolved_contacts:
            logger.warning("No contacts resolved. Cannot link activities.")
            return

        # primary contact selection
        primary_contact_id = None
        
        # 1. Try LLM suggested primary contact
        if analysis and analysis.primary_contact_email:
            p_email = analysis.primary_contact_email.lower()
            for email, cid in resolved_contacts:
                if email.lower() == p_email:
                    primary_contact_id = cid
                    break
        
        # 2. Fallback: pick first recipient or sender
        if not primary_contact_id:
            for email, cid in resolved_contacts:
                if email != sender_raw[1]:
                    primary_contact_id = cid
                    break
        
        if not primary_contact_id:
            primary_contact_id = resolved_contacts[0][1]

        # Extract email timestamp for accurate activity dating
        email_date = headers.get('Date', None)
        
        # Prepare EML file content
        filename = os.path.basename(file_path)
        file_content = None
        
        try:
            with open(file_path, "rb") as f:
                file_content = f.read()
        except Exception as e:
            logger.error(f"Failed to read EML file: {e}")
        
        # Create notes for ALL participants
        all_contact_ids = [cid for _, cid in resolved_contacts if cid]
        eml_attachment_url = None
        
        # Determine the role of the sender for note context
        sender_addr = sender_raw[1]
        sender_email_lower = sender_addr.lower()
        sender_domain = sender_addr.split("@")[-1].lower() if "@" in sender_addr else ""
        sender_is_internal = (sender_domain in self.internal_domains) or (sender_email_lower in self.internal_emails)
        sender_label = "Internal Staff" if sender_is_internal else "External Contact"

        for idx, contact_id in enumerate(all_contact_ids):
            # Find the email for this contact_id to check if it matches primary recipient
            contact_email = next((email for email, cid in resolved_contacts if cid == contact_id), "Unknown")
            is_recipient = (contact_id == primary_contact_id)
            
            # Personalize note text based on role
            if sender_is_internal:
                activity_text = f"📤 **Email from {sender_label}** ({sender_addr})\n"
                activity_text += f"To: {headers.get('To')}\n"
            else:
                activity_text = f"📥 **Email from {sender_label}** ({sender_addr})\n"
            
            activity_text += f"Subject: {headers.get('Subject')}\n"
            activity_text += f"Date: {email_date or 'Unknown'}\n\n"
            
            if analysis:
                activity_text += f"**Sentiment**: {analysis.sentiment} 🟢  |  **Intent**: {analysis.intent} 🎯\n\n"
                activity_text += f"{analysis.summary}\n\n"
            
            activity_text += "[Original EML file attached below]"
            
            # Create note
            note_kwargs = {
                "contact_id": contact_id,
                "status": "New"
            }
            
            if email_date:
                note_kwargs["date"] = email_date
            
            # First note: upload via multipart and extract URL
            if idx == 0 and file_content:
                files_payload = [("files", (filename, file_content, "message/rfc822"))]
                note_kwargs["files"] = files_payload
                
                # Call log_activity and capture response to extract URL
                success, response_data = self.crm.log_activity_with_response(activity_text, **note_kwargs)
                
                # Extract attachment URL from response
                if success and response_data and response_data.get("data"):
                    attachments = response_data["data"].get("attachments", [])
                    if len(attachments) > 0:
                        eml_attachment_url = attachments[0].get("src")
            
            # Subsequent notes: reuse URL
            elif eml_attachment_url:
                note_kwargs["attachments"] = [{
                    "url": eml_attachment_url,
                    "title": filename,
                    "type": "message/rfc822"
                }]
                self.crm.log_activity(activity_text, **note_kwargs)
            else:
                # Fallback if no URL available
                self.crm.log_activity(activity_text, **note_kwargs)
        
        # Optional: Create company-level note if primary company exists
        if primary_company_id and analysis and eml_attachment_url:
            company_note = f"📧 **Email Activity**\n\nSubject: {headers.get('Subject')}\n"
            company_note += f"Date: {email_date or 'Unknown'}\n\n"
            company_note += f"Participants: {len(all_contact_ids)} contacts\n\n"
            company_note += f"{analysis.summary}\n\n"
            company_note += "[Original EML file attached below]"
            
            company_kwargs = {
                "activity_type": "company_note",
                "company_id": primary_company_id,
                "attachments": [{
                    "url": eml_attachment_url,
                    "title": filename,
                    "type": "message/rfc822"
                }]
            }
            
            if email_date:
                company_kwargs["date"] = email_date
            
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



def main():
    """Entry point for uvx/pip installation."""
    import argparse
    import sys

    # Set up basic logging before anything else
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Load environment variables (current directory .env find-up)
    load_dotenv()
    # Also look for .env in the same directory as the script for dev convenience
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

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
    parser.add_argument("--show-filter-stats", action="store_true", help="Show email filtering statistics after processing")
    
    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # If custom env file is provided, load it now (overwriting existing env vars if needed)
    if args.env_file:
        if os.path.exists(args.env_file):
            load_dotenv(args.env_file, override=True)
        else:
            logger.warning(f"Specified --env-file not found: {args.env_file}")

    # Priority: Flag > EnvVar > Default
    final_api_key = args.api_key or os.environ.get("CRM_API_KEY")
    final_base_url = args.base_url or os.environ.get("CRM_API_BASE_URL")
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
        
        # Resolve target files
        input_path = args.eml_path
        target_files = []
        
        if os.path.isfile(input_path):
            try:
                if os.path.getsize(input_path) > 0:
                    target_files.append(input_path)
                else:
                    logger.error(f"Input file is empty: {input_path}")
                    sys.exit(1)
            except OSError as e:
                logger.error(f"Error accessing file {input_path}: {e}")
                sys.exit(1)
        elif os.path.isdir(input_path):
            logger.info(f"Scanning directory for EML files: {input_path}")
            try:
                for root, _, files in os.walk(input_path):
                    for file in files:
                        if file.lower().endswith(".eml"):
                            file_path = os.path.join(root, file)
                            try:
                                if os.path.getsize(file_path) > 0:
                                    target_files.append(file_path)
                                else:
                                    logger.warning(f"Skipping empty EML file: {file}")
                            except OSError:
                                logger.warning(f"Skipping inaccessible file: {file}")
            except OSError as e:
                logger.error(f"Error scanning directory {input_path}: {e}")
                sys.exit(1)
            
            logger.info(f"Found {len(target_files)} valid EML files.")
        else:
            logger.error(f"Input path does not exist: {input_path}")
            sys.exit(1)

        if not target_files:
            logger.warning("No valid EML files found to process.")
            return

        # Batch Processing Loop
        stats = {"success": 0, "failed": 0, "total": len(target_files)}
        
        for file_path in tqdm(
            target_files, 
            desc="Processing emails",
            unit="email",
            colour="green",
            leave=True
        ):
            file_name = os.path.basename(file_path)
            try:
                processor.process(file_path, force=args.force)
                stats["success"] += 1
            except Exception as e:
                tqdm.write(f"ERROR: Failed to process {file_name}: {e}")
                stats["failed"] += 1
        
        # Summary Report
        logger.info("--- Processing Summary ---")
        logger.info(f"Total Files: {stats['total']}")
        logger.info(f"Successfully Processed: {stats['success']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info("--------------------------")

        # Show filter statistics if requested
        if args.show_filter_stats:
            try:
                from eml.filters.logging import print_suppression_report
                print_suppression_report(persistence)
            except ImportError:
                from filters.logging import print_suppression_report
                print_suppression_report(persistence)

    except Exception as e:
        logger.critical(f"Fatal error during processing: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
