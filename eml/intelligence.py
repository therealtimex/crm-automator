import os
import logging
from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field
from email.utils import parseaddr
import instructor
import openai

logger = logging.getLogger(__name__)

# LLM defaults
DEFAULT_MODEL = "qwen/qwen3-4b-2507"

# --- Models ---
class CompanyDetails(BaseModel):
    name: str
    sector: Optional[str] = None
    size: Optional[int] = None
    revenue_range: Optional[Literal['0-1M', '1M-10M', '10M-50M', '50M-100M', '100M+', 'unknown']] = Field(
        None, description="Revenue bracket aligned with CRM schema"
    )
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
    
    # Alignment with CRM api-v1-companies
    lifecycle_stage: Optional[Literal['prospect', 'customer', 'churned', 'lost', 'archived']] = None
    company_type: Optional[Literal['customer', 'prospect', 'partner', 'vendor', 'competitor', 'internal']] = None
    industry: Optional[Literal['SaaS', 'E-commerce', 'Healthcare', 'Fintech', 'Manufacturing', 'Consulting', 'Real Estate', 'Education']] = None
    employee_count: Optional[int] = None
    founded_year: Optional[int] = Field(
        None, ge=1800, le=2100, description="Year the company was founded (1800-2100)"
    )
    social_profiles: Optional[Dict[str, str]] = Field(default_factory=dict, description="Map of network type to URL (e.g., twitter: ...)")
    logo_url: Optional[str] = None
    context_links: Optional[Dict[str, str]] = None
    external_heartbeat_status: Optional[Literal['healthy', 'risky', 'dead', 'unknown']] = None
    internal_heartbeat_status: Optional[Literal['engaged', 'quiet', 'at_risk', 'unresponsive']] = None
    email: Optional[str] = None

class ExtractedTask(BaseModel):
    description: str
    due_date: Optional[str] = Field(description="ISO format date grounded by document context")
    priority: str = Field(description="High, Medium, or Low")
    status: str = Field(default="todo", description="Task status: todo, in_progress, done")

class DealInfo(BaseModel):
    name: str = Field(description="Descriptive name for the deal")
    amount: Optional[float] = Field(description="Estimated deal value if mentioned")
    stage: str = Field(description="CRM stage: discovery, proposal, negotiation, etc.")
    description: Optional[str] = Field(None, description="Detailed description of the deal opportunity")
    category: Optional[str] = None

class ParticipantInfo(BaseModel):
    email: Optional[str] = Field(None, description="The email address this info belongs to")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = Field(None, description="Job title or role")
    company: Optional[str] = None
    background: Optional[str] = Field(None, description="A brief biography or historical context about the contact")
    linkedin_url: Optional[str] = None
    gender: Optional[str] = None
    status: Optional[Literal['qualified', 'unqualified', 'duplicate', 'spam', 'test']] = Field(None, description="Qualification status")

class AnalysisResult(BaseModel):
    summary: str = Field(description="A brief summary of the email or text content")
    sentiment: str = Field(description="The emotional tone: Positive, Neutral, or Negative")
    intent: str = Field(description="The primary goal: Demo, Support, Sales, or Other")
    language: str = Field(default="English", description="The primary language of the content (e.g., English, Vietnamese)")
    primary_contact_email: Optional[str] = Field(None, description="The email address of the person who is the main focus of this activity (e.g., the customer)")
    primary_contact: ParticipantInfo = Field(description="Primary person of interest (customer, lead, or main subject - NOT necessarily the email sender)")
    additional_contacts: List[ParticipantInfo] = Field(default_factory=list, description="Other people mentioned or participating in the email thread")
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

    def analyze_text(self, text: str, context_date: str = "Unknown", metadata: Optional[Dict] = None) -> Optional[AnalysisResult]:
        logger.info(f"Analyzing content with context date: {context_date}")
        if not self.base_url:
             logger.error("Cannot analyze text: LLM_BASE_URL is not set")
             return None

        # Smart Cleaning Pipeline (Markdown-like & Noise Reduction)
        # We only clean the main text/body, not the structured metadata
        cleaned_body = self._smart_clean(text)
        
        full_prompt_text = ""
        if metadata:
            full_prompt_text += "--- METADATA ---\n"
            for k, v in metadata.items():
                full_prompt_text += f"{k}: {v}\n"
            full_prompt_text += "\n--- CONTENT ---\n"
        
        full_prompt_text += cleaned_body

        system_prompt = (
            "You are a CRM Intelligence Agent. Extract structured data from the provided text.\n"
            f"Context Date: {context_date}\n\n"
            "Guidelines:\n"
            "1. Analyze metadata headers (From, To, Cc, Subject) to understand participants and topic.\n"
            "2. Extract first_name and last_name for ALL participants from email signatures, body text, and headers.\n"
            "3. Attachment filenames provide critical context (e.g., 'Invoice' -> billing, 'Deck' -> sales).\n"
            "4. Extract social media profiles (LinkedIn, Twitter/X) from signatures and content.\n"
            "5. Identify the primary person of interest (customer/lead) as 'primary_contact'.\n"
            "6. List all other participants in 'additional_contacts'.\n"
            "7. If multiple messages in a thread, focus on latest interaction for sentiment/intent."
        )
        
        try:
            return self.client.chat.completions.create(
                model=self.model,
                response_model=AnalysisResult,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt_text}
                ],
            )
        except Exception as e:
            logger.error(f"LLM Analysis Error: {e}")
            return None

    def _smart_clean(self, text: str, max_chars: int = 12000) -> str:
        """Cleans and compresses text for LLM ingestion."""
        import re
        
        # 0. Unwrap "Safe Links" (Proofpoint, Outlook, etc.)
        text = self.unwrap_safe_links(text)
        
        # 0.1 High-Accuracy Social Link Resolution (Resolve tracking links)
        text = self.resolve_social_links(text)

        # 1. Convert HTML to Markdown if it looks like HTML
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

    def unwrap_safe_links(self, text: str) -> str:
        """
        Detects and replaces 'safe' links (Proofpoint, Outlook Safelinks) 
        with their original decoded URLs.
        """
        import re
        from urllib.parse import unquote, parse_qs, urlparse

        def replace_match(match):
            full_url = match.group(0)
            try:
                parsed = urlparse(full_url)
                query = parse_qs(parsed.query)
                
                # Proofpoint (u) / Outlook (url)
                real_url = None
                if "proofpoint.com" in parsed.netloc and "u" in query:
                    real_url = query["u"][0]
                elif "outlook.com" in parsed.netloc and "url" in query:
                    real_url = query["url"][0]
                
                # Fallback: Google redirects, generic redirects often use 'q' or 'url'
                elif "google.com" in parsed.netloc and "url" in query:
                    real_url = query["url"][0]

                if real_url:
                    # Often these parameters are typically also valid URLs, but might be encoded 
                    # specifically. parse_qs does basic decoding, but verify.
                    # Fix recurring encodings if necessary (safelinks often doesn't double encode, but proofpoint might use special translation)
                    # For V2 proofpoint, 'u' is effectively the URL but '-' is replaced by '%' sometimes.
                    # However, standard unquote usually is sufficient for the query param value.
                    return unquote(real_url)
            except Exception:
                pass
            return full_url

        # Regex to capture http/s URLs that look like typical safe links
        # We catch broadly then filter in the callback
        safe_link_pattern = r'https?://[a-zA-Z0-9.-]+(?:\.proofpoint\.com|\.outlook\.com|\.google\.com)[^\s")\]]*'
        
        return re.sub(safe_link_pattern, replace_match, text)

    def resolve_social_links(self, text: str) -> str:
        """
        Parses HTML, finds links that look like social profiles but might be tracking URLs,
        and resolves them to their canonical targets via HTTP requests.
        """
        if not ("<" in text and ">" in text):
            return text
            
        try:
            from bs4 import BeautifulSoup
            import requests
            
            soup = BeautifulSoup(text, "html.parser")
            social_domains = ["linkedin", "twitter", "x.com", "facebook", "instagram"]
            
            # Find candidate links: Either their text or href contains social keywords
            # but they don't look like clean social URLs yet (e.g. they are tracking links)
            candidates = []
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                link_text = a.get_text().lower()
                
                # Check if this is likely a social link (by text content or title)
                is_social_context = any(d in link_text or d in a.get("title", "").lower() or d in a.get("alt", "").lower() for d in social_domains)
                
                # OR check if href contains a known tracking domain for social (generic check)
                # But safer to rely on context + href mismatch.
                
                # If it's a social context but the href is NOT a simple social URL, verify it
                if is_social_context:
                    # Skip if it's already a clean social link
                    if any(f"{d}.com" in href for d in social_domains):
                        continue
                    candidates.append(a)
            
            if not candidates:
                return text

            # Resolve candidates
            logger.info(f"Attempting to resolve {len(candidates)} potential social tracking links...")
            for a in candidates:
                try:
                    original_url = a["href"]
                    # Quick HEAD request to follow redirects
                    # Short timeout because we don't want to hang
                    resp = requests.head(original_url, allow_redirects=True, timeout=3.0)
                    final_url = resp.url
                    
                    if final_url != original_url:
                        logger.debug(f"Resolved social link: {original_url[:30]}... -> {final_url}")
                        a["href"] = final_url
                except Exception as e:
                    logger.warning(f"Failed to resolve social link {a['href'][:30]}...: {e}")
            
            return str(soup)
            
        except ImportError:
            return text
        except Exception as e:
            logger.warning(f"Error during social link resolution: {e}")
            return text

    def web_search_company(self, query: str) -> Optional[CompanyDetails]:
        """
        Multi-source company enrichment with priority:
        1. Website scraping (if domain detected in query)
        2. Multi-provider search (DuckDuckGo -> Serper -> SerpAPI)
        """
        logger.info(f"Enriching company data for: {query}")
        
        # Try to extract domain from query
        domain = self._extract_domain_from_query(query)
        
        # Priority 1: Scrape website if domain found
        if domain:
            scraped_data = self._scrape_website(domain)
            if scraped_data:
                return scraped_data
        
        # Priority 2: Fallback to search providers
        provider_order = os.environ.get("SEARCH_PROVIDERS", "duckduckgo,serper,serpapi").split(",")
        
        for provider in provider_order:
            provider = provider.strip().lower()
            try:
                results = self._search_with_provider(provider, query)
                if results:
                    return self._parse_search_results(results)
            except Exception as e:
                logger.warning(f"{provider} search failed: {e}, trying next provider...")
                continue
        
        logger.error(f"All enrichment methods failed for query: {query}")
        return None
    
    def _extract_domain_from_query(self, query: str) -> Optional[str]:
        """Extract domain from search query if present."""
        import re
        # Look for patterns like "care.org.vn" or "example.com"
        domain_pattern = r'\b([a-z0-9-]+\.)+[a-z]{2,}\b'
        matches = re.findall(domain_pattern, query.lower())
        return matches[0] if matches else None
    
    def _scrape_website(self, domain: str) -> Optional[CompanyDetails]:
        """
        Scrape company website using Crawl4AI for rich data extraction.
        Targets: homepage, /about, /contact pages.
        """
        try:
            import asyncio
            from crawl4ai import AsyncWebCrawler
            
            # Run async scraping in sync context
            return asyncio.run(self._async_scrape_website(domain))
        except ImportError:
            logger.warning("crawl4ai not installed. Run: pip install crawl4ai")
            return None
        except Exception as e:
            logger.warning(f"Website scraping failed for {domain}: {e}")
            return None
    
    async def _async_scrape_website(self, domain: str) -> Optional[CompanyDetails]:
        """Async website scraping with Crawl4AI."""
        from crawl4ai import AsyncWebCrawler
        
        urls_to_try = [
            f"https://{domain}",
            f"https://{domain}/about",
            f"https://{domain}/about-us",
            f"https://{domain}/contact",
        ]
        
        combined_content = []
        
        async with AsyncWebCrawler(verbose=False) as crawler:
            for url in urls_to_try:
                try:
                    result = await crawler.arun(
                        url=url,
                        word_count_threshold=10,
                        bypass_cache=True,
                        timeout=8000  # 8 seconds
                    )
                    
                    if result.success and result.markdown:
                        # Limit content per page to avoid overwhelming LLM
                        content = result.markdown[:2000]
                        combined_content.append(f"### {url}\n{content}")
                        
                        # Stop after collecting enough data
                        if len(combined_content) >= 2:
                            break
                except Exception as e:
                    logger.debug(f"Failed to scrape {url}: {e}")
                    continue
        
        if not combined_content:
            return None
        
        # Parse scraped content with LLM
        full_text = "\n\n".join(combined_content)
        system_prompt = "Extract structured company information from the following website content."
        
        try:
            return self.client.chat.completions.create(
                model=self.model,
                response_model=CompanyDetails,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_text}
                ]
            )
        except Exception as e:
            logger.error(f"LLM parsing error for scraped content: {e}")
            return None
    
    def _search_with_provider(self, provider: str, query: str, max_results: int = 3) -> Optional[List[Dict]]:
        """Execute search with specified provider."""
        
        if provider == "duckduckgo":
            return self._search_duckduckgo(query, max_results)
        elif provider == "serper":
            return self._search_serper(query, max_results)
        elif provider == "serpapi":
            return self._search_serpapi(query, max_results)
        else:
            logger.warning(f"Unknown search provider: {provider}")
            return None
    
    def _search_duckduckgo(self, query: str, max_results: int) -> Optional[List[Dict]]:
        """DuckDuckGo search (free, no API key needed)."""
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return [{"title": r.get("title", ""), "snippet": r.get("body", "")} for r in results]
        except ImportError:
            logger.error("ddgs not installed. Run: pip install ddgs")
            return None
    
    def _search_serper(self, query: str, max_results: int) -> Optional[List[Dict]]:
        """Serper.dev search (paid, requires SERPER_API_KEY)."""
        api_key = os.environ.get("SERPER_API_KEY")
        if not api_key:
            logger.warning("SERPER_API_KEY not set, skipping Serper")
            return None
        
        try:
            import requests
            response = requests.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": max_results},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            organic = data.get("organic", [])
            return [{"title": r.get("title", ""), "snippet": r.get("snippet", "")} for r in organic[:max_results]]
        except Exception as e:
            logger.error(f"Serper API error: {e}")
            return None
    
    def _search_serpapi(self, query: str, max_results: int) -> Optional[List[Dict]]:
        """SerpAPI search (paid, requires SERPAPI_KEY)."""
        api_key = os.environ.get("SERPAPI_KEY") or os.environ.get("SERPAPI_API_KEY")
        if not api_key:
            logger.warning("SERPAPI_KEY not set, skipping SerpAPI")
            return None
        
        try:
            import requests
            response = requests.get(
                "https://serpapi.com/search",
                params={"q": query, "api_key": api_key, "num": max_results, "engine": "google"},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            organic = data.get("organic_results", [])
            return [{"title": r.get("title", ""), "snippet": r.get("snippet", "")} for r in organic[:max_results]]
        except Exception as e:
            logger.error(f"SerpAPI error: {e}")
            return None
    
    def _parse_search_results(self, results: List[Dict]) -> Optional[CompanyDetails]:
        """Parse search results into CompanyDetails using LLM."""
        if not results:
            logger.warning("No search results to parse")
            return None
        
        logger.debug(f"Parsing {len(results)} search results")
        combined_text = "\n\n".join([f"**{r['title']}**\n{r['snippet']}" for r in results])
        system_prompt = "Parse the following search results into a structured CompanyDetails object."
        
        try:
            return self.client.chat.completions.create(
                model=self.model,
                response_model=CompanyDetails,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": combined_text}
                ]
            )
        except Exception as e:
            logger.error(f"LLM parsing error for search results: {e}")
            logger.debug(f"Search results that failed to parse: {combined_text[:200]}...")
            return None
    def hydrate_from_eesa(self, eesa_data: Dict, metadata: Optional[Dict] = None) -> Optional[AnalysisResult]:
        """
        Creates an AnalysisResult from EESA pre-processed metadata, skipping the LLM call.
        """
        classification = eesa_data.get("classification", {})
        confidence = classification.get("confidence", 0.0)
        logger.info(f"Hydrating AnalysisResult from EESA metadata (confidence: {confidence:.2f})")
        
        extraction = eesa_data.get("extraction", {})
        
        # 1. Map Intent
        category = classification.get("category", "other").lower()
        intent_map = {
            "sales": "Sales",
            "support": "Support",
            "newsletter": "Other",
            "transactional": "Other",
            "demo": "Demo"
        }
        intent = intent_map.get(category, "Other")
        
        # 2. Map Summary
        # EESA summary might use placeholders, we take it as is
        summary = extraction.get("summary", "No summary provided by EESA.")
        
        # 3. Tasks
        tasks = []
        for action in extraction.get("action_items", []):
            tasks.append(ExtractedTask(
                description=action,
                due_date=None,  # EESA doesn't provide due dates
                priority="Medium",  # Default
                status="todo"
            ))
            
        # 4. Sender Info
        # Extract just the email address from the From header
        sender_email = None
        if metadata:
            sender_name, sender_email = parseaddr(metadata.get("From", ""))
            
        # Try to find a name from EESA entities that matches? 
        # For MVP we just assume the first person if any is relevant, or leave blank.
        sender_info = ParticipantInfo(
            email=sender_email, 
            company=None
        )
        
        # 5. Company Details
        company_details = None
        company_search_query = None
        orgs = extraction.get("entities", {}).get("organizations", [])
        if orgs and len(orgs) > 0:
            company_details = CompanyDetails(name=orgs[0])
            # Trigger web enrichment if we only have the name
            company_search_query = orgs[0]
            
        # 6. Deal Info
        deal_info = None
        monetary = extraction.get("entities", {}).get("monetary_values", [])
        if intent in ["Sales", "Demo"]:
            deal_name = f"{orgs[0]} - {intent}" if orgs else f"{intent} Opportunity"
            amount = 0.0
            # Very basic string to float cleanup
            if monetary:
                try:
                    val = monetary[0].replace("$", "").replace(",", "")
                    amount = float(val)
                except:
                    pass
            
            deal_info = DealInfo(
                name=deal_name,
                amount=amount,
                stage="Discovery"
            )
            
        return AnalysisResult(
            summary=summary,
            sentiment="Neutral", # specific default
            intent=intent,
            primary_contact_email=sender_email,
            primary_contact=sender_info,
            additional_contacts=[],
            company_details=company_details,
            company_search_query=company_search_query,
            suggested_tasks=tasks,
            deal_info=deal_info
        )
