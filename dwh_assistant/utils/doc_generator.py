import json
import logging
import streamlit as st
from datetime import date
from typing import Dict, Any, List
from dwh_assistant.backend.executor import call_cortex_with_continuation

logger = logging.getLogger(__name__)

PROPOSAL_SECTIONS = [
    "1. Executive Summary",
    "2. Business Challenges & Opportunity",
    "3. Proposed Solution Overview",
    "4. Scope of Work",
    "5. Solution Deliverables",
    "6. Project Phases & Milestones",
    "7. Proposed Team Structure",
    "8. Indicative Timeline",
    "9. Investment Summary",
    "10. Risk Register & Mitigation Plan",
    "11. Success Metrics & KPIs",
    "12. Post-Go-Live Support & Maintenance",
    "13. Commercial Terms & Conditions",
    "14. Why Our Practice",
    "15. Conclusion & Call to Action"
]

TECHNICAL_SECTIONS = [
    "1. Executive Summary",
    "2. Business Requirements Summary",
    "3. Solution Architecture Overview",
    "4. Current State vs. Future State",
    "5. Detailed Architecture Design",
    "6. Data Model Design",
    "7. Source-to-Target Mapping",
    "8. ETL/ELT Framework Design",
    "9. Snowflake Object Design",
    "10. Security & Governance Framework",
    "11. Deployment & Release Strategy",
    "12. Testing Strategy",
    "13. Observability & Support Model",
    "14. Risk & Issue Register",
    "15. Assumptions & Dependencies",
    "16. Future Enhancements Roadmap"
]

def build_chunk_prompt(doc_type: str, context_str: str, chunk_sections: List[str]) -> str:
    sections_str = "\n".join(f"- {s}" for s in chunk_sections)
    
    if doc_type == "proposal":
        return f"""
You are a Principal Solution Architect and Enterprise Data Practice Lead at a Tier-1 consulting firm.
Your assignment: produce a CLIENT-READY Proposal Document for a Snowflake Data Warehouse.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WRITING STANDARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Executive-level English.
• Quantify where possible.
• For tables, headers must be arrays of strings, and rows must be arrays of string arrays.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — STRICT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON object containing a "sections" array. No markdown code fences.

Schema:
{{
  "sections": [
    {{
      "heading": "<section_heading>",
      "type": "text" | "table",
      "content": "...",
      "headers": [],
      "rows": []
    }}
  ]
}}

Generate ONLY the following sections in this exact order:
{sections_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{context_str}
"""
    else:
        return f"""
You are a Principal Snowflake Data Architect at a Tier-1 consulting firm.
Your assignment: produce a COMPREHENSIVE Technical Solution Document.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WRITING STANDARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Technical precision over prose.
• Populate tables with real values extracted from the provided context.
• For tables, headers must be arrays of strings, and rows must be arrays of string arrays.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — STRICT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON object containing a "sections" array. No markdown code fences.

Schema:
{{
  "sections": [
    {{
      "heading": "<section_heading>",
      "type": "text" | "table",
      "content": "...",
      "headers": [],
      "rows": []
    }}
  ]
}}

Generate ONLY the following sections in this exact order:
{sections_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{context_str}
"""

def generate_document_chunked(session, doc_type: str, context_str: str, model: str) -> Dict[str, Any]:
    sections_list = PROPOSAL_SECTIONS if doc_type == "proposal" else TECHNICAL_SECTIONS
    title = "Data Warehouse Modernisation Proposal" if doc_type == "proposal" else "Technical Solution Design Document"
    task_type = "proposal_gen" if doc_type == "proposal" else "tech_doc_gen"
    
    today = date.today().strftime("%B %d, %Y")
    
    final_doc = {
        "document_metadata": {
            "title": title,
            "client": "Client", 
            "version": "1.0",
            "date": today
        },
        "sections": []
    }
    
    chunk_size = 2
    progress_bar = st.progress(0)
    
    total_chunks = (len(sections_list) + chunk_size - 1) // chunk_size
    
    for i in range(0, len(sections_list), chunk_size):
        chunk = sections_list[i:i+chunk_size]
        prompt = build_chunk_prompt(doc_type, context_str, chunk)
        
        chunk_idx = i // chunk_size
        progress_bar.progress((chunk_idx) / total_chunks)
        
        try:
            res = call_cortex_with_continuation(session, prompt, task_type, model=model)
            if res.get("success"):
                output_val = res.get("output", {})
                
                # Retrieve parsed JSON
                if isinstance(output_val, dict) and "sections" in output_val:
                    parsed_sections = output_val["sections"]
                else:
                    # Try to parse raw if extraction missed the sections key
                    raw_str = res.get("raw", "")
                    try:
                        import re
                        raw_str = re.sub(r'```json\s*', '', raw_str).replace('```', '')
                        parsed = json.loads(raw_str)
                        parsed_sections = parsed.get("sections", [])
                    except:
                        parsed_sections = []
                
                if not parsed_sections:
                    for c in chunk:
                        final_doc["sections"].append({
                            "heading": c,
                            "type": "text",
                            "content": "_JSON parse failed. Please regenerate._"
                        })
                else:
                    final_doc["sections"].extend(parsed_sections)
            else:
                for c in chunk:
                    final_doc["sections"].append({
                        "heading": c,
                        "type": "text",
                        "content": "_Cortex generation error. Please regenerate._"
                    })
        except Exception as e:
            logger.error(f"Chunk failed: {e}")
            for c in chunk:
                final_doc["sections"].append({
                    "heading": c,
                    "type": "text",
                    "content": f"_Chunk failed: {str(e)}_"
                })
                
    progress_bar.empty()
    return final_doc
