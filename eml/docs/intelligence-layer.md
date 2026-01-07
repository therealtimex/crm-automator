# Intelligence Layer Guide

The Intelligence Layer is the "brain" of CRM Automator. It uses Large Language Models (LLMs) to turn unstructured email text into structured, actionable CRM data.

## Capabilities

1.  **Schema Extraction**: Converts free text into Pydantic models (`AnalysisResult`, `CompanyDetails`, `ParticipantInfo`).
2.  **Geographic Grounding**: Detects location context to distinguish between entities with similar names (e.g., "Savills Poland" vs "Savills Vietnam").
3.  **Company Enrichment**: actively searches the web to fill in missing company details (Sector, Revenue, Headcount).
4.  **Date Grounding**: Converts relative dates ("next Friday") into ISO-8601 timestamps based on the email's sent date.

## How Extraction Works

The system uses [instructor](https://github.com/jxnl/instructor) to force the LLM to output valid JSON matching our Pydantic schemas.

### Core Schema: `AnalysisResult`

| Field | Description | Source |
|-------|-------------|--------|
| `summary` | 1-2 sentence executive summary | Generated |
| `sentiment` | Positive, Neutral, Negative | Sentiment Analysis |
| `intent` | Sales, Demo, Support, Other | Intent Classification |
| `primary_contact` | The main person of interest (customer/lead) | Extracted from From/To/Signature |
| `company_details` | Structured company profile | Enriched via Search/Scraping |
| `suggested_tasks` | Action items (e.g., "Follow up on invoice") | Derived from content |
| `deal_info` | Opportunity details (Amount, Stage) | Extracted if Intent=Sales |

## Geographic Grounding

To prevent "hallucinations" where the LLM conflates entities (e.g., searching for "City Garden" and finding a cafe in London instead of a real estate project in Vietnam), we implement **Geographic Grounding**.

### Logic Flow
1.  **Context Detection**: The LLM scans the email for:
    *   **Currency Symbols**: `₫`, `VND` -> Vietnam; `£` -> UK; `€` -> Europe.
    *   **Phone Codes**: `+84` -> Vietnam; `+1` -> USA.
    *   **Address Footers**: Physical addresses in signatures.
2.  **Search Query Injection**: When generating `company_search_query`, the LLM is instructed to append these hints (e.g., "Savills Property Management **Vietnam**").
3.  **Validation**: Extracted addresses in `CompanyDetails` are checked against these clues.

### Tuning for Localization
If you operate in a specific region, you can further enforce this by updating the System Prompt in `eml/intelligence.py` or lowering `LLM_TEMPERATURE` to `0.0` to reduce "creative" guessing.

## Company Enrichment

The enrichment pipeline runs automatically when company details are sparse.

### Enrichment Cascade

1.  **Domain Extraction**:
    *   Input: "Contact us at support@**acme-corp.com**"
    *   Action: Identifies `acme-corp.com`.
2.  **Website Scraping (Priority 1)**:
    *   Tool: `crawl4ai`
    *   Action: Visits `https://acme-corp.com`, `/about`, and `/contact`.
    *   Result: High-fidelity data (Mission statement, exact headcount, leadership team).
3.  **Search Providers (Priority 2)**:
    *   Trigger: If scraping fails or no domain is found.
    *   Tools: `DuckDuckGo` (Free), `Serper` (Paid), `SerpAPI` (Paid).
    *   Action: Searches for the company name + location hints. Parses snippets into JSON.

### Configuration

```bash
# Prioritize free search
SEARCH_PROVIDERS=duckduckgo

# Prioritize high-quality paid search
SEARCH_PROVIDERS=serper,serpapi
SERPER_API_KEY=sk-...
```

## Tuning LLM Parameters

Different LLMs require different settings for optimal extraction.

### `LLM_MAX_TOKENS`
*   **Default**: `4096`
*   **Purpose**: Controls the maximum length of the generated JSON.
*   **Adjustment**:
    *   **Increase (e.g., 8192)** for local models (Qwen, Llama 3) that are "chatty" or output deep reasoning chains before the JSON.
    *   **Decrease (e.g., 1000)** for expensive models (GPT-4) to prevent runaway costs, though strict schemas usually limit this automatically.

### `LLM_TEMPERATURE`
*   **Default**: `0.1`
*   **Purpose**: Controls randomness.
*   **Adjustment**:
    *   **Keep Low (0.0 - 0.2)**: Essential for **Data Extraction**. You want the *facts*, not creative writing. High temperature leads to schema validation failures.
    *   **Increase (0.5+)**: Only for **Summarization** if you want more "human-like" prose, but risky for the structured fields.

## Troubleshooting

### "Failed to parse LLM response"
*   **Cause**: Model output was truncated or contained conversational text ("Here is your JSON: ...").
*   **Fix**: Increase `LLM_MAX_TOKENS` or switch to a smarter model (`gpt-4o-mini`).

### "Hallucinated Company Info"
*   **Cause**: Model guessed details for a generic name (e.g., "Summit Inc").
*   **Fix**: Check if the email contains location clues. If not, the model is guessing. Lower `LLM_TEMPERATURE` to 0.

### "Enrichment Failed"
*   **Cause**: Website blocked scraping or Search API quota exceeded.
*   **Fix**: Rotate `SEARCH_PROVIDERS` or enable `SERPER_API_KEY`.
