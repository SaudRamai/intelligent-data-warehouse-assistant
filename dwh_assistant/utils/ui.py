import streamlit as st
import uuid
from dwh_assistant.backend.snowflake import get_available_cortex_models, ensure_session

# --- 1. SESSION STATE MANAGEMENT ---

def init_session_state():
    """Initializes all session state keys for the DWH Assistant."""
    defaults = {
        "snowflake_session": None, "snowflake_connected": False, "requirements": {},
        "form_complete": False, "data_profile": {}, "profile_source": None,
        "selected_model": "claude-sonnet-4-6", "generation_running": False,
        "generation_results": {}, "project_id": str(uuid.uuid4())
    }
    for key, value in defaults.items():
        if key not in st.session_state: st.session_state[key] = value

def reset_project_state():
    """Clears project-specific data to start fresh."""
    st.session_state["project_id"] = str(uuid.uuid4())
    for key in ["requirements", "data_profile", "generation_results"]:
        st.session_state[key] = {}
    st.session_state["form_complete"] = False
    # Clear flow caches
    for k in list(st.session_state.keys()):
        if any(p in k for p in ["flow_state_", "mini_erd_", "dag_state_"]): del st.session_state[k]

# --- 2. PREMIUM STYLING ---

def apply_premium_style():
    """Applies the unified, glass-morphism aesthetic to the current page."""
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
            html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
            h1, h2, h3, h4, h5, h6 { color: #002244 !important; }
            .glass-card {
                background: rgba(0, 34, 68, 0.8); /* Navy Blue Glass */
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
                color: #FFFFFF; /* White text for dark cards */
            }
            .glass-card-white {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(0, 34, 68, 0.1);
                border-radius: 16px;
                padding: 24px;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.1);
                color: #002244; /* Navy Blue text for white cards */
            }
            .header-banner {
                background: rgba(0, 34, 68, 0.9); /* Deep Navy Glass */
                backdrop-filter: blur(15px);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 20px;
                padding: 50px 40px;
                margin-bottom: 40px;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            }
            .header-banner, .glass-card, .glass-card-white {
                position: relative;
                overflow: hidden;
            }
            .header-banner::after, .glass-card::after, .glass-card-white::after {
                content: "";
                position: absolute;
                top: -50%;
                left: -60%;
                width: 20%;
                height: 200%;
                background: rgba(255, 255, 255, 0.1);
                transform: rotate(30deg);
                animation: shine 4s infinite;
            }
            @keyframes shine {
                0% { left: -60%; }
                20% { left: 120%; }
                100% { left: 120%; }
            }
            .accent-text { color: #38BDF8; font-weight: 600; }
        </style>
    """, unsafe_allow_html=True)

def render_page_header(title: str, subtitle: str, highlight: str = ""):
    """Renders a unified header with the first word (title) in white."""
    st.markdown(f"""
        <div class="header-banner">
            <h1 style="font-size: 3.5rem; font-weight: 800; margin: 0; letter-spacing: -1.5px;">
                <span style="color: #FFFFFF;">{title}</span> <span style="color: #38BDF8;">{highlight}</span>
            </h1>
            <p style="font-size: 1.25rem; color: #E2E8F0; max-width: 800px; margin-top: 15px; line-height: 1.6;">
                {subtitle}
            </p>
        </div>
    """, unsafe_allow_html=True)

# --- 3. SIDEBAR COMPONENTS ---

def render_ai_sidebar():
    """Renders the centralized AI Engine selector with connectivity validation."""
    with st.sidebar:
        st.markdown("### AI ENGINE")
        try:
            active_session = ensure_session()
            st.session_state["snowflake_connected"] = True
        except Exception as e:
            active_session = None
            st.session_state["snowflake_connected"] = False
            st.warning(f"Offline Mode: {str(e)[:60]}")
            
        # Get fallback models list if offline
        if active_session:
            available_models = get_available_cortex_models(active_session)
        else:
            from dwh_assistant.backend.snowflake import MODEL_REGISTRY
            available_models = [m["id"] for m in MODEL_REGISTRY]
            
        current_model = st.session_state.get("selected_model", "claude-sonnet-4-6")
        def_idx = available_models.index(current_model) if current_model in available_models else 0
        
        selected_model = st.selectbox("Active Engine", available_models, index=def_idx, key="global_model_selector")
        if st.session_state.get("selected_model") != selected_model:
            st.session_state["selected_model"] = selected_model
            
        st.divider()
        status_color = "#10B981" if active_session else "#EF4444"
        status_text = "● READY" if active_session else "● OFFLINE"
        st.markdown(f"**Status**: <span style='color: {status_color};'>{status_text}</span>", unsafe_allow_html=True)
        st.markdown(f"**Model**: `{selected_model}`")
    return selected_model, active_session
