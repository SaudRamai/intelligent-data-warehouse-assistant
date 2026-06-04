import streamlit as st
import uuid
from dwh_assistant.backend.snowflake import get_available_cortex_models, ensure_session
from dwh_assistant.components.state_config import get_default_state, STATE_PREFIXES_TO_CLEAN, STATE_EXACT_KEYS_TO_CLEAN
from dwh_assistant.components.styles import PREMIUM_CSS

def init_session_state():
    """Initializes all session state keys for the DWH Assistant."""
    defaults = get_default_state()
    for key, value in defaults.items():
        if key not in st.session_state: st.session_state[key] = value

def reset_project_state():
    """Clears project-specific data to start fresh."""
    st.session_state["project_id"] = str(uuid.uuid4())
    st.session_state["requirements"] = {}
    st.session_state["data_profile"] = {}
    st.session_state["generation_results"] = {}
    st.session_state["form_complete"] = False
    st.session_state["current_section"] = 1
    st.session_state["form_buffer"] = {}
    
    # Clean all generation artifacts, UI sliders, toggles, editors and cached keys
    keys_to_delete = []
    for k in list(st.session_state.keys()):
        if any(p in k for p in STATE_PREFIXES_TO_CLEAN) or k in STATE_EXACT_KEYS_TO_CLEAN:
            keys_to_delete.append(k)
            
    for k in keys_to_delete:
        del st.session_state[k]

def apply_premium_style():
    """Applies the unified, glass-morphism aesthetic to the current page."""
    st.markdown(PREMIUM_CSS, unsafe_allow_html=True)

def render_page_header(title: str, subtitle: str, highlight: str = ""):
    """Renders a unified header with the first word (title) in white."""
    st.markdown(f"""
        <div class="header-banner">
            <h1 style="font-size: 3.5rem; font-weight: 800; margin: 0; letter-spacing: -1.5px;">
                <span style="color: #FFFFFF;">{title}</span> <span class="text-gradient">{highlight}</span>
            </h1>
            <p style="font-size: 1.25rem; color: #94a3b8; max-width: 800px; margin-top: 15px; line-height: 1.6; font-weight: 400;">
                {subtitle}
            </p>
        </div>
    """, unsafe_allow_html=True)

def render_ai_sidebar(show_model_selector: bool = True, show_logo: bool = False):
    """Renders the centralized AI Engine selector with connectivity validation."""
    
    import os
    logo_path = "assets/logo.png"
    
    # Try to use st.logo if available, otherwise just use sidebar image
    if show_logo and os.path.exists(logo_path):
        try:
            st.logo(logo_path)
        except AttributeError:
            pass

    with st.sidebar:
        if show_logo and os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
        if show_model_selector:
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
        
        if show_model_selector:
            selected_model = st.selectbox("Active Engine", available_models, index=def_idx, key="global_model_selector")
            if st.session_state.get("selected_model") != selected_model:
                st.session_state["selected_model"] = selected_model
        else:
            selected_model = current_model
            
        st.divider()
        status_color = "#006da8" if active_session else "#8c1c14"
        if active_session:
            status_text = "● READY"
            st.markdown(f"**Status**: <span style='color: {status_color};'>{status_text}</span>", unsafe_allow_html=True)
        else:
            status_text = "● OFFLINE"
            st.markdown(f"**Status**: <span class='status-offline'>{status_text}</span>", unsafe_allow_html=True)
        
        if show_model_selector:
            st.markdown(f"**Model**: `{selected_model}`")
            
    return selected_model, active_session
