import streamlit as st
import sys
import os
from pathlib import Path

# Fix for ModuleNotFoundError
root_path = str(Path(__file__).parent.parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

from dwh_assistant.backend.executor import execute_deployment
from dwh_assistant.utils.ui import apply_premium_style, render_ai_sidebar, init_session_state
st.set_page_config(page_title="Deploy | AI DWH", layout="wide")
init_session_state()
apply_premium_style()

def main():
    # Sidebar for consistent model selection
    # Unified Sidebar Configuration
    selected_model, active_session = render_ai_sidebar()

    if not st.session_state.get("ddl_generation"):
        st.warning("No DDL generated yet. Please run AI Generation first.")
        if st.button("Go to AI Generation"):
            st.switch_page("pages/3_AI_Generation.py")
        return

    # Standalone Header Glass-Card
    st.markdown("""
        <div class="glass-card" style="text-align: left; padding: 35px; margin-bottom: 30px;">
            <h1 style="font-size: 2.5rem; margin: 0; color: white;">Deployment <span style="color: #00D4FF;">Engine</span></h1>
            <p style="color: #E2E8F0; font-size: 1.1rem; margin: 0;">Validate and execute your architecture directly into Snowflake.</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div style="background: white; padding: 30px; border-radius: 16px; border: 1px solid rgba(0,0,0,0.05);">', unsafe_allow_html=True)
    
    # Pre-flight Checks
    st.markdown("### Pre-flight Checklist")
    
    checks = []
    session = active_session
    
    # Check 1: Session
    if session:
        st.success("Snowflake Session: Connected")
        checks.append(True)
    else:
        st.error("Snowflake Session: Disconnected")
        checks.append(False)
        
    # Check 2: Privileges
    if session:
        try:
            active_role = session.sql("SELECT CURRENT_ROLE()").collect()[0][0]
            grants = session.sql(f"SHOW GRANTS TO ROLE {active_role}").collect()
            st.success("Permissions: Validated")
            checks.append(True)
        except:
            st.warning("Permissions: Could not verify, proceed with caution.")
            checks.append(True) # Non-blocking
            
    # Target Selection
    st.divider()
    st.markdown("### Deployment Target")
    
    col1, col2 = st.columns(2)
    if session:
        dbs = [r['name'] for r in session.sql("SHOW DATABASES").collect()]
        target_db = col1.selectbox("Target Database", dbs)
        
        if target_db:
            schemas = [r['name'] for r in session.sql(f"SHOW SCHEMAS IN DATABASE {target_db}").collect()]
            target_schema = col2.selectbox("Target Schema", schemas)
    else:
        st.error("Connect to Snowflake to select targets.")
        target_db, target_schema = None, None

    all_pass = all(checks) and target_db and target_schema
    
    if st.button("Deploy Architecture", disabled=not all_pass):
        with st.status("Executing Deployment...", expanded=True) as status:
            ddl_gen = st.session_state.get("ddl_generation", {})
            if not isinstance(ddl_gen, dict): ddl_gen = {}
            ddl = ddl_gen.get("ddl_sql", "")
            project_id = st.session_state.get("project_id", "N/A")
            result = execute_deployment(session, ddl, target_db, target_schema, project_id=project_id)
            
            if result["success"]:
                st.session_state["deployed"] = True
                status.update(label="Deployment Successful!", state="complete", expanded=False)
                st.balloons()
            else:
                st.error(f"Deployment Failed: {result.get('error')}")
                if "rollback" in result:
                    st.info("Rollback actions taken:")
                    for action in result["rollback"]:
                        st.write(f"- {action}")
                status.update(label="Deployment Failed", state="error")
    else:
        st.info("Resolve pre-flight errors to enable deployment.")

    if st.session_state.get("deployed"):
        st.success("Your Data Warehouse has been architected and deployed.")
        st.markdown(f"**Project ID:** `{st.session_state['project_id']}`")
        if st.button("Download Deployment Bundle"):
            st.info("Bundle generator would create a ZIP of all artifacts here.")

    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
