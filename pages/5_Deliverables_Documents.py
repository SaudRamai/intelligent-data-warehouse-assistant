import streamlit as st
import sys
import os
import json
from pathlib import Path

root_path = str(Path(__file__).parent.parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

from dwh_assistant.backend.snowflake import ensure_session, get_all_projects, load_project_by_id
from dwh_assistant.backend.executor import call_cortex
from dwh_assistant.utils.ui import apply_premium_style, render_page_header, render_ai_sidebar, init_session_state
from dwh_assistant.utils.doc_export import ConsultingPDFExporter, ConsultingDOCXExporter
from dwh_assistant.utils.doc_generator import generate_document_chunked

st.set_page_config(page_title="Deliverables Documents | AI DWH", layout="wide")
init_session_state()
apply_premium_style()

def render_document_ui(doc_data: dict):
    """Renders the deeply structured document JSON in Streamlit natively."""
    meta = doc_data.get("document_metadata", {})
    st.markdown(f"**Title:** {meta.get('title', 'Document')} | **Version:** {meta.get('version', '1.0')} | **Date:** {meta.get('date', '')}")
    st.divider()
    
    sections = doc_data.get("sections", [])
    for sec in sections:
        heading = sec.get("heading", "")
        if heading:
            st.markdown(f"### {heading}")
            
        if sec.get("type") == "table":
            headers = sec.get("headers", [])
            rows = sec.get("rows", [])
            if headers or rows:
                import pandas as pd
                df = pd.DataFrame(rows, columns=headers if headers else None)
                st.dataframe(df, use_container_width=True)
        else:
            st.markdown(sec.get("content", ""))

def to_markdown_string(doc_data: dict) -> str:
    """Converts the structured JSON back into a flat markdown file for raw viewing/download."""
    lines = []
    meta = doc_data.get("document_metadata", {})
    lines.append(f"# {meta.get('title', 'Document')}")
    lines.append(f"**Client:** {meta.get('client', '')} | **Version:** {meta.get('version', '')}")
    lines.append("\n---\n")
    
    for sec in doc_data.get("sections", []):
        if sec.get("heading"):
            lines.append(f"## {sec.get('heading')}\n")
        
        if sec.get("type") == "table":
            headers = sec.get("headers", [])
            rows = sec.get("rows", [])
            if headers:
                lines.append("| " + " | ".join(map(str, headers)) + " |")
                lines.append("|" + "|".join(["---"] * len(headers)) + "|")
                for r in rows:
                    lines.append("| " + " | ".join(map(str, r)) + " |")
            lines.append("\n")
        else:
            lines.append(f"{sec.get('content', '')}\n\n")
            
    return "\n".join(lines)
        
from datetime import date

def build_bidding_prompt(doc_type: str, context_str: str) -> str:
    today = date.today().strftime("%B %d, %Y")

    if doc_type == "proposal":
        return f"""
You are a Principal Solution Architect and Enterprise Data Practice Lead at a Tier-1 consulting firm (McKinsey, Deloitte, Accenture, PwC calibre).

Your assignment: produce a CLIENT-READY, BOARD-PRESENTABLE Proposal Document for a Snowflake Data Warehouse engagement.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WRITING STANDARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Executive-level English. Decisive, specific, and authoritative — never vague or generic.
• Every section must reference specifics extracted from the provided context (architecture type, layer names, table counts, pipeline logic, roles, compliance items).
• No AI filler phrases ("This document aims to...", "We are pleased to present..."). Lead with impact.
• Use active voice. Quantify where possible (e.g., "reduce data latency from 4h to <15min").
• Budget and timeline figures must be internally consistent across sections.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — STRICT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON object. No markdown code fences. No preamble. No comments.

Schema:
{{
  "document_metadata": {{
    "title": "Data Warehouse Modernisation Proposal",
    "client": "<extract from context or 'Client'>",
    "version": "1.0",
    "date": "{today}"
  }},
  "sections": [
    {{
      "heading": "1. Executive Summary",
      "type": "text",
      "content": "Multi-paragraph text. Use **bold** for key terms. Use '- ' prefix for bullet points."
    }},
    {{
      "heading": "9. Investment Summary",
      "type": "table",
      "headers": ["Phase", "Workstream", "Effort (Days)", "Estimated Investment"],
      "rows": [["Phase 1 — Foundation", "Architecture & Infra Setup", "15", "$45,000"]]
    }}
  ]
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY SECTIONS — IN THIS ORDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Executive Summary
   One-page summary. Open with the client's core business problem, then articulate
   the proposed solution in 2-3 decisive sentences, key business outcomes (quantified),
   and the engagement value proposition. NO lists of section names.

2. Business Challenges & Opportunity
   Describe the current-state pain points (data silos, latency, governance gaps, manual
   processes) extracted from the requirements. Frame each as a business risk or lost
   opportunity, not just a technical issue. Use bullet format.

3. Proposed Solution Overview
   Describe the recommended architecture (type, paradigm, layer model) in business terms.
   Explain WHY this approach was selected over alternatives. Include a high-level data flow
   narrative (Source → Ingestion → Staging → Transformation → Serving → Consumption).

4. Scope of Work
   Use a table: rows = workstream, columns = In Scope / Out of Scope / Assumptions.
   Be explicit. Avoid scope ambiguity that leads to change orders.

5. Solution Deliverables
   Table: Deliverable | Type (Artifact/Service/Documentation) | Acceptance Criteria.
   Must map directly to the architecture outputs (DDL scripts, pipeline DAGs, governance
   playbook, runbooks, etc.).

6. Project Phases & Milestones
   Table: Phase | Key Activities | Deliverables | Duration | Exit Criteria.
   Minimum 4 phases (Discovery → Build → UAT → Hypercare).

7. Proposed Team Structure
   Table: Role | Responsibility | Allocation (%) | Location.
   Include Principal Architect, Senior Data Engineer, Data Modeler, QA/Test Lead,
   Project Manager, Client Counterpart.

8. Indicative Timeline
   Table: Week | Phase | Workstream | Owner | Status.
   Must align with phases in section 6. Realistically sized.

9. Investment Summary
   Table: Phase | Workstream | Effort (Person-Days) | Rate ($/day) | Estimated Cost.
   Include a subtotal per phase and a TOTAL investment row.
   Separate fixed-cost from variable/T&M items if applicable.

10. Risk Register & Mitigation Plan
    Table: Risk ID | Description | Probability | Impact | Mitigation | Owner.
    Include data, technical, people, and commercial risks. Minimum 6 risks.

11. Success Metrics & KPIs
    Table: KPI | Baseline | Target | Measurement Method | Review Cadence.
    Include pipeline reliability, data freshness, query performance, adoption rate.

12. Post-Go-Live Support & Maintenance
    Describe hypercare period, SLA tiers, support model (L1/L2/L3), knowledge transfer
    plan, and handover conditions.

13. Commercial Terms & Conditions
    Payment milestones (tied to deliverable acceptance), change request process,
    IP ownership, confidentiality, warranty period. Tabular format preferred.

14. Why Our Practice
    3-5 specific differentiators. Reference Snowflake-specific expertise, delivery
    methodology, accelerators, and relevant case pattern experience.
    Avoid generic claims. Specific tools, frameworks, and capabilities only.

15. Conclusion & Call to Action
    One paragraph. Restate the primary value proposition. Specify the clear next step
    (e.g., "We propose a 2-day Discovery Workshop commencing [date] to finalise scope").

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{context_str}
"""

    elif doc_type == "technical":
        return f"""
You are a Principal Snowflake Data Architect at a Tier-1 consulting firm.

Your assignment: produce a COMPREHENSIVE, IMPLEMENTATION-READY Technical Solution Document
that a senior data engineering team could use to build the solution without further clarification.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WRITING STANDARDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Technical precision over prose. Concise, unambiguous.
• Every design decision must include a rationale (e.g., "SCD Type 2 used for CUSTOMER_DIM
  to preserve historical segmentation for cohort analysis").
• Tables for structured data — never prose where a table is clearer.
• Populate tables with real values extracted from the provided architecture context
  (actual table names, column lists, task names, role names, compliance items).
• No placeholder text or lorem ipsum.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — STRICT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Return ONLY a valid JSON object. No markdown code fences. No preamble. No comments.

{{
  "document_metadata": {{
    "title": "Technical Solution Design Document",
    "client": "<extract from context or 'Client'>",
    "version": "1.0",
    "date": "{today}"
  }},
  "sections": [...]
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY SECTIONS — IN THIS ORDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Executive Summary
   2-3 paragraphs. Architecture type, modeling paradigm, layer model, key design decisions,
   and the primary technical risks being mitigated.

2. Business Requirements Summary
   Table: Requirement ID | Business Requirement | Technical Implication | Priority (MoSCoW).
   Derive from the provided context.

3. Solution Architecture Overview
   Describe the end-to-end architecture narrative. Cover: compute/storage separation rationale,
   multi-cluster vs single-cluster decision, warehouse sizing strategy, VPC/private link
   if applicable, and integration touch-points. Include layer model: Bronze/Silver/Gold
   or Staging/ODS/DWH/Mart with purpose of each.

4. Current State vs. Future State
   Table: Dimension | Current State | Future State | Delta/Improvement.
   Dimensions: Data Latency, Data Quality, Governance Maturity, Query Performance,
   Operational Overhead, Scalability, Cost Structure.

5. Detailed Architecture Design
   Sub-sections:
   5a. Infrastructure & Environment Strategy (DEV/QA/PROD, Snowflake account setup,
       Virtual Warehouse naming conventions, cost controls)
   5b. Connectivity & Data Sources (source systems, connection methods, network security)
   5c. Medallion Layer Design (purpose, SLA, retention policy per layer)

6. Data Model Design
   Table: Table Name | Layer | Model Type (Fact/Dim/Bridge/Staging) | Grain |
          Key Columns (top 5) | SCD Type (if dim) | Estimated Row Count.
   Populate from schema_modeling context. Include at least all tables present.

7. Source-to-Target Mapping
   Table: Source System | Source Object | Source Column | Target Table | Target Column |
          Transformation Rule | Data Type | Nullable.
   Use actual pipeline tasks from context for transformation rules.

8. ETL/ELT Framework Design
   8a. Pipeline Architecture: describe orchestration tool, task dependency model,
       error handling strategy, retry policy, and idempotency approach.
   8b. Task Inventory Table: Task Name | Source | Target | Load Type (Full/Incremental) |
       Frequency | SLA (mins) | Dependency.
   Populate from pipeline_design context.

9. Snowflake Object Design
   Table: Object Type | Object Name | Schema | Purpose | Owner Role | Notes.
   Cover: databases, schemas, stages, pipes, streams, tasks, dynamic tables, file formats.

10. Security & Governance Framework
    10a. Role Hierarchy: Role Name | Parent Role | Privilege Level | Assigned Objects.
    10b. Data Masking Policies: Policy Name | Column(s) | Masking Logic | Applied To Role.
    10c. Compliance Controls: Control | Framework (GDPR/HIPAA/SOC2) | Implementation | Owner.
    Populate from governance_security context.

11. Deployment & Release Strategy
    Table: Phase | Environment | Activities | Validation Gate | Rollback Procedure.
    Include CI/CD pipeline design, blue/green or canary deployment notes, and
    Terraform/Schemachange/Flyway usage if applicable.

12. Testing Strategy
    Table: Test Type | Scope | Tool/Method | Pass Criteria | Owner.
    Cover: unit tests, integration tests, data quality checks, UAT, performance/load,
    security penetration testing.

13. Observability & Support Model
    13a. Monitoring: Metric | Alert Threshold | Channel | Escalation Path.
    13b. SLA Definition: Tier | Criticality | Response Time | Resolution Time.
    Describe ACCOUNT_USAGE / INFORMATION_SCHEMA queries for pipeline health dashboards.

14. Risk & Issue Register
    Table: Risk ID | Category | Description | Probability | Impact | Mitigation | Owner | Status.
    Include technical (schema drift, late-arriving data), operational, and security risks.

15. Assumptions & Dependencies
    Table: ID | Type (Assumption/Dependency/Constraint) | Description | Owner | Impact if Unmet.

16. Future Enhancements Roadmap
    Table: Enhancement | Business Value | Technical Complexity | Suggested Release | Prerequisites.
    Include ML feature store, real-time streaming, self-serve analytics, data mesh evolution.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARCHITECTURE CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{context_str}
"""

    return ""

def main():
    selected_model, active_session = render_ai_sidebar()
    
    render_page_header("Deliverables", "Generate Client Proposals and Technical Solutions directly from the orchestrated architecture outputs.", "Documents")

    req_keys = [
        "architecture_strategy", "schema_modeling", "relationship_design",
        "pipeline_design", "governance_security", "ddl_generation", "final_blueprint"
    ]
    
    missing = [k for k in req_keys if not st.session_state.get(k)]
    if missing:
        st.warning("Complete AI Architecture Generation first to access Project Bidding.")
        if st.button("Go to AI Generation"):
            st.switch_page("pages/3_AI_Generation.py")
        return

    # Gather enriched context for enterprise-grade documentation
    context = {}
    
    # 0. Core Business Context
    context["business_requirements"] = st.session_state.get("requirements", {})
    
    # Extract only key meta-stats from data profile to prevent token bloat
    dp = st.session_state.get("data_profile", {})
    if isinstance(dp, dict):
        context["data_profile_summary"] = {
            "source_type": dp.get("source_type", "Unknown"),
            "table_count": len(dp.get("tables", [])),
            "estimated_volume": "Provided in intake form"
        }
    
    # 1. Architecture Strategy
    arch = st.session_state.get("architecture_strategy", {})
    if isinstance(arch, dict):
        context["architecture"] = {
            "type": arch.get("architecture_type"),
            "paradigm": arch.get("modeling_paradigm"),
            "layers": arch.get("layers", []),
            "justification": arch.get("architecture_justification", {}).get("why_chosen", "")
        }
        
    # 2. Schema Modeling (include columns for implementation detail)
    schema = st.session_state.get("schema_modeling", {})
    if isinstance(schema, dict) and "tables" in schema:
        context["data_model"] = [
            {
                "table": t.get("name"), 
                "layer": t.get("layer", ""),
                "columns": [c.get("name") for c in t.get("columns", []) if isinstance(c, dict)][:10] # Top 10 cols
            } 
            for t in schema["tables"] if isinstance(t, dict)
        ]
        
    # 3. Pipeline Design (include source/target mapping for ETL framework)
    pipe = st.session_state.get("pipeline_design", {})
    if isinstance(pipe, dict) and "tasks" in pipe:
        context["etl_framework"] = [
            {"task": t.get("n"), "source": t.get("s"), "target": t.get("t"), "logic": t.get("l")} 
            for t in pipe["tasks"] if isinstance(t, dict)
        ]
        
    # 4. Governance (include roles and masking)
    gov = st.session_state.get("governance_security", {})
    if isinstance(gov, dict):
        context["security_governance"] = {
            "roles": [r.get("n") for r in gov.get("roles", []) if isinstance(r, dict)],
            "masking_policies": [{"column": m.get("n"), "type": m.get("t")} for m in gov.get("mask", []) if isinstance(m, dict)],
            "compliance": gov.get("compliance_checklist", [])
        }
        
    # 5. DDL/Deployment Snippet
    ddl = st.session_state.get("ddl_generation", {})
    if isinstance(ddl, dict) and ddl.get("transform_sql"):
        context["deployment_pattern"] = ddl.get("transform_sql", "")[:500] # Provide snippet for pattern context
        
    # 6. Final Blueprint
    bp = st.session_state.get("final_blueprint", {})
    if isinstance(bp, dict):
        context["blueprint_executive_summary"] = bp.get("documentation", {}).get("executive_summary", bp.get("summary", ""))
        
    context_str = json.dumps(context, default=str)

    st.markdown('''
        <div class="glass-card-white" style="margin-bottom: 20px; padding: 20px;">
            <h3 style="margin-top: 0; color: #002244; font-weight: 700; font-family: 'Outfit', sans-serif;">Document Generation</h3>
            <p style="color: #64748B; font-size: 0.95rem; margin-bottom: 0; font-family: 'Outfit', sans-serif;">Leverage your finalized architecture blueprint to automatically construct business and technical documentation.</p>
        </div>
    ''', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    gen_prop = c1.button("Generate Proposal", type="primary", use_container_width=True)
    gen_tech = c2.button("Generate Technical Document", type="primary", use_container_width=True)
    gen_both = c3.button("Generate Both Documents", use_container_width=True)

    def save_docs_to_db(session):
        from dwh_assistant.backend.snowflake import save_project_to_store
        
        project_id = st.session_state.get("project_id")
            
        req = st.session_state.get("requirements", {})
        dp = st.session_state.get("data_profile", {})
        
        # Build outputs bundle mapping to current state
        outputs = {
            "architecture_selection": st.session_state.get("architecture_strategy", {}),
            "schema_design": st.session_state.get("schema_modeling", {}),
            "pipeline_design": st.session_state.get("pipeline_design", {}),
            "governance_security": st.session_state.get("governance_security", {}),
            "artifacts": {
                "ddl_sql": st.session_state.get("ddl_generation", {}).get("ddl_sql", ""),
                "documentation": json.dumps({
                    "proposal": st.session_state.get("proposal_doc"),
                    "technical": st.session_state.get("tech_doc")
                })
            },
            "history": st.session_state.get("history", {}),
            "mermaid_diagram": st.session_state.get("ddl_generation", {}).get("mermaid_diagram", "")
        }
        
        try:
            save_project_to_store(session, project_id, req, dp, outputs)
        except Exception as e:
            st.warning(f"Docs generated but failed to save to DB: {e}")

    if gen_prop or gen_both:
        session = ensure_session()
        doc_data = generate_document_chunked(session, "proposal", context_str, selected_model)
        if doc_data and doc_data.get("sections"):
            st.session_state["proposal_doc"] = doc_data
            st.success("Proposal Document generated successfully!")
            save_docs_to_db(session)
        else:
            st.error("Failed to generate Proposal Document")

    if gen_tech or gen_both:
        session = ensure_session()
        doc_data = generate_document_chunked(session, "technical", context_str, selected_model)
        if doc_data and doc_data.get("sections"):
            st.session_state["tech_doc"] = doc_data
            st.success("Technical Solution Document generated successfully!")
            save_docs_to_db(session)
        else:
            st.error("Failed to generate Technical Solution Document")

    st.markdown("<br>", unsafe_allow_html=True)

    # Display outputs
    if st.session_state.get("proposal_doc"):
        st.markdown('''
            <div style="background: #F8FAFC; border-left: 4px solid #38BDF8; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h4 style="margin: 0; color: #0F172A; font-family: 'Outfit', sans-serif;">Proposal Document</h4>
                    <p style="margin: 0; color: #64748B; font-size: 0.9rem;">Client-ready proposal based on your architecture.</p>
                </div>
                <div style="background: #E0F2FE; color: #0284C7; padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600;">
                    Ready
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        doc_data = st.session_state["proposal_doc"]
        if isinstance(doc_data, str): doc_data = {"sections": [{"heading": "Legacy Document", "type": "text", "content": doc_data}]}
        md_string = to_markdown_string(doc_data)
        
        pdf_gen = ConsultingPDFExporter(doc_data.get("document_metadata", {}))
        pdf_bytes = pdf_gen.generate(doc_data.get("sections", []))
        
        docx_gen = ConsultingDOCXExporter(doc_data.get("document_metadata", {}))
        docx_bytes = docx_gen.generate(doc_data.get("sections", []))
        
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        
        if c1.button("View Document" if not st.session_state.get("show_prop") else "Hide Document", key="btn_view_prop", use_container_width=True):
            st.session_state["show_prop"] = not st.session_state.get("show_prop", False)
            st.rerun()
            
        c2.download_button("PDF", data=pdf_bytes, file_name="Client_Proposal.pdf", mime="application/pdf", use_container_width=True)
        c3.download_button("DOCX", data=docx_bytes, file_name="Client_Proposal.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        c4.download_button("Markdown", data=md_string, file_name="Client_Proposal.md", mime="text/markdown", use_container_width=True)
        
        if c5.button("Copy Content" if not st.session_state.get("copy_prop") else "Hide Content", key="btn_copy_prop", use_container_width=True):
            st.session_state["copy_prop"] = not st.session_state.get("copy_prop", False)
            st.rerun()
            
        if c6.button("Regenerate", key="regen_prop", use_container_width=True):
            with st.spinner("Regenerating Proposal Document..."):
                session = ensure_session()
                doc_data_new = generate_document_chunked(session, "proposal", context_str, selected_model)
                if doc_data_new and doc_data_new.get("sections"):
                    st.session_state["proposal_doc"] = doc_data_new
                    st.success("Regenerated successfully!")
                    save_docs_to_db(session)
                else:
                    st.error("Failed to regenerate.")
            st.rerun()
            
        if st.session_state.get("copy_prop"):
            st.info("Click the copy icon in the top right of the code block below to copy the markdown content.")
            st.code(md_string, language="markdown")
            
        if st.session_state.get("show_prop"):
            with st.container(border=True):
                render_document_ui(doc_data)
                
        st.divider()

    if st.session_state.get("tech_doc"):
        st.markdown('''
            <div style="background: #F8FAFC; border-left: 4px solid #38BDF8; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h4 style="margin: 0; color: #0F172A; font-family: 'Outfit', sans-serif;">Technical Solution Document</h4>
                    <p style="margin: 0; color: #64748B; font-size: 0.9rem;">Comprehensive technical specification for data engineering.</p>
                </div>
                <div style="background: #E0F2FE; color: #0284C7; padding: 4px 10px; border-radius: 20px; font-size: 0.8rem; font-weight: 600;">
                    Ready
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        doc_data = st.session_state["tech_doc"]
        if isinstance(doc_data, str): doc_data = {"sections": [{"heading": "Legacy Document", "type": "text", "content": doc_data}]}
        md_string = to_markdown_string(doc_data)
        
        pdf_gen_t = ConsultingPDFExporter(doc_data.get("document_metadata", {}))
        pdf_bytes_t = pdf_gen_t.generate(doc_data.get("sections", []))
        
        docx_gen_t = ConsultingDOCXExporter(doc_data.get("document_metadata", {}))
        docx_bytes_t = docx_gen_t.generate(doc_data.get("sections", []))
        
        tc1, tc2, tc3, tc4, tc5, tc6 = st.columns(6)
        
        if tc1.button("View Document" if not st.session_state.get("show_tech") else "Hide Document", key="btn_view_tech", use_container_width=True):
            st.session_state["show_tech"] = not st.session_state.get("show_tech", False)
            st.rerun()
            
        tc2.download_button("PDF", data=pdf_bytes_t, file_name="Technical_Solution.pdf", mime="application/pdf", use_container_width=True)
        tc3.download_button("DOCX", data=docx_bytes_t, file_name="Technical_Solution.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
        tc4.download_button("Markdown", data=md_string, file_name="Technical_Solution.md", mime="text/markdown", use_container_width=True)
        
        if tc5.button("Copy Content" if not st.session_state.get("copy_tech") else "Hide Content", key="btn_copy_tech", use_container_width=True):
            st.session_state["copy_tech"] = not st.session_state.get("copy_tech", False)
            st.rerun()
            
        if tc6.button("Regenerate", key="regen_tech", use_container_width=True):
            with st.spinner("Regenerating Technical Solution..."):
                session = ensure_session()
                doc_data_new = generate_document_chunked(session, "technical", context_str, selected_model)
                if doc_data_new and doc_data_new.get("sections"):
                    st.session_state["tech_doc"] = doc_data_new
                    st.success("Regenerated successfully!")
                    save_docs_to_db(session)
                else:
                    st.error("Failed to regenerate.")
            st.rerun()
            
        if st.session_state.get("copy_tech"):
            st.info("Click the copy icon in the top right of the code block below to copy the markdown content.")
            st.code(md_string, language="markdown")
            
        if st.session_state.get("show_tech"):
            with st.container(border=True):
                render_document_ui(doc_data)

    # Document History Section
    st.divider()
    st.markdown('''
        <div class="glass-card-white" style="margin-bottom: 20px; padding: 20px;">
            <h3 style="margin-top: 0; color: #002244; font-weight: 700; font-family: 'Outfit', sans-serif;">Document History</h3>
            <p style="color: #64748B; font-size: 0.95rem; margin-bottom: 0; font-family: 'Outfit', sans-serif;">View and download documents generated from past projects.</p>
        </div>
    ''', unsafe_allow_html=True)
    
    session = ensure_session()
    all_projects = get_all_projects(session)
    if all_projects:
        project_options = {p["ID"]: f"{p['ID']} - {p['CREATED_AT'].strftime('%Y-%m-%d %H:%M') if hasattr(p['CREATED_AT'], 'strftime') else p['CREATED_AT']}" for p in all_projects}
        selected_past_id = st.selectbox("Select a past project to view its documents:", options=[""] + list(project_options.keys()), format_func=lambda x: project_options.get(x, "Select Project..."))
        
        if selected_past_id:
            past_proj = load_project_by_id(session, selected_past_id)
            if past_proj:
                p_doc = past_proj.get("proposal_doc")
                t_doc = past_proj.get("tech_doc")
                
                if p_doc:
                    st.markdown("#### Historical Proposal Document")
                    if isinstance(p_doc, str): p_doc = {"sections": [{"heading": "Legacy Document", "type": "text", "content": p_doc}]}
                    md_string_p = to_markdown_string(p_doc)
                    pdf_gen_p = ConsultingPDFExporter(p_doc.get("document_metadata", {}))
                    pdf_bytes_p = pdf_gen_p.generate(p_doc.get("sections", []))
                    docx_gen_p = ConsultingDOCXExporter(p_doc.get("document_metadata", {}))
                    docx_bytes_p = docx_gen_p.generate(p_doc.get("sections", []))
                    
                    hc1, hc2, hc3, hc4, hc5 = st.columns(5)
                    if hc1.button("View Document" if not st.session_state.get(f"show_prop_{selected_past_id}") else "Hide Document", key=f"btn_view_prop_{selected_past_id}", use_container_width=True):
                        st.session_state[f"show_prop_{selected_past_id}"] = not st.session_state.get(f"show_prop_{selected_past_id}", False)
                        st.rerun()
                    hc2.download_button("PDF", data=pdf_bytes_p, file_name=f"Proposal_{selected_past_id}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_pdf_p_{selected_past_id}")
                    hc3.download_button("DOCX", data=docx_bytes_p, file_name=f"Proposal_{selected_past_id}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key=f"dl_docx_p_{selected_past_id}")
                    hc4.download_button("Markdown", data=md_string_p, file_name=f"Proposal_{selected_past_id}.md", mime="text/markdown", use_container_width=True, key=f"dl_md_p_{selected_past_id}")
                    if hc5.button("Copy Content" if not st.session_state.get(f"copy_prop_{selected_past_id}") else "Hide Content", key=f"btn_copy_prop_{selected_past_id}", use_container_width=True):
                        st.session_state[f"copy_prop_{selected_past_id}"] = not st.session_state.get(f"copy_prop_{selected_past_id}", False)
                        st.rerun()
                        
                    if st.session_state.get(f"copy_prop_{selected_past_id}"):
                        st.code(md_string_p, language="markdown")
                    if st.session_state.get(f"show_prop_{selected_past_id}"):
                        with st.container(border=True):
                            render_document_ui(p_doc)
                            
                    st.divider()
                            
                if t_doc:
                    st.markdown("#### Historical Technical Document")
                    if isinstance(t_doc, str): t_doc = {"sections": [{"heading": "Legacy Document", "type": "text", "content": t_doc}]}
                    md_string_t = to_markdown_string(t_doc)
                    pdf_gen_t2 = ConsultingPDFExporter(t_doc.get("document_metadata", {}))
                    pdf_bytes_t2 = pdf_gen_t2.generate(t_doc.get("sections", []))
                    docx_gen_t2 = ConsultingDOCXExporter(t_doc.get("document_metadata", {}))
                    docx_bytes_t2 = docx_gen_t2.generate(t_doc.get("sections", []))
                    
                    hc1, hc2, hc3, hc4, hc5 = st.columns(5)
                    if hc1.button("View Document" if not st.session_state.get(f"show_tech_{selected_past_id}") else "Hide Document", key=f"btn_view_tech_{selected_past_id}", use_container_width=True):
                        st.session_state[f"show_tech_{selected_past_id}"] = not st.session_state.get(f"show_tech_{selected_past_id}", False)
                        st.rerun()
                    hc2.download_button("PDF", data=pdf_bytes_t2, file_name=f"Tech_{selected_past_id}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_pdf_t_{selected_past_id}")
                    hc3.download_button("DOCX", data=docx_bytes_t2, file_name=f"Tech_{selected_past_id}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key=f"dl_docx_t_{selected_past_id}")
                    hc4.download_button("Markdown", data=md_string_t, file_name=f"Tech_{selected_past_id}.md", mime="text/markdown", use_container_width=True, key=f"dl_md_t_{selected_past_id}")
                    if hc5.button("Copy Content" if not st.session_state.get(f"copy_tech_{selected_past_id}") else "Hide Content", key=f"btn_copy_tech_{selected_past_id}", use_container_width=True):
                        st.session_state[f"copy_tech_{selected_past_id}"] = not st.session_state.get(f"copy_tech_{selected_past_id}", False)
                        st.rerun()
                        
                    if st.session_state.get(f"copy_tech_{selected_past_id}"):
                        st.code(md_string_t, language="markdown")
                    if st.session_state.get(f"show_tech_{selected_past_id}"):
                        with st.container(border=True):
                            render_document_ui(t_doc)
                
                # Render Historical Diagram
                m_diagram = past_proj.get("documentation_design", {}).get("mermaid_diagram", "")
                if m_diagram and isinstance(m_diagram, str) and len(m_diagram) > 10:
                    st.markdown("#### Historical Architecture Diagram")
                    
                    mdc1, mdc2 = st.columns([1, 4])
                    if mdc1.button("View Diagram" if not st.session_state.get(f"show_diag_{selected_past_id}") else "Hide Diagram", key=f"btn_view_diag_{selected_past_id}", use_container_width=True):
                        st.session_state[f"show_diag_{selected_past_id}"] = not st.session_state.get(f"show_diag_{selected_past_id}", False)
                        st.rerun()
                        
                    if st.session_state.get(f"show_diag_{selected_past_id}"):
                        from dwh_assistant.components.mermaid_renderer import render_mermaid
                        with st.container(border=True):
                            render_mermaid(m_diagram, height=600)
                            
                    st.divider()

                # Handle legacy plain-text documents
                legacy_str = past_proj.get("documentation_design", {}).get("documentation", "")
                if not p_doc and not t_doc and isinstance(legacy_str, str) and len(legacy_str) > 20 and not legacy_str.strip().startswith('{"proposal"'):
                    st.markdown("#### Historical Legacy Document")
                    legacy_doc = {"document_metadata": {"title": "Legacy Project Document", "version": "1.0"}, "sections": [{"heading": "Content", "type": "text", "content": legacy_str}]}
                    md_string_l = legacy_str
                    pdf_gen_l = ConsultingPDFExporter(legacy_doc.get("document_metadata", {}))
                    pdf_bytes_l = pdf_gen_l.generate(legacy_doc.get("sections", []))
                    docx_gen_l = ConsultingDOCXExporter(legacy_doc.get("document_metadata", {}))
                    docx_bytes_l = docx_gen_l.generate(legacy_doc.get("sections", []))
                    
                    hc1, hc2, hc3, hc4, hc5 = st.columns(5)
                    if hc1.button("View Document" if not st.session_state.get(f"show_leg_{selected_past_id}") else "Hide Document", key=f"btn_view_leg_{selected_past_id}", use_container_width=True):
                        st.session_state[f"show_leg_{selected_past_id}"] = not st.session_state.get(f"show_leg_{selected_past_id}", False)
                        st.rerun()
                    hc2.download_button("PDF", data=pdf_bytes_l, file_name=f"Legacy_{selected_past_id}.pdf", mime="application/pdf", use_container_width=True, key=f"dl_pdf_l_{selected_past_id}")
                    hc3.download_button("DOCX", data=docx_bytes_l, file_name=f"Legacy_{selected_past_id}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True, key=f"dl_docx_l_{selected_past_id}")
                    hc4.download_button("Markdown", data=md_string_l, file_name=f"Legacy_{selected_past_id}.md", mime="text/markdown", use_container_width=True, key=f"dl_md_l_{selected_past_id}")
                    if hc5.button("Copy Content" if not st.session_state.get(f"copy_leg_{selected_past_id}") else "Hide Content", key=f"btn_copy_leg_{selected_past_id}", use_container_width=True):
                        st.session_state[f"copy_leg_{selected_past_id}"] = not st.session_state.get(f"copy_leg_{selected_past_id}", False)
                        st.rerun()
                        
                    if st.session_state.get(f"copy_leg_{selected_past_id}"):
                        st.code(md_string_l, language="markdown")
                    if st.session_state.get(f"show_leg_{selected_past_id}"):
                        with st.container(border=True):
                            render_document_ui(legacy_doc)

                elif not p_doc and not t_doc:
                    st.info("Documents have not been generated for this project yet. Select the project and click 'Generate Both Documents' above to create them.")
    else:
        st.info("No historical projects found in the database.")

if __name__ == "__main__":
    main()
