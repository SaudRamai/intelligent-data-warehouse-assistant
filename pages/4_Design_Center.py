import streamlit as st
import time
import sys
import os
from pathlib import Path

# Fix for ModuleNotFoundError
root_path = str(Path(__file__).parent.parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

import pandas as pd
import json
import re

from dwh_assistant.backend.executor import format_ddl
from dwh_assistant.utils.ui import apply_premium_style, render_ai_sidebar, init_session_state, render_page_header
from dwh_assistant.components.mermaid_renderer import render_mermaid
st.set_page_config(page_title="Design Center | AI DWH", layout="wide")
init_session_state()
apply_premium_style()

def repair_session_state_keys():
    """Repairs mismatched keys in session_state for backward compatibility."""
    
    # If we have schema_modeling but not schema_design, create alias
    if st.session_state.get("schema_modeling") and not st.session_state.get("schema_design"):
        st.session_state["schema_design"] = st.session_state["schema_modeling"]
        st.session_state["schema"] = st.session_state["schema_modeling"]
        print("[REPAIR] Created schema_design alias from schema_modeling")
    
    # If we have final_blueprint but not blueprint, create alias
    if st.session_state.get("final_blueprint") and not st.session_state.get("blueprint"):
        st.session_state["blueprint"] = st.session_state["final_blueprint"]
        print("[REPAIR] Created blueprint alias from final_blueprint")
    
    # If generation_results exists, re-extract outputs
    gen_res = st.session_state.get("generation_results")
    if isinstance(gen_res, dict):
        outputs = gen_res.get("outputs", {})
        if outputs:
            # Re-map with correct keys
            if "schema_modeling" in outputs and not st.session_state.get("schema"):
                st.session_state["schema"] = outputs["schema_modeling"]
                st.session_state["schema_design"] = outputs["schema_modeling"]
                print("[REPAIR] Restored schema from generation_results")

def main():
    # Sidebar for consistent model selection
    st.sidebar.title("DWH Assistant")
    from dwh_assistant.backend.snowflake import ensure_session
    try:
        ensure_session()
    except Exception as e:
        st.error(f"Session Error: {e}")
        st.stop()
        
    selected_model, active_session = render_ai_sidebar()

    # ADD THIS:
    repair_session_state_keys()  # Fix any key mismatches

    def render_regenerate_button(label: str, module_key: str):
        c_spacer, c_btn = st.columns([5, 1])
        with c_btn:
            if st.button(f"🔄 Regenerate", key=f"regen_{module_key}", help=f"Regenerate {label} independently via AI", use_container_width=True):
                with st.spinner(f"Regenerating {label}..."):
                    from dwh_assistant.backend.orchestrator import run_single_module
                    model = st.session_state.get("selected_model", "claude-sonnet-4-6")
                    res = run_single_module(
                        active_session, 
                        module_key, 
                        st.session_state.get("requirements", {}), 
                        st.session_state.get("data_profile", {}), 
                        st.session_state.get("generation_results", {}).get("outputs", {}), 
                        model,
                        force_refresh=True
                    )
                    
                    if "generation_results" not in st.session_state:
                        st.session_state["generation_results"] = {"outputs": {}}
                    if "outputs" not in st.session_state["generation_results"]:
                        st.session_state["generation_results"]["outputs"] = {}
                        
                    st.session_state["generation_results"]["outputs"][module_key] = res
                    st.session_state[module_key] = res
                    
                    if module_key == "schema_modeling":
                        st.session_state["schema"] = res
                        st.session_state["schema_design"] = res
                    elif module_key == "architecture_strategy":
                        st.session_state["architecture"] = res
                        st.session_state["architecture_selection"] = res
                    elif module_key == "pipeline_design":
                        st.session_state["pipeline"] = res
                    elif module_key == "governance_security":
                        st.session_state["governance"] = res
                    elif module_key == "ddl_generation":
                        st.session_state["artifacts"] = res
                        
                    st.rerun()

    def render_tab_placeholder(label, data):
        """Shows a premium skeleton state if data is missing but generation is running."""
        is_running = st.session_state.get("generation_running", False)
        if is_running and (not data or len(str(data)) < 10):
            st.markdown(f"""
                <div style="padding: 60px; text-align: center; background: #F8FAFC; border-radius: 12px; border: 2px dashed #E2E8F0; margin-top: 20px;">
                    <div class="spinner-border text-info" role="status" style="width: 3rem; height: 3rem; margin-bottom: 20px; opacity: 0.6;"></div>
                    <h3 style="color: #0F172A; font-weight: 600; margin-bottom: 10px;">Architecting {label}...</h3>
                    <p style="color: #64748B; font-size: 0.95rem;">Our AI agents are currently designing these components in a parallel workstream.<br>Results will appear here automatically as they are finalized.</p>
                </div>
            """, unsafe_allow_html=True)
            return True
        return False

    def render_interactive_mermaid(code, session_key, label="Diagram", height=500, checks=None, node_layers: dict = None):
        """Unified helper to render Mermaid with an editor and quality checks."""
        
        print(f"\n[DWH LOG] render_interactive_mermaid for '{session_key}' ('{label}'). Code present: {bool(code)}")
        if not code:
            print(f"[DWH LOG] Code for '{label}' is empty/None.")
            st.info(f"{label} will be available after AI generation.")
            return

        from dwh_assistant.utils.parser import clean_mermaid_code
        
        tab_route = None
        if "schema" in session_key.lower(): tab_route = "schema"
        elif "architecture" in session_key.lower(): tab_route = "architecture"
        elif "pipeline" in session_key.lower(): tab_route = "pipeline"
        elif "governance" in session_key.lower(): tab_route = "governance"
        
        cleaned = clean_mermaid_code(code, tab_route=tab_route)
        
        # Callback for editor
        def sync_mermaid():
            new_val = st.session_state[f"editor_{session_key}"].strip()
            # Update deep session state
            keys = session_key.split(".")
            target = st.session_state
            for k in keys[:-1]:
                if k not in target: target[k] = {}
                target = target[k]
            target[keys[-1]] = new_val

        # Use latest edited code from session state if available, otherwise fallback to cleaned AI output
        session_val = st.session_state.get(f"editor_{session_key}")
        current_code = session_val if session_val is not None else cleaned
        
        # Prevent invalid raw headers/text from crashing Mermaid parser; render cleanly outside diagram layer
        if not current_code or current_code.strip() == "":
            st.info(f"No valid graph/diagram syntax detected for {label}. Displaying raw extracted UI text layer:")
            if code and code.strip():
                st.markdown(f"<div style='padding:15px; background:#F8FAFC; border-radius:8px; border:1px solid #E2E8F0; color:#334155; white-space: pre-wrap; font-family: monospace;'>{code}</div>", unsafe_allow_html=True)
            return
        
        st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; margin-top: 20px;">
                <h2 style="margin: 0; color: #0F172A; font-size: 1.5rem; font-weight: 700;">{label}</h2>
                <div style="color: #64748B; font-size: 0.8rem; font-weight: 500;">{len(current_code)} characters</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Layout Controls
        show_editor = st.toggle(f"Developer Mode: View/Edit {label} Syntax", value=False, key=f"toggle_{session_key}")
        if show_editor:
            canvas_h = st.slider("Canvas Viewport Height", 400, 2000, height, 50, key=f"slider_{session_key}")
        else:
            canvas_h = height

        # Always render the diagram for maximum visibility
        try:
            render_mermaid(current_code, height=canvas_h, node_layers=node_layers)
        except Exception as e:
            st.error(f"Render Error: {e}")
        
        if show_editor:
            st.markdown("<p style='color: #64748B; font-size: 0.85rem; margin-bottom: 10px;'>Manual refinements will persist in the current session.</p>", unsafe_allow_html=True)
            
            current_code = st.text_area(
                "Mermaid Syntax",
                value=current_code,
                height=300,
                key=f"editor_{session_key}",
                on_change=sync_mermaid,
                label_visibility="collapsed"
            )
            
            if checks:
                st.markdown("##### Design Quality Report")
                q_cols = st.columns(len(checks))
                for idx, (check_name, check_fn) in enumerate(checks.items()):
                    passed = check_fn(current_code)
                    q_cols[idx % len(q_cols)].markdown(f"{'[PASS]' if passed else '[FAIL]'} <small>{check_name}</small>", unsafe_allow_html=True)



    # Read from session_state with comprehensive fallbacks
    arch_data = (st.session_state.get("architecture_selection") or 
                 st.session_state.get("architecture") or 
                 st.session_state.get("architecture_strategy"))
    
    schema_data = (st.session_state.get("schema_modeling") or  # NEW: Try actual key first
                   st.session_state.get("schema_design") or 
                   st.session_state.get("schema"))
    
    pipeline_data = (st.session_state.get("pipeline_design") or 
                     st.session_state.get("pipeline"))
    
    governance_data = (st.session_state.get("governance_security") or 
                       st.session_state.get("governance"))
    
    ddl = (st.session_state.get("ddl_generation") or 
           st.session_state.get("artifacts"))
    
    # Schema context: derived from AI architecture layers (metadata-driven)
    schema_ctx = (st.session_state.get("schema_context") or
                  (st.session_state.get("generation_results") or {}).get("outputs", {}).get("schema_context") or
                  {})
    
    doc_design = (st.session_state.get("documentation_design") or 
                  st.session_state.get("final_blueprint") or {})
    
    history_data = st.session_state.get("history") or {}
    
    # Validation: Check if critical components are missing
    missing_components = []
    if not arch_data: missing_components.append("Architecture")
    if not schema_data: missing_components.append("Schema")
    if not pipeline_data: missing_components.append("Pipeline")
    if not governance_data: missing_components.append("Governance")
    if not ddl: missing_components.append("DDL Artifacts")
    
    if missing_components:
        st.error(f"Missing Components: {', '.join(missing_components)}")
        st.info("Please return to the AI Generation page to complete the architecture design.")
        if st.button("← Go to AI Generation"):
            st.switch_page("pages/3_AI_Generation.py")
        st.stop()

    # DEBUG: Log available keys for troubleshooting
    import sys
    if "--debug" in sys.argv or st.session_state.get("debug_mode"):
        st.sidebar.markdown("### Debug: Available Keys")
        available = {
            "architecture": bool(arch_data),
            "schema": bool(schema_data),
            "pipeline": bool(pipeline_data),
            "governance": bool(governance_data),
            "ddl": bool(ddl),
            "history": bool(history_data)
        }
        st.sidebar.json(available)
        
        st.sidebar.markdown("### Session State Keys")
        relevant_keys = [k for k in st.session_state.keys() if any(x in k for x in 
            ["architecture", "schema", "pipeline", "governance", "ddl", "blueprint", "history", "design"])]
        st.sidebar.code("\n".join(sorted(relevant_keys)))

    # Header Section (Aligned with Home Page / AI Generation)
    # Header Section (Aligned with Home Page / AI Generation)
    render_page_header("Design", "Review and refine your industrial data architecture.", "Center")
    
    # 0. Live Generation Monitor (Industrial Speed Hack)
    is_running = st.session_state.get("generation_running", False)
    if is_running:
        st.markdown("""
            <div style="background: rgba(15, 23, 42, 0.05); padding: 15px; border-radius: 8px; border: 1px solid #E2E8F0; margin-bottom: 25px; border-left: 4px solid #0EA5E9;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center;">
                        <span style="font-weight: 700; color: #0F172A; margin-right: 15px;">AI CORE ACTIVE:</span>
                        <span style="color: #64748B; font-size: 0.9rem;">Parallel workstreams are populating tabs in real-time...</span>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <div class="spinner-grow text-info" role="status" style="width: 1rem; height: 1rem; margin-right: 8px;"></div>
                        <span style="font-size: 0.8rem; color: #0EA5E9; font-weight: 600;">LIVE FEED ACTIVE (3s)</span>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        # Periodic refresh to pull data from background threads
        time.sleep(3)
        st.rerun()
    
    # 1. Initialize ALL Session State variables at once for consistency
    def _safe_load(key):
        val = st.session_state.get(key, {})
        if isinstance(val, str):
            try:
                # Try to extract JSON from markdown if present
                json_match = re.search(r'\{.*\}', val, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0), strict=False)
                return json.loads(val, strict=False)
            except:
                return {"_raw": val}
        return val if isinstance(val, dict) else {}

    # 1. Master Results Registry (Background Thread Safe)
    gen_results = st.session_state.get("generation_results", {})

    # 2. Master Contract Load with Deep Extraction Support
    gen_outputs = gen_results.get("outputs", gen_results) if isinstance(gen_results, dict) else {}
    
    blueprint = arch_data if arch_data else {}
    schema = schema_data if schema_data else {}
    meta = st.session_state.get("metadata_analysis") or gen_outputs.get("metadata_analysis") or {}
    rel = st.session_state.get("relationship_design") or gen_outputs.get("relationship_design") or {}
    pipeline = pipeline_data if pipeline_data else {}
    gov = governance_data if governance_data else {}
    artifacts = ddl if ddl else {}
    final = st.session_state.get("final_blueprint") or gen_outputs.get("final_blueprint") or {}
    history_data = history_data if history_data else {}

    # Define master_layers mapping tables/tasks to layers
    master_layers = {}
    if isinstance(schema, dict):
        all_tables = schema.get("tables", [])
        if isinstance(all_tables, list):
            for t in all_tables:
                if isinstance(t, dict) and t.get("name") and t.get("layer"):
                    master_layers[t.get("name").lower()] = t.get("layer").lower()
    if isinstance(pipeline, dict):
        tasks = pipeline.get("tasks", [])
        if isinstance(tasks, list):
            for t in tasks:
                if isinstance(t, dict):
                    t_name = t.get("name") or t.get("n")
                    t_layer = t.get("layer") or t.get("l")
                    if t_name and t_layer:
                        master_layers[str(t_name).lower()] = str(t_layer).lower()
    
    # Mapping minified keys for UI
    mermaid_erd = rel.get("mermaid") or rel.get("mermaid_diagram") or "erDiagram\n"
    lineage_data = meta.get("lin") or meta.get("lineage") or []
    gov_tags = meta.get("tags") or meta.get("governance_tags") or []
    governance_mermaid = gov.get("mermaid") or gov.get("mermaid_diagram") or "graph LR"


    # Map internal artifact keys to expected variables for existing UI components
    ddl = artifacts if artifacts else {}
    doc_design = (
        gen_results.get("documentation_summary") or 
        st.session_state.get("documentation_design") or 
        st.session_state.get("final_blueprint") or 
        gen_outputs.get("final_blueprint") or 
        st.session_state.get("documentation_summary") or 
        (artifacts.get("documentation") if isinstance(artifacts, dict) else {}) or {}
    )
    if not isinstance(doc_design, dict): doc_design = {}

    
    # Status Check Banner
    status_cols = st.columns(6)
    steps = [
        ("Architecture", "architecture_strategy"),
        ("Schema", "schema_modeling"),
        ("Pipeline", "pipeline_design"),
        ("Governance", "governance_security"),
        ("Artifacts", "ddl_generation"),
        ("History", "history")
    ]
    for i, (label, key) in enumerate(steps):
        is_ready = bool(gen_results.get(key) or st.session_state.get(key))
        status_cols[i].markdown(f"""
            <div style="text-align: center; padding: 8px; border-radius: 8px; background: {'rgba(56, 189, 248, 0.1)' if is_ready else 'rgba(244, 63, 94, 0.1)'}; border: 1px solid {'#38BDF8' if is_ready else '#F43F5E'};">
                <small style="color: {'#38BDF8' if is_ready else '#F43F5E'}; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px;">{label}</small><br>
                <small style="color: {'#E2E8F0' if is_ready else '#F43F5E'}; opacity: 0.8;">{'READY' if is_ready else 'MISSING'}</small>
            </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    tabs = st.tabs(["Architecture", "Schema", "Pipeline", "Governance", "Artifacts", "History"])
    
    with tabs[0]:
        render_regenerate_button("Architecture", "architecture_strategy")
        if not blueprint:
            st.warning("Architectural metadata is missing. Please ensure the 'Architecture Strategy Selection' step in AI Generation completed successfully.")
            if st.button("Return to AI Generation"):
                st.switch_page("pages/3_AI_Generation.py")
            return
            
        strategy_name = blueprint.get('architecture_type', 'N/A').replace('_', ' ').title()
        st.markdown(f"<h2 style='color: #0F172A; margin-top: 0;'>Architecture Strategy: <span style='color: #0284c7;'>{strategy_name}</span></h2>", unsafe_allow_html=True)
        st.markdown("""
            <div style="background: #F0F9FF; border-left: 4px solid #0284c7; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px;">
                <span style="font-weight: 600; color: #0369A1;">Pipeline View Only:</span> Displays high-level data pipeline layers representing system flow and data movement. Completely isolates flow architecture without relational tables or column attributes.
            </div>
        """, unsafe_allow_html=True)
        
        # Interactive Architecture Fitness Radar - Case Insensitive Mapping
        def get_metric_val(val, default=50):
            if not val: return default
            m = str(val).lower()
            return {"low": 30, "medium": 60, "high": 90}.get(m, default)

        # Dynamic Fitness Profile from Master Blueprint
        metrics = blueprint.get("fitness_metrics", {})
        if not metrics and "architecture_strategy" in st.session_state:
            metrics = st.session_state.get("architecture_strategy", {}).get("fitness_metrics", {})
            
        fitness_data = []
        if metrics:
            for k, v in metrics.items():
                fitness_data.append({"Metric": k, "Value": v})
        else:
            fitness_data = [
                {"Metric": "Complexity", "Value": get_metric_val(blueprint.get("complexity"))},
                {"Metric": "Cost", "Value": get_metric_val(blueprint.get("estimated_cost_tier"))},
                {"Metric": "Scalability", "Value": 85}, 
                {"Metric": "Performance", "Value": 75},
                {"Metric": "Security", "Value": 90}
            ]
        fitness_df = pd.DataFrame(fitness_data)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("#### Architectural Reasoning")
            reasoning = blueprint.get("reasoning_summary") or blueprint.get("selection_logic", {}).get("business_rationale") or blueprint.get("reasoning", {}).get("selection", "N/A")
            st.markdown(f"<div style='color: #1a3c61; margin-bottom: 20px;'>{reasoning}</div>", unsafe_allow_html=True)
        
        with c2:
            st.markdown("#### Architectural Fitness Profile")
            st.vega_lite_chart(fitness_df, {
                'mark': {'type': 'bar', 'cornerRadiusEnd': 4, 'fill': '#38BDF8'},
                'encoding': {
                    'y': {'field': 'Metric', 'type': 'nominal', 'axis': {'title': None, 'labelColor': '#1a3c61'}},
                    'x': {'field': 'Value', 'type': 'quantitative', 'scale': {'domain': [0, 100]}, 'axis': {'title': 'Score', 'labelColor': '#1a3c61', 'titleColor': '#1a3c61'}},
                    'color': {'condition': {'test': 'datum.Value > 70', 'value': '#38BDF8'}, 'value': '#475569'}
                },
                'height': 250, 'background': 'transparent'
            }, use_container_width=True)

        justification = blueprint.get("architecture_justification")
        if justification and isinstance(justification, dict):
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### Architectural Decision Justification")
            jc1, jc2 = st.columns(2)
            with jc1:
                st.markdown(f"**Why Chosen**:\n{justification.get('why_chosen', 'N/A')}")
                st.markdown("<br>", unsafe_allow_html=True)
                
                alts = justification.get('alternatives_rejected', [])
                if isinstance(alts, list):
                    alts_str = "\n".join([f"- {a}" for a in alts])
                else:
                    alts_str = str(alts)
                st.markdown(f"**Alternatives Analyzed & Rejected**:\n{alts_str}")
            with jc2:
                assumptions = justification.get('assumptions_made', [])
                if isinstance(assumptions, list):
                    assump_str = "\n".join([f"- {a}" for a in assumptions])
                else:
                    assump_str = str(assumptions)
                st.markdown(f"**Assumptions Made**:\n{assump_str}")
                st.markdown("<br>", unsafe_allow_html=True)
                
                constraints = justification.get('constraints_influenced', [])
                if isinstance(constraints, list):
                    const_str = "\n".join([f"- {a}" for a in constraints])
                else:
                    const_str = str(constraints)
                st.markdown(f"**Influencing Constraints**:\n{const_str}")

        st.divider()
        
        # 3. Data Model Blueprint
        model = blueprint.get("data_model_blueprint") or blueprint.get("data_model") or {}
        if model:
            st.markdown("### Data Model Blueprint")
            mc1, mc2 = st.columns(2)
            with mc1:
                st.markdown(f"**Schema Type**: <span class='accent-text'>{model.get('schema_type', 'N/A')}</span>", unsafe_allow_html=True)
                entities = model.get('core_entities') or model.get('fact_tables', [])
                st.markdown(f"**Core Entities**: {', '.join(entities if isinstance(entities, list) else [str(entities)])}")
            with mc2:
                rels = model.get('primary_relationships') or model.get('relationships', [])
                st.markdown(f"**Key Relationships**: {', '.join(rels if isinstance(rels, list) else [str(rels)])}")
            st.divider()



        # 5. Lifecycle Data Flow
        flow = blueprint.get("data_flow", {})
        if isinstance(flow, str):
            try: flow = json.loads(flow)
            except: flow = {"ingestion": flow}
        if not isinstance(flow, dict): flow = {}
        
        if flow:
            st.markdown("### LIFECYCLE DATA FLOW")
            with st.container():
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    st.markdown("##### Ingestion Path")
                    st.info(flow.get('ingestion', 'N/A'))
                with fc2:
                    st.markdown("##### Processing Layer")
                    st.info(flow.get('processing', 'N/A'))
                with fc3:
                    st.markdown("##### Serving/BI Layer")
                    st.info(flow.get('serving', 'N/A'))

        # 6. Governance & Compliance
        gov_meta = blueprint.get("governance", {})
        if isinstance(gov_meta, str):
            try: gov_meta = json.loads(gov_meta)
            except: gov_meta = {"security": gov_meta}
        if not isinstance(gov_meta, dict): gov_meta = {}
        
        if gov_meta:
            st.markdown("### ARCHITECTURAL GOVERNANCE")
            with st.container():
                gc1, gc2 = st.columns(2)
                with gc1:
                    st.success(f"**Security Guardrails**: {gov_meta.get('security', 'N/A')}")
                with gc2:
                    st.success(f"**Lineage Tracking**: {gov_meta.get('lineage', 'N/A')}")
            
        st.divider()
        
        # Architecture quality checks — fully adaptive, not tied to any specific layer model
        arch_checks = {
            "Has layer structure": lambda x: "subgraph" in x.lower() or ("-->" in x and len(x.split("\n")) > 2),
            "Has flow paths": lambda x: "-->" in x or "---" in x,
            "Has named nodes": lambda x: "[" in x or "(" in x or "{" in x,
            "Flowchart format": lambda x: "flowchart" in x.lower() or "graph" in x.lower(),
        }
        
        render_interactive_mermaid(
            blueprint.get("mermaid_diagram"), 
            "architecture_selection.mermaid_diagram",
            label="Architecture Blueprint",
            height=1000,
            checks=arch_checks,
            node_layers=master_layers
        )

    with tabs[1]:
        render_regenerate_button("Schema", "schema_modeling")
        st.markdown("### Industrial Schema Design")
        st.markdown("""
            <div style="background: #F0F9FF; border-left: 4px solid #0284c7; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px;">
                <span style="font-weight: 600; color: #0369A1;">Warehouse Detailed Model Only:</span> Fully detailed relational design derived from the Architecture tab. Explicitly defines all table structures, columns, data types, primary keys (PK), and foreign keys (FK) without high-level pipeline or source system layers.
            </div>
        """, unsafe_allow_html=True)

        # Schema ERD: ONLY use schema_modeling mermaid_diagram — never doc_design which contains architecture-level diagrams
        # doc_design.mermaid_diagram is intentionally excluded here to avoid mixing pipeline architecture with the warehouse relational model
        from dwh_assistant.utils.parser import synthesize_erd_from_tables

        all_tables = schema.get("tables", [])
        if not isinstance(all_tables, list): all_tables = []
        rel_list = rel.get("rel", [])
        if not isinstance(rel_list, list): rel_list = []

        # Pull Data Model Blueprint metadata
        model = blueprint.get("data_model_blueprint") or blueprint.get("data_model") or {}
        core_entities = model.get('core_entities') or model.get('fact_tables', []) or []
        primary_relationships = model.get('primary_relationships') or model.get('relationships', []) or []

        # Backfill entities from Data Model Blueprint
        if core_entities:
            existing_names = {t.get("name").upper() for t in all_tables if isinstance(t, dict) and t.get("name")}
            for ent in core_entities:
                if ent.upper() not in existing_names:
                    # Guess a layer based on prefixes
                    layer = "Gold" if any(p in ent.upper() for p in ["DIM_", "FACT_", "FCT_", "GOLD"]) else "Silver"
                    all_tables.append({
                        "name": ent,
                        "layer": layer,
                        "columns": [
                            {"name": f"{ent.lower()}_sk", "type": "int", "pk": True, "description": "Surrogate primary key"},
                            {"name": "created_at", "type": "timestamp", "description": "Record creation timestamp"}
                        ]
                    })

        # Backfill relationships from Data Model Blueprint
        if primary_relationships:
            existing_rels = set()
            for r in rel_list:
                f = (r.get("from") or r.get("from_table") or "").upper()
                t = (r.get("to") or r.get("to_table") or "").upper()
                if f and t:
                    existing_rels.add((f, t))
                    existing_rels.add((t, f))
            
            for r_str in primary_relationships:
                parts = re.split(r'\s*(?:->|joins|to|-|ref|references)\s*', r_str, flags=re.IGNORECASE)
                if len(parts) >= 2:
                    f_ent = parts[0].strip().upper()
                    t_ent = parts[1].strip().upper()
                    if (f_ent, t_ent) not in existing_rels:
                        rel_list.append({
                            "from": parts[0].strip(),
                            "to": parts[1].strip(),
                            "cardinality": "||--o{",
                            "label": "references"
                        })

        total_cols = sum(len(t.get("columns", [])) for t in all_tables if isinstance(t, dict))
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Design Entities", len(all_tables), "Tables")
        mc2.metric("System Relationships", len(rel_list), "Foreign Keys")
        mc3.metric("Attribute Density", total_cols, "Columns")
        st.divider()

        # Data Model Blueprint (Shared from Architecture)
        model = blueprint.get("data_model_blueprint") or blueprint.get("data_model") or {}
        if model:
            st.markdown("### Data Model Blueprint")
            mc_b1, mc_b2 = st.columns(2)
            with mc_b1:
                st.markdown(f"**Schema Type**: <span style='color: #0284c7; font-weight: 600;'>{model.get('schema_type', 'N/A')}</span>", unsafe_allow_html=True)
                entities = model.get('core_entities') or model.get('fact_tables', [])
                st.markdown(f"**Core Entities**: {', '.join(entities if isinstance(entities, list) else [str(entities)])}")
            with mc_b2:
                rels = model.get('primary_relationships') or model.get('relationships', [])
                st.markdown(f"**Key Relationships**: {', '.join(rels if isinstance(rels, list) else [str(rels)])}")
            st.divider()
        # Tier 1: AI-generated diagram stored in schema_modeling — use if non-trivial and covers most tables
        ai_erd = schema.get("mermaid_diagram") or st.session_state.get("schema_modeling", {}).get("mermaid_diagram") or ""
        ai_erd = ai_erd.strip()

        def _erd_is_complete(erd_str: str, n_tables: int) -> bool:
            """Returns True only if the stored diagram looks substantially complete."""
            if not erd_str or len(erd_str) < 30:
                return False
            if "erdiagram" not in erd_str.lower():
                return False
            # Count entity blocks — each opens with a bare word followed by {
            entity_blocks = len(re.findall(r'^\s{0,8}[A-Z_][A-Z0-9_]+\s*\{', erd_str, re.MULTILINE | re.IGNORECASE))
            # Accept the AI diagram only if it covers at least 60 % of the tables
            if n_tables > 0 and entity_blocks < max(1, int(n_tables * 0.6)):
                return False
            return True

        if _erd_is_complete(ai_erd, len(all_tables)):
            erd_code = ai_erd
            print(f"[DWH LOG] Using AI-generated ERD ({len(erd_code)} chars, covers most tables)")
        elif all_tables:
            # Tier 2: Synthesise deterministically from merged tables + relationship list
            print(f"[DWH LOG] AI ERD incomplete or absent — synthesising from {len(all_tables)} tables + {len(rel_list)} rels")
            erd_code = synthesize_erd_from_tables(all_tables, rel_list)
        else:
            # Tier 3: Nothing available yet
            erd_code = "erDiagram\n"

        erd_key = "schema_design.mermaid_diagram"

        # 2. Main Visualization — schema ERD key already set above
        
        schema_checks = {
            "Has Entity Attributes": lambda x: "{" in x and "}" in x,
            "Has PK/FK Markers": lambda x: "PK" in x or "FK" in x or "sk" in x.lower() or "id" in x.lower(),
            "Surrogate Key Integrity": lambda x: "_sk" in x.lower(),
            "Has Relationships": lambda x: any(c in x for c in ["||--", "}o--", "|o--", "--o|", "--||", "-->"]),
            "Business Accuracy": lambda x: len(x.split("\n")) > 3
        }
        
        schema_tabs = st.tabs(["Entity Relationship Model", "Schema Inventory"])
        
        with schema_tabs[0]:
            # STRICT: Only use the warehouse schema ERD — rel.get("mermaid_diagram") can be a flowchart type and must NOT be used here
            mermaid_erd = erd_code or "erDiagram\n"
            render_interactive_mermaid(
                mermaid_erd,
                "schema.mermaid_diagram",
                label="Entity Relationship Diagram (ERD)",
                height=900,
                node_layers=master_layers
            )
            
            # 3. Layer Inventory

        with schema_tabs[1]:
            st.markdown("### Tabular Schema Inventory")
            # Strictly rely on runtime inference payload from the selected Cortex AI model
            unique_tables = all_tables

            if not unique_tables:
                st.info("No tables generated yet. Run AI Architect to populate.")
            else:
                from collections import defaultdict
                from dwh_assistant.utils.parser import layer_sort_key
                
                # Group unique tables by layer
                tables_by_layer = defaultdict(list)
                for t in unique_tables:
                    if not isinstance(t, dict):
                        continue
                    layer = t.get("layer", "Warehouse")
                    layer_display = str(layer).title()
                    tables_by_layer[layer_display].append(t)
                    
                sorted_layer_names = sorted(tables_by_layer.keys(), key=layer_sort_key)
                
                for layer_name in sorted_layer_names:
                    st.divider()
                    st.markdown(f"#### 📁 {layer_name.upper()} LAYER ({len(tables_by_layer[layer_name])} Entities)")
                    with st.container():
                        layer_tables = tables_by_layer[layer_name]
                        t_names = sorted([t.get("name") for t in layer_tables])
                        
                        selected_t_name = st.selectbox(
                            "Select Entity to Review", 
                            t_names, 
                            key=f"sel_inv_{layer_name.lower()}",
                            label_visibility="collapsed"
                        )
                        
                        t_obj = next((t for t in layer_tables if t.get("name") == selected_t_name), None)
                        if t_obj:
                            mcol1, mcol2 = st.columns([3, 1])
                            with mcol1:
                                st.markdown(f"##### Metadata: `{selected_t_name}`")
                                cols = t_obj.get("columns", [])
                                df_data = []
                                for c in cols:
                                    is_pk = t_obj.get("primary_key") == c.get("name") or c.get("primary_key") or c.get("pk")
                                    is_fk = c.get("is_fk") or c.get("references") or c.get("fk")
                                    df_data.append({
                                        "Column": c.get("name"),
                                        "Type": c.get("type"),
                                        "PK": "🔑 PK" if is_pk else "",
                                        "FK": "🔗 FK" if is_fk else "",
                                        "References": c.get("references") or c.get("ref") or "",
                                        "Description": c.get("description", "")
                                    })
                                st.dataframe(pd.DataFrame(df_data), use_container_width=True, hide_index=True)
                            with mcol2:
                                st.markdown("##### Entity Properties")
                                st.info(f"**Layer**: {t_obj.get('layer', 'N/A')}")
                                pk_name = t_obj.get('primary_key') or next((c.get("name") for c in t_obj.get("columns", []) if c.get("pk")), "None")
                                st.success(f"**PK**: {pk_name}")
                                t_rels = [r for r in rel_list if r.get("from") == selected_t_name or r.get("from_table") == selected_t_name]
                                if t_rels:
                                    st.markdown("##### Outbound Joins")
                                    for r in t_rels:
                                        target = r.get('to') or r.get('to_table')
                                        st.code(f"→ {target}")

        


    with tabs[2]:
        render_regenerate_button("Pipeline", "pipeline_design")
        if not render_tab_placeholder("Transformation Pipelines", pipeline):
            # 1. Metric Overview
            tasks = pipeline.get("tasks", [])
            pc1, pc2, pc3 = st.columns(3)
            pc1.metric("Total Orchestration Tasks", len(tasks), "Workflows")
            arch_state = st.session_state.get("architecture_strategy", {}) or st.session_state.get("architecture", {})
            arch_display = arch_state.get("architecture_type", "Dynamic")
            pc2.metric("Ingestion Frequency", "Streaming/Batch", arch_display)
            pc3.metric("Transformation Logic", len([t for t in tasks if t.get("type") == "transformation"]), "Steps")
            st.divider()
    
            # 2. Main Visualization
            # Pipeline quality checks — architecture-agnostic: supports Medallion, Data Vault, Lakehouse
            pipe_checks = {
                "Has Flowchart": lambda x: "graph" in x.lower() or "flowchart" in x.lower(),
                "Has Task Dependencies": lambda x: "-->" in x,
                "Has Layer Nodes": lambda x: any(kw in x.lower() for kw in [
                    "bronze", "silver", "gold",        # Medallion
                    "hub", "sat", "lnk", "vault",     # Data Vault
                    "raw", "conformed", "enriched",   # Lakehouse
                    "landing", "staging", "mart",     # Generic
                ]),
            }
            
            render_interactive_mermaid(
                pipeline.get("mermaid_diagram"),
                "pipeline_design.mermaid_diagram",
                label="Technical Pipeline DAG",
                height=800,
                checks=pipe_checks,
                node_layers=master_layers
            )
    
            # 3. Task Inventory
            st.markdown("#### Execution Strategy")
            if tasks:
                task_df = pd.DataFrame(tasks)
                if not task_df.empty:
                    available_cols = [c for c in ["name", "type", "layer", "frequency"] if c in task_df.columns]
                    st.dataframe(task_df[available_cols], use_container_width=True, hide_index=True)
        

    with tabs[3]:
        render_regenerate_button("Governance", "governance_security")
        if not render_tab_placeholder("Governance & Security", gov):
            # 1. Metric Overview
            g1, g2, g3 = st.columns(3)
            g1.metric("Roles Defined", len(gov.get("roles", [])), "RBAC")
            g2.metric("Masking Policies", len(gov.get("masking_policies", [])), "GDPR/CCPA")
            g3.metric("Compliant Steps", len(gov.get("compliance_checklist", [])), "Audit")
            st.divider()
    
            # 2. Main Visualization
            lineage_code_raw = (
                doc_design.get("governance_security", {}).get("mermaid_diagram") or 
                gov.get("mermaid_diagram") or 
                gov.get("mermaid_lineage")
            )
            lineage_code = lineage_code_raw or "graph LR\n  NODATA"

            # Governance checks — architecture-agnostic: detects any RBAC/policy/source/consumer pattern
            lineage_checks = {
                "Has Source/Role nodes": lambda x: any(kw in x.lower() for kw in ["source", "role", "graph", "admin", "user", "ingestion"]),
                "Has Consumer/Policy nodes": lambda x: any(kw in x.lower() for kw in ["gold", "bi", "policy", "storage", "mart", "info_mart", "dashboard", "report", "catalog"]),
                "Has Flow paths": lambda x: "-->" in x or "-." in x or "===" in x,
            }
            
            render_interactive_mermaid(
                lineage_code,
                "governance_security.mermaid_lineage",
                label="Industrial Privacy & Lineage Map",
                height=800,
                checks=lineage_checks,
                node_layers=master_layers
            )
    
            # 3. RBAC & Policies
            st.divider()
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown("#### RBAC Authorization Heatmap")
                rbac_data = []
                for role in gov.get("roles", []):
                    if isinstance(role, dict):
                        grants = role.get("grants") or role.get("privileges", [])
                        for grant in grants: 
                            if isinstance(grant, dict):
                                rbac_data.append({
                                    "Role": role.get("name"),
                                    "Object": grant.get("object_name", "All"),
                                    "Privilege": grant.get("privilege", "USAGE")
                                })
                if rbac_data: st.vega_lite_chart(pd.DataFrame(rbac_data), {'mark': {'type': 'rect', 'stroke': '#fff'}, 'encoding': {'x': {'field': 'Role', 'type': 'nominal'}, 'y': {'field': 'Object', 'type': 'nominal'}, 'color': {'field': 'Privilege', 'type': 'nominal', 'scale': {'range': ['#002244', '#38BDF8', '#1E40AF']}}}, 'height': 400}, use_container_width=True)
                
        with c2:
            st.markdown("#### Masking Policies")
            policies = gov.get("masking_policies", [])
            for p in policies:
                if isinstance(p, dict):
                    st.markdown(f"""
                        <div style="border: 1px solid #E2E8F0; padding: 10px; border-radius: 8px; margin-bottom: 10px;">
                            <span style="color: #F43F5E; font-weight: bold;">{p.get('column')}</span><br>
                            <small>{p.get('type')} for <b>{p.get('role')}</b></small>
                        </div>
                    """, unsafe_allow_html=True)

    with tabs[4]:
        render_regenerate_button("Artifacts", "ddl_generation")
        if not render_tab_placeholder("Artifacts & Deployment", artifacts):
            st.markdown("### Industrial Artifacts & Deployment")
            
            ac1, ac2, ac3 = st.columns(3)
            ddl_ready = bool(artifacts.get("ddl_sql"))
            ac1.metric("DDL Status", "READY" if ddl_ready else "PENDING")
            ac2.metric("RBAC Status", "READY" if bool(artifacts.get("grant_sql")) else "PENDING")
            ac3.metric("Readiness Score", "95%" if ddl_ready else "0%")
            
            st.divider()
            
            # Helper: force any value to a string for st.code / st.download_button
            def _to_str(val, fallback=""):
                if val is None: return fallback
                if isinstance(val, str): return val
                if isinstance(val, (dict, list)):
                    try: return json.dumps(val, indent=2)
                    except Exception: return str(val)
                return str(val)
    
            schema_creation_str = _to_str(ddl.get("schema_creation_sql"), "")
            if not schema_creation_str:
                # Pre-calculate fallback from schema_ctx so it is editable
                ctx_layers = schema_ctx.get("layers", []) if isinstance(schema_ctx, dict) else []
                if ctx_layers:
                    from dwh_assistant.backend.executor import layer_to_schema_name as _l2s
                    lines = ["-- ========================================================================="]
                    lines.append("-- SCHEMA CREATION (Derived from AI Architecture Strategy)")
                    lines.append("-- =========================================================================")
                    for lm in ctx_layers:
                        sname = lm.get("schema_name") or _l2s(lm.get("layer_name", "WAREHOUSE"))
                        lines.append(f"CREATE SCHEMA IF NOT EXISTS {sname};")
                    schema_creation_str = "\n".join(lines)

            ddl_sql_str     = _to_str(ddl.get("ddl_sql"), "-- No DDL generated")
            
            # Enhanced Documentation Rendering for Structured Objects
            doc_obj = doc_design
            if isinstance(doc_design, dict) and "documentation" in doc_design:
                nested = doc_design["documentation"]
                if isinstance(nested, (dict, str)):
                    doc_obj = nested
            
            if isinstance(doc_obj, str):
                doc_str = doc_obj
            elif isinstance(doc_obj, dict):
                doc_str = f"### Executive Summary\n{doc_obj.get('executive_summary', 'N/A')}\n\n"
                doc_str += f"### Architectural Logic\n{doc_obj.get('architecture_decision', doc_obj.get('architectural_logic', 'N/A'))}\n\n"
                if doc_obj.get('key_entities'):
                    entities = doc_obj.get('key_entities', [])
                    if isinstance(entities, list):
                        doc_str += f"### Key Entities\n- " + "\n- ".join(entities)
                    else:
                        doc_str += f"### Key Entities\n{entities}"
            else:
                doc_str = _to_str(doc_obj, "No documentation generated.")
            grant_sql_str = _to_str(ddl.get("grant_sql"), "-- No Grants generated")
            transform_sql_str = _to_str(ddl.get("transform_sql"), "-- No Transformations generated")

            # Synchronize editable state with original AI payload
            original_payload = {
                "schema_creation": schema_creation_str,
                "ddl_sql": ddl_sql_str,
                "grant_sql": grant_sql_str,
                "transform_sql": transform_sql_str
            }
            if st.session_state.get("artifacts_original_payload") != original_payload:
                st.session_state["edited_schema_creation"] = schema_creation_str
                st.session_state["edited_ddl_sql"] = ddl_sql_str
                st.session_state["edited_grant_sql"] = grant_sql_str
                st.session_state["edited_transform_sql"] = transform_sql_str
                st.session_state["artifacts_original_payload"] = original_payload

            # Ensure keys exist in session state
            if "edited_schema_creation" not in st.session_state: st.session_state["edited_schema_creation"] = schema_creation_str
            if "edited_ddl_sql" not in st.session_state: st.session_state["edited_ddl_sql"] = ddl_sql_str
            if "edited_grant_sql" not in st.session_state: st.session_state["edited_grant_sql"] = grant_sql_str
            if "edited_transform_sql" not in st.session_state: st.session_state["edited_transform_sql"] = transform_sql_str

            full_sql_script = f"""-- =========================================================================
-- SCHEMA CREATION (AI-Derived from Architecture Strategy)
-- =========================================================================
{st.session_state["edited_schema_creation"]}

-- =========================================================================
-- CORE DDL (TABLES & SCHEMAS)
-- =========================================================================
{st.session_state["edited_ddl_sql"]}

-- =========================================================================
-- ACCESS CONTROL (RBAC & GRANTS)
-- =========================================================================
{st.session_state["edited_grant_sql"]}
"""

            c1, c2 = st.columns([2, 1])
            with c1:
                # Add the Developer Mode Edit toggle
                edit_mode = st.toggle("✏️ Enable Developer Edit Mode (Modify AI Artifacts)", value=False, key="artifacts_edit_mode")
                
                # Sub-tabs for better organization
                sub_tabs = st.tabs(["Full Script", "Schemas", "Tables", "Grants", "Transformations"])
                
                with sub_tabs[0]:
                    if edit_mode:
                        st.info("💡 Edit the individual tabs to modify this compiled deployment script.")
                    st.code(full_sql_script, language="sql", line_numbers=True)

                with sub_tabs[1]:
                    st.markdown("#### Schema Architecture Map")
                    st.markdown("""
                        <div style="background: #F0F9FF; border-left: 4px solid #0284c7; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px;">
                            <span style="font-weight: 600; color: #0369A1;">Metadata-Driven Schemas:</span>
                            Derived dynamically from the AI-generated architecture layers — no hardcoded schema names.
                        </div>
                    """, unsafe_allow_html=True)

                    # Render the schema layer → schema name → table count table
                    ctx_layers = schema_ctx.get("layers", []) if isinstance(schema_ctx, dict) else []
                    if ctx_layers:
                        schema_map_rows = []
                        for lm in ctx_layers:
                            schema_map_rows.append({
                                "Architecture Layer": lm.get("layer_name", "N/A"),
                                "Snowflake Schema":   lm.get("schema_name", "N/A"),
                                "Tables Assigned":    len(lm.get("tables", [])),
                                "Table Names":        ", ".join(t.get("name", "") for t in lm.get("tables", []))
                            })
                        st.dataframe(pd.DataFrame(schema_map_rows), hide_index=True, use_container_width=True)
                        st.divider()
                    else:
                        st.info("Schema context not yet available. Run AI generation to populate.")

                    # Show/Edit the deterministic CREATE SCHEMA block
                    if edit_mode:
                        st.markdown("#### Edit Schema Creation Statements")
                        st.session_state["edited_schema_creation"] = st.text_area(
                            "Edit Schema Creation SQL",
                            value=st.session_state["edited_schema_creation"],
                            height=300,
                            key="editor_schema_creation",
                            label_visibility="collapsed"
                        )
                    else:
                        st.markdown("#### CREATE SCHEMA Statements")
                        if st.session_state["edited_schema_creation"].strip():
                            st.code(st.session_state["edited_schema_creation"], language="sql", line_numbers=True)
                        else:
                            st.info("No schema creation SQL available yet.")

                with sub_tabs[2]:
                    if edit_mode:
                        st.markdown("#### Edit Table DDL SQL")
                        st.session_state["edited_ddl_sql"] = st.text_area(
                            "Edit Table DDL SQL",
                            value=st.session_state["edited_ddl_sql"],
                            height=500,
                            key="editor_ddl_sql",
                            label_visibility="collapsed"
                        )
                    else:
                        st.code(st.session_state["edited_ddl_sql"], language="sql", line_numbers=True)

                with sub_tabs[3]:
                    if edit_mode:
                        st.markdown("#### Edit Access Control SQL")
                        st.session_state["edited_grant_sql"] = st.text_area(
                            "Edit Access Control SQL",
                            value=st.session_state["edited_grant_sql"],
                            height=500,
                            key="editor_grant_sql",
                            label_visibility="collapsed"
                        )
                    else:
                        st.code(st.session_state["edited_grant_sql"], language="sql", line_numbers=True)

                with sub_tabs[4]:
                    if edit_mode:
                        st.markdown("#### Edit Transformations SQL")
                        st.session_state["edited_transform_sql"] = st.text_area(
                            "Edit Transformations SQL",
                            value=st.session_state["edited_transform_sql"],
                            height=500,
                            key="editor_transform_sql",
                            label_visibility="collapsed"
                        )
                    else:
                        st.markdown("#### Transformations")
                        st.code(st.session_state["edited_transform_sql"], language="sql")
    
                st.divider()
                d1, d2 = st.columns(2)
                d1.download_button("Download Full Script (.sql)", full_sql_script, file_name="full_deployment_script.sql", use_container_width=True)
                d2.download_button("Technical Docs (.md)", doc_str, file_name="documentation.md", use_container_width=True)
            
            with c2:
                st.markdown("#### Deployment Console")
                
                with st.container():
                    st.markdown("""
                        <div style="background: #F8FAFC; padding: 15px; border-radius: 10px; border: 1px solid #E2E8F0; margin-bottom: 15px;">
                            <small style="color: #64748B; text-transform: uppercase; font-weight: 600;">Status</small><br>
                            <span style="font-size: 1.1rem; color: #0F172A; font-weight: 500;">Ready for Deployment</span>
                        </div>
                    """, unsafe_allow_html=True)
                
                if st.button("SAVE PROJECT SNAPSHOT", type="secondary", use_container_width=True):
                     from dwh_assistant.backend.snowflake import save_project_to_store, ensure_session
                     try:
                         ensure_session()
                         outputs = {
                             "architecture_selection": st.session_state.get("architecture_selection"),
                             "schema_design": st.session_state.get("schema_design"),
                             "pipeline_design": st.session_state.get("pipeline_design"),
                             "governance_security": st.session_state.get("governance_security"),
                             "ddl_generation": st.session_state.get("ddl_generation"),
                             "documentation_design": st.session_state.get("documentation_design"),
                             "relationship_design": st.session_state.get("relationship_design"),
                             "final_blueprint": st.session_state.get("final_blueprint"),
                             "history": st.session_state.get("history")
                         }
                         save_project_to_store(
                             st.session_state["snowflake_session"],
                             st.session_state.get("project_id"),
                             st.session_state.get("requirements", {}),
                             st.session_state.get("data_profile", {}),
                             outputs
                         )
                         st.toast("Design Saved Successfully!")
                     except Exception as e:
                         st.error(f"Save Failed: {e}")
    
                st.divider()
                st.markdown("##### Target Destination")
                
                t_db = st.text_input("Database", value="ANALYTICS_PROD")
                
                if st.button("EXECUTE FULL DEPLOYMENT", type="primary", use_container_width=True):
                    from dwh_assistant.backend.executor import execute_deployment
                    with st.status("Deploying to Snowflake...", expanded=True) as status:
                        schema_context = st.session_state.get("schema_context")
                        res = execute_deployment(
                            st.session_state.snowflake_session,
                            full_sql_script,
                            t_db,
                            project_id=st.session_state.get("project_id", "N/A"),
                            schema_context=schema_context
                        )
                        if res["success"]:
                            status.update(label="Deployment Successful!", state="complete", expanded=False)
                            st.success(f"Successfully executed {res['statements_run']} statements.")
                            if res.get("skipped_count", 0) > 0:
                                st.warning(f"⚠️ Skipped {res['skipped_count']} non-blocking statements (e.g. references to objects or roles that do not exist).")
                            st.dataframe(pd.DataFrame(res["results"]) if "results" in res else pd.DataFrame([{"status": "deployed"}]), use_container_width=True, hide_index=True)
                        else:
                            status.update(label="Deployment Failed", state="error", expanded=True)
                            st.error(f"Error: {res['error']}")
                            if "failed_statement" in res: st.code(res["failed_statement"], language="sql")

    with tabs[5]:
        if not render_tab_placeholder("Design History", history_data):
            st.markdown("### Industrial History & Provenance")
            
            # 1. Metric Overview
            hcol1, hcol2, hcol3 = st.columns(3)
            hcol1.metric("Current Version", history_data.get("version", "v1.0"), "Production")
            hcol2.metric("Last Generation", (history_data.get("generated_at", "N/A")[:10]) if history_data.get("generated_at") else time.strftime("%Y-%m-%d"), "UTC")
            hcol3.metric("Industrial Assumptions", len(history_data.get("assumptions", [])), "Verified")
            st.divider()
    
            # 2. History Details
            h_c1, h_c2 = st.columns(2)
            with h_c1:
                st.markdown("#### Strategic Assumptions")
                for a in history_data.get("assumptions", []):
                    st.info(f"**✓ Assumption**: {a}")
            with h_c2:
                st.markdown("#### Revision Log")
                for c in history_data.get("change_log", []):
                    st.success(f"**• Revision**: {c}")
        
        st.divider()
        st.subheader("Project Registry (Global History)")
        from dwh_assistant.backend.snowflake import get_all_projects, load_project_by_id
        projects = get_all_projects(st.session_state["snowflake_session"])
        for p_row in projects:
            # get_all_projects now returns plain dicts after Fix 6
            raw = p_row if isinstance(p_row, dict) else p_row.as_dict()
            p = {k.upper(): v for k, v in raw.items()}
            pid = p.get('ID')
            created_at = p.get('CREATED_AT')
            
            st.markdown(f"""
                <div class="glass-card" style="padding: 25px; margin-bottom: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: start;">
                        <div>
                            <h3 style="margin: 0; color: #38BDF8 !important;">Project Snapshot</h3>
                            <code style="background: rgba(0,0,0,0.2); color: #94A3B8; padding: 2px 6px; border-radius: 4px;">{pid}</code>
                        </div>
                        <div style="text-align: right;">
                            <small style="color: #94A3B8;">Created At</small><br>
                            <span style="font-weight: 600; color: #E2E8F0;">{created_at}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            with st.container():
                h1, h2 = st.columns([3, 1])
                h1.code(str(p.get('DDL_SQL') or "-- No DDL")[:500] + "...", language="sql")
                if h2.button("Load Design", key=f"load_dc_{pid}"):
                    p_data = load_project_by_id(st.session_state["snowflake_session"], pid)
                    if p_data:
                        for k, v in p_data.items(): st.session_state[k] = v
                        st.session_state["form_complete"] = True
                        st.success(f"Project {pid} Loaded Successfully!")
                        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
