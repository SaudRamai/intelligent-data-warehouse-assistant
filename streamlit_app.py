import streamlit as st
import uuid
import sys
import os
from pathlib import Path

import logging
import warnings

logging.getLogger("streamlit.runtime.scriptrunner").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
warnings.filterwarnings("ignore", category=UserWarning, module="streamlit")

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

logging.getLogger().addFilter(SuppressWebSocketClosedError())
for logger_name in ["tornado.application", "tornado.general", "streamlit.web.server.browser_websocket_handler", "streamlit"]:
    logging.getLogger(logger_name).addFilter(SuppressWebSocketClosedError())

from dwh_assistant.utils.ui import apply_premium_style, render_ai_sidebar, init_session_state, render_page_header, reset_project_state
from dwh_assistant.backend.snowflake import get_snowflake_session, ensure_session, get_available_cortex_models

st.set_page_config(page_title="Industrial DWH Assistant", layout="wide", page_icon="❄️")
init_session_state()
apply_premium_style()

def main():
    selected_model, active_session = render_ai_sidebar(show_model_selector=False, show_logo=False, show_big_logo=True)
    
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
    
    with st.sidebar:
        conn_state = "Connected" if st.session_state.get("snowflake_connected") else "Offline"
        color = "#006da8" if conn_state == "Connected" else "#8c1c14"
        st.markdown(f"<div style='margin-top: -10px; margin-bottom: 10px;'><span style='color: #64748B; font-size: 0.9rem; font-weight: 600;'>Snowflake Status</span><br><strong style='font-size: 1.2rem; color: {color};'>{conn_state}</strong></div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('''
            <div class="glass-card-white" style="height: 200px; text-align: center; font-family: 'Outfit', sans-serif;">
                <h3 style="margin-top: 10px; color: #002244; font-weight: 700;">AI-Driven Design</h3>
                <p style="color: #64748B; font-size: 1.05rem; font-weight: 400;">Automated, intelligent architecture specifically tailored for your Snowflake environment.</p>
            </div>
        ''', unsafe_allow_html=True)
    with c2:
        st.markdown('''
            <div class="glass-card-white" style="height: 200px; text-align: center; font-family: 'Outfit', sans-serif;">
                <h3 style="margin-top: 10px; color: #002244; font-weight: 700;">End-to-End DDL</h3>
                <p style="color: #64748B; font-size: 1.05rem; font-weight: 400;">Instantly generates ready-to-deploy schema structures, tables, and Snowflake tasks.</p>
            </div>
        ''', unsafe_allow_html=True)
    with c3:
        st.markdown('''
            <div class="glass-card-white" style="height: 200px; text-align: center; font-family: 'Outfit', sans-serif;">
                <h3 style="margin-top: 10px; color: #002244; font-weight: 700;">Secure & Governed</h3>
                <p style="color: #64748B; font-size: 1.05rem; font-weight: 400;">Built-in best practices for RBAC, dynamic masking policies, and robust data lineage.</p>
            </div>
        ''', unsafe_allow_html=True)
        
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown('''
        <div style="display: flex; justify-content: space-between; align-items: center; background: linear-gradient(90deg, #F8FAFC 0%, #F1F5F9 100%); padding: 25px 50px; border-radius: 15px; border: 1px solid #E2E8F0; font-family: 'Outfit', sans-serif;">
            <div style="text-align: center; color: #002244;"><strong style="font-size: 1.1rem; letter-spacing: 0.5px;">1. Define Needs</strong><br><span style="font-size: 0.95rem; color: #64748B; font-weight: 400;">Fill Intake Form</span></div>
            <div style="color: #94A3B8; font-size: 1.5rem; font-weight: 300;">→</div>
            <div style="text-align: center; color: #002244;"><strong style="font-size: 1.1rem; letter-spacing: 0.5px;">2. Profile Data</strong><br><span style="font-size: 0.95rem; color: #64748B; font-weight: 400;">Analyze Sources</span></div>
            <div style="color: #94A3B8; font-size: 1.5rem; font-weight: 300;">→</div>
            <div style="text-align: center; color: #002244;"><strong style="font-size: 1.1rem; letter-spacing: 0.5px;">3. AI Generation</strong><br><span style="font-size: 0.95rem; color: #64748B; font-weight: 400;">Design Architecture</span></div>
            <div style="color: #94A3B8; font-size: 1.5rem; font-weight: 300;">→</div>
            <div style="text-align: center; color: #002244;"><strong style="font-size: 1.1rem; letter-spacing: 0.5px;">4. Design Center</strong><br><span style="font-size: 0.95rem; color: #64748B; font-weight: 400;">Refine & Export</span></div>
        </div>
    ''', unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("### Project Actions")
    
    action_col1, action_col2 = st.columns(2)
    
    with action_col1:
        st.markdown('''
            <div class="glass-card-white" style="margin-bottom: 20px; font-family: 'Outfit', sans-serif;">
                <h4 style="margin-top: 0; font-weight: 700; font-size: 1.3rem;">New Project</h4>
                <p style="color: #64748B; font-size: 0.95rem; font-weight: 400;">Start building a new Data Warehouse architecture from scratch or continue your active session.</p>
            </div>
        ''', unsafe_allow_html=True)
        if not st.session_state["form_complete"]:
            if st.button("START NEW PROJECT", type="primary", use_container_width=True):
                reset_project_state()
                st.switch_page("pages/1_Intake_Form.py")
        else:
            st.info(f"Active Project: `{st.session_state['project_id']}`")
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("CONTINUE DESIGN", type="primary", use_container_width=True):
                    st.switch_page("pages/4_Design_Center.py")
            with col_btn2:
                if st.button("DISCARD & RESTART", use_container_width=True):
                    reset_project_state()
                    st.switch_page("pages/1_Intake_Form.py")

    with action_col2:
        st.markdown('''
            <div class="glass-card-white" style="margin-bottom: 20px; font-family: 'Outfit', sans-serif;">
                <h4 style="margin-top: 0; font-weight: 700; font-size: 1.3rem;">Load Saved Project</h4>
                <p style="color: #64748B; font-size: 0.95rem; font-weight: 400;">Resume a previously saved architectural design from your Snowflake storage.</p>
            </div>
        ''', unsafe_allow_html=True)
        
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
