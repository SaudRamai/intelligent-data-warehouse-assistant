import streamlit as st
import uuid
import sys
import os
from pathlib import Path

# Fix for ModuleNotFoundError when running from inside the package
root_path = str(Path(__file__).parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

import logging
import warnings

# Aggressively mute the "missing ScriptRunContext" warning globally
logging.getLogger("streamlit.runtime.scriptrunner").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", category=UserWarning, module="streamlit")

# Custom logging filter to suppress WebSocketClosedError tracebacks and logs
class SuppressWebSocketClosedError(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        if "WebSocketClosedError" in message:
            return False
        if record.exc_info:
            exc_type, _, _ = record.exc_info
            if exc_type:
                exc_name = getattr(exc_type, "__name__", "")
                if "WebSocketClosedError" in exc_name:
                    return False
                try:
                    import tornado.websocket
                    if issubclass(exc_type, tornado.websocket.WebSocketClosedError):
                        return False
                except Exception:
                    pass
        return True

# Apply the filter to suppress noisy disconnect tracebacks
logging.getLogger().addFilter(SuppressWebSocketClosedError())
for logger_name in ["tornado.application", "tornado.general", "streamlit.web.server.browser_websocket_handler", "streamlit"]:
    logging.getLogger(logger_name).addFilter(SuppressWebSocketClosedError())

from dwh_assistant.utils.ui import apply_premium_style, render_ai_sidebar, init_session_state, render_page_header, reset_project_state
from dwh_assistant.backend.snowflake import get_snowflake_session, check_connection, ensure_session, get_available_cortex_models

# Page Config
st.set_page_config(page_title="Industrial DWH Assistant", layout="wide", page_icon="🏗️")
init_session_state()
apply_premium_style()

# App Navigation & Auth
def main():
    # Sidebar Navigation and Connectivity Check
    selected_model, active_session = render_ai_sidebar()
    
    # Generate Project ID if not exists
    if not st.session_state["project_id"]:
        st.session_state["project_id"] = str(uuid.uuid4())
    
    # 2. Snowflake Connection Check (With Circuit Breaker)
    if not st.session_state.get("snowflake_connected"):
        try:
            # ensure_session will check the local lockout file first
            session = ensure_session()
            st.session_state["snowflake_session"] = session
            st.session_state["snowflake_connected"] = True
            st.sidebar.success("Connected to Snowflake")
        except Exception as e:
            st.session_state["snowflake_connected"] = False
            err_msg = str(e).lower()
            
            if "please wait" in err_msg and "error:" in err_msg:
                st.sidebar.error("Snowflake: Connection Cooldown")
                st.error(f"{e}")
            elif "locked" in err_msg:
                st.error("SNOWFLAKE ACCOUNT LOCKED: Snowflake has suspended your account due to multiple failed login attempts. Please wait 15-30 minutes before trying again.")
            else:
                st.sidebar.error("Snowflake: Connection Blocked")
                st.error(f"Snowflake Authentication Error: {e}")
        
        # provide a way to manual reset if failed
        from dwh_assistant.backend.snowflake import LOCKOUT_FILE
        if LOCKOUT_FILE.exists():
            st.warning("GLOBAL LOCKOUT ACTIVE: To protect your account, all login attempts are suspended for 5 minutes.")
            if st.button("I HAVE FIXED CREDENTIALS - RESET NOW"):
                LOCKOUT_FILE.unlink(missing_ok=True)
                st.rerun()
        
        st.info("Check your credentials in `.streamlit/secrets.toml` or verify your Snowflake account status.")

    # 3. Main Landing UI
    render_page_header("Industrial", "Autonomous AI Architect for Snowflake.", "DWH Assistant")
    
    st.markdown('<div style="text-align: left; margin-top: 10px;">', unsafe_allow_html=True)
    
    # 4. Project Persistence Layer
    if st.session_state.get("snowflake_connected"):
        st.divider()
        st.markdown("### Project Management")
        
        from dwh_assistant.backend.snowflake import get_all_projects, load_project_by_id
        projects = get_all_projects(st.session_state["snowflake_session"])
        
        if projects:
            p_list = [f"{p['ID']} ({p['STATUS']} - {p['CREATED_AT'].strftime('%Y-%m-%d')})" for p in projects]
            selected_p = st.selectbox("Resume Existing Project", ["-- Select a Project --"] + p_list)
            
            if selected_p != "-- Select a Project --":
                p_id = selected_p.split(" ")[0]
                if st.button("LOAD PROJECT"):
                    with st.spinner("Fetching from ARCHITECTURE_STORE..."):
                        p_data = load_project_by_id(st.session_state["snowflake_session"], p_id)
                        if p_data:
                            # Map to session state
                            for k, v in p_data.items():
                                st.session_state[k] = v
                            st.session_state["form_complete"] = True
                            st.success(f"Project {p_id} Loaded Successfully!")
                            st.rerun()
        else:
            st.info("No saved projects found in Snowflake. Start a new one below.")

    st.markdown("<br>", unsafe_allow_html=True)
    
    if not st.session_state["form_complete"]:
        if st.button("Start New Project", type="primary"):
            reset_project_state()
            st.switch_page("pages/1_Intake_Form.py")
    else:
        st.info(f"Active Project: `{st.session_state['project_id']}`")
        c1, c2 = st.columns(2)
        if c1.button("Continue Current Design", width='stretch'):
            st.switch_page("pages/4_Design_Center.py")
        if c2.button("Start Fresh Project", width='stretch'):
            reset_project_state()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
