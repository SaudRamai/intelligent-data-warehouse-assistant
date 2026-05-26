import streamlit as st
import sys
import os
from pathlib import Path

# Fix for ModuleNotFoundError
root_path = str(Path(__file__).parent.parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

import logging
import warnings
# Aggressively mute the "missing ScriptRunContext" warning
logging.getLogger("streamlit.runtime.scriptrunner").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")

import time
from dwh_assistant.backend.snowflake import get_available_cortex_models, ensure_session, save_project_to_store
from dwh_assistant.utils.ui import apply_premium_style, render_ai_sidebar, init_session_state, render_page_header
st.set_page_config(page_title="AI Generation | AI DWH", layout="wide")
init_session_state()
apply_premium_style()

def clear_all_generation_caches(steps):
    # 1. Clear persistent disk cache directory
    import shutil
    from dwh_assistant.backend.orchestrator import CORTEX_CACHE_DIR
    if CORTEX_CACHE_DIR.exists():
        shutil.rmtree(CORTEX_CACHE_DIR, ignore_errors=True)
        CORTEX_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Clear Streamlit's data cache
    st.cache_data.clear()

    # 3. Clear memory caches
    if "cortex_memory_cache" in st.session_state:
        st.session_state["cortex_memory_cache"] = {}
    if "profile_cache" in st.session_state:
        st.session_state["profile_cache"] = {}

    # 4. Clear steps outputs and raw outputs
    for _k, _ in steps:
        st.session_state[_k] = None
        st.session_state[f"{_k}_raw"] = None

    # 5. Clear compatibility and mapped session state keys
    other_keys = [
        "architecture_selection", "schema_design", "schema_modeling",
        "pipeline_design", "governance_security", "ddl_generation",
        "metadata_analysis", "relationship_design", "final_blueprint",
        "blueprint", "documentation_design", "architecture", "schema",
        "pipeline", "governance", "artifacts", "history", "generation_results"
    ]
    for key in other_keys:
        st.session_state[key] = None

    # 6. Clear manual overrides from the Design Center
    editor_keys = [k for k in list(st.session_state.keys()) if k.startswith("editor_") or k.startswith("toggle_") or k.startswith("slider_")]
    for key in editor_keys:
        del st.session_state[key]

def main():
    from dwh_assistant.backend.orchestrator import run_all, step_is_complete
    from dwh_assistant.backend.executor import call_cortex
    if not st.session_state.get("data_profile"):
        st.warning("Please confirm the Data Profile first.")
        if st.button("Go to Data Profile"):
            st.switch_page("pages/2_Data_Profile.py")
        return

    # Ensure valid session to prevent token expiration
    selected_model, active_session = render_ai_sidebar()

    # Continue adding custom sidebar elements after the unified selector
    with st.sidebar:
        # System Readiness Center
        st.markdown("**System Readiness Center**")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("PERMISSION CHECK", use_container_width=True):
                with st.spinner("Checking..."):
                    res = call_cortex(active_session, "hi", "check", model=selected_model, max_retries=1)
                    if res["success"]:
                        st.success("Access OK")
                    else:
                        st.error("Access Failed")
                        current_role = active_session.get_current_role() or "YOUR_ROLE"
                        st.code(f"GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE {current_role};", language="sql")
        
        with c2:
            if st.button("REGIONAL CHECK", use_container_width=True):
                with st.spinner("Verifying..."):
                    res = call_cortex(active_session, "hi", "check", model=selected_model, max_retries=1)
                    if res["success"]:
                        st.success(f"{selected_model} OK")
                    else:
                        st.error(f"{selected_model} Restricted")
                    
        st.info(f"Active Engine: **{selected_model}**")
        

    # Header Section (Aligned with Home Page)
    render_page_header("AI", "Cortex LLM is orchestrating your multi-tier data warehouse architecture. Sit back while the engine designs your schema, pipelines, and governance policies.", "Architect")

    # Step Definitions (Matched with orchestrator.py phases)
    steps = [
        ("architecture_strategy", "Architecture Strategy"),
        ("schema_modeling",       "Physical Schema Design"),
        ("metadata_analysis",     "Metadata & Lineage"),
        ("relationship_design",   "PK/FK Relationship Design"),
        ("pipeline_design",       "Transformation Pipelines"),
        ("governance_security",   "Governance & Security"),
        ("ddl_generation",        "DDL & Deployment SQL"),
        ("final_blueprint",       "Final Architectural Blueprint")
    ]
    
    # Progress & Console Section
    col_status, col_log = st.columns([1, 1], gap="large")
    
    with col_status:
        st.markdown("### **Progress Tracker**")
        status_placeholders = {}
        for key, label in steps:
            # Check current state to show previously completed steps
            cached = st.session_state.get(key)
            is_done = step_is_complete(key, cached)
            
            icon = "[Done]" if is_done else " (Wait)"
            color = "#10B981" if is_done else "#64748B"
            
            status_placeholders[key] = st.empty()
            status_placeholders[key].markdown(f" {icon} <span style='color: {color};'>{label}</span>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        overall_progress = st.progress(0)
        progress_text = st.empty()
    
    with col_log:
        st.markdown("### **System Logs**")
        log_box = st.empty()
        log_content = ["[SYSTEM] Ready to initialize...", "[READY] Waiting for user trigger..."]
        log_box.code("\n".join(log_content), language="bash")
    
    # Action Logic
    cta_placeholder = st.empty()
    
    # Check if we already have results (Success or Failure)
    gen_res = st.session_state.get("generation_results")
    is_running = st.session_state.get("generation_running")
    
    if gen_res and gen_res.get("success") and not is_running:
        cta_placeholder.success("Architecture Generation Complete!")
        
        c1, c2 = st.columns(2)
        if c1.button("Generate Full Reset", use_container_width=True):
            clear_all_generation_caches(steps)
            st.session_state["generation_running"] = True
            st.rerun()
            
        if c2.button("PROCEED TO DESIGN CENTER", type="primary", use_container_width=True):
            st.switch_page("pages/4_Design_Center.py")
            
    elif gen_res and not gen_res.get("success") and not is_running:
        st.error(f"Generation Failed: {gen_res.get('error')}")
        c1, c2 = st.columns(2)
        if c1.button("RETRY FROM FAILED STEP", type="primary", use_container_width=True):
            # DO NOT clear state. orchestrator.run_all will skip 'Done' steps.
            st.session_state["generation_running"] = True
            st.rerun()
        if c2.button("START OVER (RESET)", use_container_width=True):
            clear_all_generation_caches(steps)
            st.session_state["generation_running"] = True
            st.rerun()

    elif not is_running:
        if cta_placeholder.button("BEGIN ARCHITECTURAL GENERATION", type="primary", use_container_width=True):
            clear_all_generation_caches(steps)
            st.session_state["generation_running"] = True
            st.rerun()

    if st.session_state.get("generation_running"):
        with st.status("**Cortex AI Architecting...**", expanded=True) as status:
            log_container = st.empty()
            
            def update_ui(step_key, state, data=None):
                step_labels = dict(steps)
                label = step_labels.get(step_key, step_key)
                
                # Extract sub-step info (e.g. layer or batch)
                sub_info = ""
                if isinstance(data, dict):
                    if "layer" in data: sub_info = f" [{data['layer']}]"
                    elif "batch" in data: sub_info = f" [Batch {data['batch']}]"

                # 1. Update Persistent Progress Tracker (Sidebar-like list)
                if step_key in status_placeholders:
                    if state == "running":
                        status_placeholders[step_key].markdown(f"**{label}{sub_info} (Designing...)**", unsafe_allow_html=True)
                    elif state == "done":
                        status_placeholders[step_key].markdown(f"(Done) <span style='color: #10B981;'>{label} (Complete)</span>", unsafe_allow_html=True)
                    elif state == "error":
                        status_placeholders[step_key].markdown(f"(Fail) <span style='color: #EF4444;'>{label} (Failed)</span>", unsafe_allow_html=True)

                # 2. Update Main Status & Log
                if state == "running":
                    status.update(label=f"Architecting: {label}{sub_info}...", state="running")
                    with log_container:
                        # Defensive access for threaded execution
                        try:
                            current_model = st.session_state.get('selected_model', 'Default')
                        except:
                            current_model = "Active Thread"
                        st.info(f"Step: **{label}{sub_info}** | Current Engine: `{current_model}`")
                        st.write(f"Cortex is calculating optimal {label.lower()} patterns...")
                elif state == "done":
                    # Update Overall Progress Bar
                    try:
                        current_idx = [s[0] for s in steps].index(step_key) + 1
                        overall_progress.progress(current_idx / len(steps))
                        progress_text.markdown(f"**Step {current_idx} of {len(steps)}**: {label} finalized.")
                    except: pass
                    st.write(f"**{label} Design Generated.**")
                elif state == "error":
                    # Handle both string errors and response dictionaries
                    err_msg = (data.get("error") if isinstance(data, dict) else data) or "Unknown error"
                    st.error(f"Error in {label}: {err_msg}")
                    
                    # If we have raw output, show it in a debug box
                    if isinstance(data, dict) and data.get("raw"):
                        with st.expander("VIEW RAW AI OUTPUT (DEBUG)", expanded=True):
                            st.code(data["raw"], language="json")
                            st.info("Check Line 3 for missing commas or structural issues.")

            try:
                # Ensure session is alive
                valid_session = ensure_session()
                
                # OPTIMIZATION: Use existing results if this is a retry/resume
                # Only carry forward steps that are valid dicts (not None or str)
                _step_keys = [
                    "architecture_strategy", "schema_modeling",
                    "metadata_analysis", "relationship_design",
                    "pipeline_design", "governance_security",
                    "ddl_generation", "final_blueprint"
                ]
                initial_results = {}
                for _sk in _step_keys:
                    _val = st.session_state.get(_sk)
                    if isinstance(_val, dict) and _val:
                        initial_results[_sk] = _val
                
                results = run_all(
                    valid_session,
                    st.session_state["requirements"],
                    st.session_state["data_profile"],
                    model=st.session_state.get("selected_model", "claude-sonnet-4-6"),
                    status_callback=update_ui,
                    initial_results=initial_results
                )
                
                st.session_state["generation_running"] = False
                
                # Always extract outputs if they exist, even on partial failure
                outputs = results.get("outputs", {})
                if not outputs and results.get("success"):
                    outputs = results # Fallback for flat returns
                
                if outputs:
                    # Primary keys (from orchestrator) - CORRECTED TO MATCH ACTUAL OUTPUT KEYS
                    st.session_state["architecture_selection"] = outputs.get("architecture_selection") or outputs.get("architecture_strategy")
                    st.session_state["architecture_strategy"] = outputs.get("architecture_strategy") or outputs.get("architecture_selection")
                    
                    # FIX: Use "schema_modeling" (actual key) instead of non-existent "schema_design"
                    st.session_state["schema_design"] = outputs.get("schema_modeling")
                    st.session_state["schema_modeling"] = outputs.get("schema_modeling")
                    
                    st.session_state["pipeline_design"] = outputs.get("pipeline_design")
                    st.session_state["governance_security"] = outputs.get("governance_security")
                    st.session_state["ddl_generation"] = outputs.get("ddl_generation")
                    
                    # FIX: Extract metadata_analysis and relationship_design
                    st.session_state["metadata_analysis"] = outputs.get("metadata_analysis")
                    st.session_state["relationship_design"] = outputs.get("relationship_design")
                    
                    # FIX: Map final_blueprint to both keys
                    st.session_state["final_blueprint"] = outputs.get("final_blueprint")
                    st.session_state["blueprint"] = outputs.get("final_blueprint")
                    
                    # FIX: Extract documentation from final_blueprint if it exists
                    final_bp = outputs.get("final_blueprint", {})
                    if isinstance(final_bp, dict):
                        st.session_state["documentation_design"] = final_bp.get("documentation") or final_bp
                    else:
                        st.session_state["documentation_design"] = {"summary": str(final_bp)}
                    
                    # Master Contract Keys — Design Center reads from these short keys
                    st.session_state["architecture"] = outputs.get("architecture_strategy") or outputs.get("architecture_selection")
                    
                    # FIX: Use schema_modeling for schema key
                    st.session_state["schema"] = outputs.get("schema_modeling")
                    
                    st.session_state["pipeline"] = outputs.get("pipeline_design")
                    st.session_state["governance"] = outputs.get("governance_security")
                    st.session_state["artifacts"] = outputs.get("ddl_generation") or outputs.get("artifacts")
                    st.session_state["history"] = outputs.get("history") or {"version": "v1.0", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "assumptions": []}
                    
                    # VERIFICATION COMMANDS
                    print("\n[VERIFICATION] Session State Keys Set:")
                    print(f"  architecture: {bool(st.session_state.get('architecture'))}")
                    print(f"  schema: {bool(st.session_state.get('schema'))}")
                    print(f"  schema_design: {bool(st.session_state.get('schema_design'))}")
                    print(f"  schema_modeling: {bool(st.session_state.get('schema_modeling'))}")
                    print(f"  pipeline: {bool(st.session_state.get('pipeline'))}")
                    print(f"  governance: {bool(st.session_state.get('governance'))}")
                    print(f"  artifacts: {bool(st.session_state.get('artifacts'))}")
                    print(f"  blueprint: {bool(st.session_state.get('blueprint'))}")
                    print(f"  history: {bool(st.session_state.get('history'))}")
                
                if results["success"]:
                    # PERSIST TO ARCHITECTURE_STORE
                    save_project_to_store(
                        valid_session,
                        st.session_state["project_id"],
                        st.session_state["requirements"],
                        st.session_state["data_profile"],
                        outputs
                    )
                    
                    status.update(label="**Architecture Generation Complete!**", state="complete", expanded=False)
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    # Partial Save on failure to allow resume
                    partial = results.get("partial_outputs", {})
                    for k, v in partial.items():
                        if v: st.session_state[k] = v
                        
                    status.update(label="**Generation Paused/Failed**", state="error")
                    st.error(f"Error: {results.get('error')}")
                    st.session_state["generation_running"] = False
                    if st.button("RETRY FROM POINT OF FAILURE"):
                        st.session_state["generation_running"] = True
                        st.rerun()
            except Exception as e:
                status.update(label="**System Error**", state="error")
                st.error(f"Unexpected Runtime Error: {str(e)}")
                st.session_state["generation_running"] = False
                if st.button("Restart Session"):
                    st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
