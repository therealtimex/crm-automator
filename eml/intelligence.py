import os
import logging
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
import instructor
import openai

logger = logging.getLogger(__name__)

# LLM defaults
DEFAULT_MODEL = "qwen/qwen3-4b-2507"

# --- Models ---
class Contact(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: List[Dict[str, str]]
    company_id: Optional[int] = None
    title: Optional[str] = None
    background: Optional[str] = None
    linkedin_url: Optional[str] = None
    status: Optional[str] = None

class CompanyDetails(BaseModel):
    name: str
    sector: Optional[str] = None
    size: Optional[int] = None
    revenue: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    stateAbbr: Optional[str] = None
    zipcode: Optional[str] = None
    country: Optional[str] = None
    phone_number: Optional[str] = None
    tax_identifier: Optional[str] = None

class ExtractedTask(BaseModel):
    description: str
    due_date: Optional[str] = Field(description="ISO format date grounded by document context")
    priority: str = Field(description="High, Medium, or Low")

class DealInfo(BaseModel):
    name: str = Field(description="Descriptive name for the deal")
    amount: Optional[float] = Field(description="Estimated deal value if mentioned")
    stage: str = Field(description="CRM stage: discovery, proposal, negotiation, etc.")
    description: Optional[str] = Field(None, description="Detailed description of the deal opportunity")
    category: Optional[str] = None

class SenderInfo(BaseModel):
    phone: Optional[str] = None
    title: Optional[str] = Field(None, description="Job title or role")
    company: Optional[str] = None
    background: Optional[str] = Field(None, description="A brief biography or historical context about the contact")
    linkedin_url: Optional[str] = None
    gender: Optional[str] = None

class AnalysisResult(BaseModel):
    summary: str = Field(description="A brief summary of the email or text content")
    sentiment: str = Field(description="The emotional tone: Positive, Neutral, or Negative")
    intent: str = Field(description="The primary goal: Demo, Support, Sales, or Other")
    sender_info: SenderInfo = Field(description="Detailed information about the person who sent or is the focus of the text")
    company_details: Optional[CompanyDetails] = Field(None, description="Structured details about the company mentioned, especially if it's the sender's company")
    company_search_query: Optional[str] = Field(None, description="A focused Google/Bing search query to find more info if company details are sparse in the text")
    suggested_tasks: List[ExtractedTask] = Field(description="Actionable items or tasks derived from the content, grounded to the context date")
    deal_info: Optional[DealInfo] = Field(None, description="Information about a potential sales opportunity, extracted if the intent is Sales or Demo")

class IntelligenceLayer:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("LLM_API_KEY")
        self.base_url = base_url or os.environ.get("LLM_BASE_URL")
        self.model = model or os.environ.get("LLM_MODEL") or DEFAULT_MODEL
        
        if not self.base_url:
            logger.warning("LLM_BASE_URL is not set. Intelligence functions may fail.")

        self.client = instructor.from_openai(
            openai.OpenAI(api_key=self.api_key, base_url=self.base_url),
            mode=instructor.Mode.MD_JSON
        )

    def analyze_text(self, text: str, context_date: str = "Unknown") -> Optional[AnalysisResult]:
        logger.info(f"Analyzing content with context date: {context_date}")
        if not self.base_url:
             logger.error("Cannot analyze text: LLM_BASE_URL is not set")
             return None

        # Smart Cleaning Pipeline (Markdown-like & Noise Reduction)
        cleaned_text = self._smart_clean(text)
        
        system_prompt = f"Extract CRM structured data from the provided text. Context Date is {context_date}."
        
        try:
            return self.client.chat.completions.create(
                model=self.model,
                response_model=AnalysisResult,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": cleaned_text}
                ],
            )
        except Exception as e:
            logger.error(f"LLM Analysis Error: {e}")
            return None

    def _smart_clean(self, text: str, max_chars: int = 12000) -> str:
        """Cleans and compresses text for LLM ingestion."""
        import re
        
        # 0. Convert HTML to Markdown if it looks like HTML
        if "<" in text and ">" in text:
            try:
                from markdownify import markdownify as md
                text = md(text, strip=['script', 'style', 'img'])
            except ImportError:
                logger.warning("markdownify not installed, skipping HTML-to-Markdown conversion.")
            except Exception as e:
                logger.warning(f"Markdown conversion error: {e}")

        # 1. Remove obvious noise (Unsubscribe, View in Browser, etc.)
        noise_patterns = [
            r"Unsubscribe.*?\n",
            r"View in browser.*?\n",
            r"Privacy Policy.*?\n",
            r"Terms of Service.*?\n",
            r"© \d{4}.*?\n",
            r"Click here to.*?\n",
            r"\[.*?\]\(http.*?\)", # Remove inline markdown links if they add too much noise
        ]
        for pattern in noise_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # 2. Collapse whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        # 3. Fallback Truncation (Keep start and end if too long)
        if len(text) > max_chars:
            logger.warning(f"Text too long ({len(text)} chars). Truncating for safe processing.")
            # Keep first 70% and last 30% roughly
            lead = int(max_chars * 0.7)
            tail = max_chars - lead
            text = text[:lead] + "\n\n[... content truncated due to length ...]\n\n" + text[-tail:]
            
        return text.strip()

    def web_search_company(self, query: str) -> Optional[CompanyDetails]:
        logger.info(f"Performing web search for: {query}")
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
                if results:
                    combined_text = "\n".join([r['body'] for r in results])
                    system_prompt = "Parse the following search results into a structured CompanyDetails object."
                    return self.client.chat.completions.create(
                        model=self.model,
                        response_model=CompanyDetails,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": combined_text}
                        ]
                    )
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
        return None
