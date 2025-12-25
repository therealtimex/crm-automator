# Example: Syncing a Meeting Transcript

This example shows how an AI agent uses the toolkit to process a raw transcript into a CRM record.

## 1. Raw Input
```text
Met with Sarah Connor today. She's the Technical Lead at Cyberdyne Systems (cyberdyne.ai).
They are looking for a cloud security solution. Budget is around $50k.
Follow up next Monday to schedule a deep dive.
Sarah's mobile is +1-555-0199.
```

## 2. Agentic Workflow (Internal)
1.  **Analyze**: `IntelligenceLayer.analyze_text()` extracts:
    - **Intent**: Sales
    - **Company**: Cyberdyne Systems (Website: cyberdyne.ai)
    - **Contact**: Sarah Connor (Title: Technical Lead, Phone: +1-555-0199)
    - **Task**: Follow up next Monday for deep dive.
2.  **Enrich**: (Optional) Tool triggers a web search for Cyberdyne's revenue/size if not found.
3.  **Client Sync**: `RealTimeXClient` performs idempotent upserts for the company and contact, then logs the activity and creates the task.

## 3. CLI Command
```bash
python3 eml/agent_demo.py
```
*(Ensure your `.env` is configured or pass `--api-key`)*
