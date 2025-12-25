import os
import logging
from dotenv import load_dotenv
from crm_client import RealTimeXClient
from intelligence import IntelligenceLayer, AnalysisResult

# --- Environment Configuration (Default loading) ---
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# --- Production Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main(api_key: str, base_url: str, llm_url: Optional[str] = None):
    # 1. Initialize tools
    crm = RealTimeXClient(api_key, base_url)
    intelligence = IntelligenceLayer(base_url=llm_url)

    # 2. Suppose an agent receives generic text
    raw_text = """
    Met with Sarah Connor today. She's the Technical Lead at Cyberdyne Systems (cyberdyne.ai).
    They are looking for a cloud security solution. Budget is around $50k.
    Follow up next Monday to schedule a deep dive.
    Sarah's mobile is +1-555-0199.
    """

    logger.info("--- Agent Ingesting Generic Text ---")
    
    # 3. Step 1: Analyze intelligence (Resource agnostic)
    analysis = intelligence.analyze_text(raw_text, context_date="2025-12-24")
    if not analysis:
        logger.error("Analysis failed.")
        return

    logger.info(f"Summary: {analysis.summary}")
    logger.info(f"Intent: {analysis.intent}")

    # 4. Step 2: Use CRM tools (Composition)
    # Search/Upsert Company
    domain = "cyberdyne.ai"
    company_name = "Cyberdyne Systems"
    if analysis.company_details:
        company_name = analysis.company_details.name or company_name
    
    company_id = crm.upsert_company(company_name, website=domain)
    
    # Upsert Contact
    contact_kwargs = {}
    if analysis.sender_info.phone:
        contact_kwargs["phone_jsonb"] = [{"number": analysis.sender_info.phone, "type": "Work"}]
    if analysis.sender_info.title:
        contact_kwargs["title"] = analysis.sender_info.title
    if analysis.sender_info.gender:
        contact_kwargs["gender"] = analysis.sender_info.gender

    contact_id = crm.upsert_contact(
        "sarah.connor@cyberdyne.ai", 
        first_name="Sarah", 
        last_name="Connor", 
        company_id=company_id,
        **contact_kwargs
    )

    if contact_id:
        logger.info(f"Successfully synced contact ID: {contact_id}")
        crm.log_activity(contact_id, raw_text)
        
        for task in analysis.suggested_tasks:
            crm.create_task(contact_id, task.description, task.due_date, task.priority)

    logger.info("--- Ingestion Complete ---")

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Demonstrate agentic CRM ingestion from generic text.")
    parser.add_argument("--api-key", help="RealTimeX API Key (overrides CRM_API_KEY env)")
    parser.add_argument("--base-url", help="RealTimeX Base URL (overrides CRM_API_BASE_URL env)")
    parser.add_argument("--env-file", help="Path to custom .env file")
    parser.add_argument("--llm-url", help="LLM Base URL (overrides LLM_BASE_URL env)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging (DEBUG level)")
    
    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load custom env before reading other fallbacks
    if args.env_file:
        if os.path.exists(args.env_file):
            load_dotenv(args.env_file, override=True)
        else:
            logger.warning(f"Specified --env-file not found: {args.env_file}")
    
    # Priority: Flag > EnvVar > Default
    env_api_key = os.environ.get("CRM_API_KEY")
    env_base_url = os.environ.get("CRM_API_BASE_URL", "https://xydvyhnspkzcsocewhuy.supabase.co/functions/v1")
    
    final_api_key = args.api_key or env_api_key
    final_base_url = args.base_url or env_base_url
    
    if args.llm_url:
        os.environ["LLM_BASE_URL"] = args.llm_url

    if not final_api_key:
        logger.error("CRM_API_KEY not set via environment variable or --api-key flag. Exiting.")
        sys.exit(1)
    
    main(final_api_key, final_base_url, args.llm_url)
