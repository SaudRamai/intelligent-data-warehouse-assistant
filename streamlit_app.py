import streamlit as st
import uuid
import sys
import os
from pathlib import Path

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

st.set_page_config(page_title="Industrial DWH Assistant", layout="wide", page_icon="🏭")
init_session_state()
apply_premium_style()

def main():
    selected_model, active_session = render_ai_sidebar(show_model_selector=False, show_logo=True)
    
    if not st.session_state["project_id"]:
        st.session_state["project_id"] = str(uuid.uuid4())
    
    if not st.session_state.get("snowflake_connected"):
        try:
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
        
        
        if st.button("Retry Connection"):
            st.rerun()

    render_page_header("Industrial", "Autonomous AI Architect for Snowflake.", "DWH Assistant")
    
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('''
            <div class="glass-card-white" style="height: 230px;">
                <h3 style="margin-top: 0; color: #002244;">🤖 AI-Driven Design</h3>
                <p style="color: #64748B; font-size: 1.1rem;">Automated, intelligent data warehouse architecture specifically tailored for your Snowflake environment.</p>
            </div>
        ''', unsafe_allow_html=True)
    with c2:
        st.markdown('''
            <div class="glass-card-white" style="height: 230px;">
                <h3 style="margin-top: 0; color: #002244;">⚡ End-to-End DDL</h3>
                <p style="color: #64748B; font-size: 1.1rem;">Instantly generates ready-to-deploy schema structures, tables, and Snowflake tasks.</p>
            </div>
        ''', unsafe_allow_html=True)
    with c3:
        st.markdown('''
            <div class="glass-card-white" style="height: 230px;">
                <h3 style="margin-top: 0; color: #002244;">🛡️ Secure & Governed</h3>
                <p style="color: #64748B; font-size: 1.1rem;">Built-in best practices for RBAC, dynamic masking policies, and robust data lineage.</p>
            </div>
        ''', unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    st.divider()
    st.markdown("### Project Actions")
    st.markdown("<br>", unsafe_allow_html=True)
    
    action_col1, action_col2 = st.columns(2)
    
    with action_col1:
        with st.container(border=True, height=300):
            st.markdown("#### New Project")
            st.markdown("<p style='color: #64748B;'>Start building a new Data Warehouse architecture from scratch or continue your active session.</p>", unsafe_allow_html=True)
            
            if not st.session_state["form_complete"]:
                if st.button("Start New Project", type="primary", use_container_width=True):
                    reset_project_state()
                    st.switch_page("pages/1_Intake_Form.py")
            else:
                st.info(f"Active Project: `{st.session_state['project_id']}`")
                if st.button("Continue Current Design", type="primary", use_container_width=True):
                    st.switch_page("pages/4_Design_Center.py")
                if st.button("Discard & Start Fresh", use_container_width=True):
                    reset_project_state()
                    st.switch_page("pages/1_Intake_Form.py")

    with action_col2:
        with st.container(border=True, height=300):
            st.markdown("#### Load Saved Project")
            st.markdown("<p style='color: #64748B;'>Resume a previously saved architectural design from your Snowflake storage.</p>", unsafe_allow_html=True)
            
            if st.session_state.get("snowflake_connected"):
                from dwh_assistant.backend.snowflake import get_all_projects, load_project_by_id
                projects = get_all_projects(st.session_state["snowflake_session"])
                
                if projects:
                    p_list = [f"{p['ID']} ({p['STATUS']} - {p['CREATED_AT'].strftime('%Y-%m-%d')})" for p in projects]
                    selected_p = st.selectbox("Select Project to Resume", ["-- Select a Project --"] + p_list, label_visibility="collapsed")
                    
                    if selected_p != "-- Select a Project --":
                        p_id = selected_p.split(" ")[0]
                        if st.button("LOAD PROJECT", use_container_width=True):
                            with st.spinner("Fetching from ARCHITECTURE_STORE..."):
                                p_data = load_project_by_id(st.session_state["snowflake_session"], p_id)
                                if p_data:
                                    for k, v in p_data.items():
                                        st.session_state[k] = v
                                    st.session_state["form_complete"] = True
                                    st.success(f"Project {p_id} Loaded!")
                                    st.rerun()
                else:
                    st.info("No saved projects found in your Snowflake account.")
            else:
                st.warning("Connect to Snowflake using the sidebar to access your saved projects.")

if __name__ == "__main__":
    main()
