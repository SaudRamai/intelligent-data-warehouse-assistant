import streamlit as st
import sys
import os
from pathlib import Path

# Fix for ModuleNotFoundError
root_path = str(Path(__file__).parent.parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

from dwh_assistant.backend.snowflake import get_snowflake_session
from dwh_assistant.utils.ui import apply_premium_style, render_ai_sidebar, init_session_state, render_page_header
st.set_page_config(page_title="Requirement Form | AI DWH", layout="wide")
init_session_state()
apply_premium_style()

def show_section_nav(current_section):
    """Shows the high-level progress in the sidebar with clean professional styling."""
    
    selected_model, active_session = render_ai_sidebar()
    st.sidebar.divider()

    st.sidebar.markdown("### PROJECT ROADMAP")
    sections = [
        ("Objectives", "STEP 1"),
        ("Data Sources", "STEP 2"),
        ("SLA & Depth", "STEP 3"),
        ("Governance", "STEP 4"),
        ("Strategy", "STEP 5")
    ]
    
    for i, (name, step) in enumerate(sections):
        step_num = i + 1
        if step_num < current_section:
            st.sidebar.markdown(f"""
                <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 15px; color: #38BDF8;'>
                    <span style='font-weight: 600; font-size: 0.8rem;'>DONE</span>
                    <span style='font-weight: 500;'>{name}</span>
                </div>
            """, unsafe_allow_html=True)
        elif step_num == current_section:
            st.sidebar.markdown(f"""
                <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 15px; color: #002244; background: #E0F2FE; padding: 12px; border-radius: 8px; border-left: 5px solid #002244;'>
                    <span style='font-weight: 700; font-size: 0.8rem;'>{step}</span>
                    <span style='font-weight: 700;'>{name}</span>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.sidebar.markdown(f"""
                <div style='display: flex; align-items: center; gap: 10px; margin-bottom: 15px; color: #94A3B8;'>
                    <span style='font-weight: 600; font-size: 0.8rem;'>WAIT</span>
                    <span>{name}</span>
                </div>
            """, unsafe_allow_html=True)
    
    st.sidebar.divider()
    progress = (current_section - 1) * 20
    st.sidebar.markdown(f"**COMPLETION**: {progress}%")
    st.sidebar.progress(progress / 100)

def main():
    if "current_section" not in st.session_state:
        st.session_state["current_section"] = 1
    
    section = st.session_state["current_section"]
    
    # Update Sidebar Navigation
    show_section_nav(section)
    
    # Header Section
    render_page_header("Requirement", f"Configuration Step {section} of 5: Establishing architectural guardrails.", "Form")

    # Content Area
    if "form_buffer" not in st.session_state:
        st.session_state["form_buffer"] = {}
    
    if section == 1:
        st.markdown("### STRATEGIC OBJECTIVES")
        st.markdown("<p style='color: #64748B;'>Define business drivers, industry context, and success metrics.</p>", unsafe_allow_html=True)
        st.divider()
        
        c1, c2 = st.columns(2, gap="large")
        with c1:
            industry = st.selectbox("Industry Sector", ["Retail", "Finance", "Healthcare", "SaaS", "Manufacturing", "Logistics", "Education", "Other"])
            
            stakeholder_options = ["Finance", "Marketing", "Executives", "Operations", "Data Team", "External"]
            existing_stakeholders = st.session_state["form_buffer"].get("consumers", [])
            valid_stakeholders = [s for s in existing_stakeholders if s in stakeholder_options]
            
            consumers = st.multiselect("Data Stakeholders", stakeholder_options,
                                     default=valid_stakeholders)
        
        with c2:
            goals_options = ["Revenue Growth", "Cost Reduction", "Compliance", "Customer Analytics", "Operational Efficiency"]
            existing_goals = st.session_state["form_buffer"].get("primary_goal", [])
            valid_goals = [g for g in existing_goals if g in goals_options]
            
            primary_goal = st.multiselect("Strategic Goals", goals_options,
                                        default=valid_goals)
            kpis = st.text_area("Key Metrics (KPIs)", value=st.session_state["form_buffer"].get("kpis", ""), height=68)
        
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns([3, 1])
        if col2.button("NEXT STEP", width='stretch'):
            if industry and primary_goal:
                st.session_state["form_buffer"].update({"industry": industry, "primary_goal": primary_goal, "kpis": kpis, "consumers": consumers})
                st.session_state["current_section"] += 1
                st.rerun()
            else:
                st.error("Industry and Strategic Goals are required.")

    elif section == 2:
        st.markdown("### DATA SOURCES")
        st.markdown("<p style='color: #64748B;'>Map existing infrastructure and profiling targets.</p>", unsafe_allow_html=True)
        st.divider()
        
        c1, c2 = st.columns(2, gap="large")
        with c1:
            systems_options = ["CRM", "ERP", "POS", "Flat Files", "REST API", "Streaming", "Other"]
            existing_systems = st.session_state["form_buffer"].get("source_systems", [])
            valid_defaults = [s for s in existing_systems if s in systems_options]
            
            source_systems = st.multiselect("Source Systems", systems_options,
                                          default=valid_defaults)
            volume = st.select_slider("Data Volume", options=["<1GB", "1-10GB", "10-100GB", ">100GB"],
                                     value=st.session_state["form_buffer"].get("estimated_volume", "1-10GB"))

        with c2:
            has_tables = st.radio("Live Tables Available?", ["Yes", "No"], index=0, horizontal=True)
            sample_size = st.slider("Profiling Depth (Rows)", 5, 100, value=st.session_state["form_buffer"].get("profile_sample_size", 10))

        if has_tables == "Yes":
            data_location = "My Snowflake Tables"
            session = st.session_state.get("snowflake_session")
            selected_db = selected_schema = selected_tables = None
            
            if session:
                st.markdown("<div style='background: #F1F5F9; padding: 20px; border-radius: 8px; margin: 20px 0;'>", unsafe_allow_html=True)
                sc1, sc2 = st.columns(2)
                try:
                    dbs = [r['name'] for r in session.sql("SHOW DATABASES").collect()]
                    selected_db = sc1.selectbox("Database", dbs)
                    if selected_db:
                        schemas = [r['name'] for r in session.sql(f"SHOW SCHEMAS IN DATABASE {selected_db}").collect()]
                        selected_schema = sc2.selectbox("Schema", schemas)
                        if selected_schema:
                            tables = [r['name'] for r in session.sql(f"SHOW TABLES IN SCHEMA {selected_db}.{selected_schema}").collect()]
                            selected_tables = st.multiselect("Select Tables", tables)
                except Exception as e:
                    st.error(f"Snowflake metadata error: {str(e)}")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("No active Snowflake session.")
        else:
            no_path_option = st.radio("Alternative Path", ["Industry Template", "Sample Data (TPCH)", "Synthetic Generator"], horizontal=True)
            data_location = {"Industry Template": "Use Industry Template", "Sample Data (TPCH)": "Use Snowflake Sample Data", "Synthetic Generator": "Generate Synthetic Data"}[no_path_option]
        
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        if col1.button("← PREVIOUS"):
            st.session_state["current_section"] -= 1
            st.rerun()
        if col2.button("NEXT: SLA", type="primary", width='stretch'):
            if data_location == "My Snowflake Tables":
                if not selected_db or not selected_schema or not selected_tables:
                    st.error("Please select a Database, Schema, and at least one Table.")
                    return
                st.session_state["form_buffer"].update({"db": selected_db, "schema": selected_schema, "tables": selected_tables})
            
            st.session_state["form_buffer"].update({"source_systems": source_systems, "data_location": data_location, "estimated_volume": volume, "profile_sample_size": sample_size})
            st.session_state["current_section"] += 1
            st.rerun()

    elif section == 3:
        st.markdown("### SLA & FRESHNESS")
        st.markdown("<p style='color: #64748B;'>Determine data latency and uptime requirements.</p>", unsafe_allow_html=True)
        st.divider()
        
        c1, c2 = st.columns(2, gap="large")
        with c1:
            refresh = st.select_slider("Refresh Frequency", options=["Real-time", "Hourly", "Daily", "Weekly", "Monthly"], value="Daily")
            latency = st.slider("Latency Tolerance (Hrs)", 0, 24, value=4)
        
        with c2:
            sla = st.radio("Uptime SLA", ["99.9%", "99.5%", "Best Effort"], horizontal=True)
            history = st.selectbox("Retention Depth", ["6 months", "1 year", "3 years", "Unlimited"])
        
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        if col1.button("← PREVIOUS"):
             st.session_state["current_section"] -= 1
             st.rerun()
        if col2.button("NEXT: GOVERNANCE", type="primary", width='stretch'):
            st.session_state["form_buffer"].update({"refresh_frequency": refresh, "history_depth": history, "uptime_sla": sla, "latency_tolerance": latency})
            st.session_state["current_section"] += 1
            st.rerun()

    elif section == 4:
        st.markdown("### COMPLIANCE & SECURITY")
        st.markdown("<p style='color: #64748B;'>Define security policies and regulatory frameworks.</p>", unsafe_allow_html=True)
        st.divider()
        
        compliance_options = ["GDPR", "HIPAA", "SOC2", "PCI-DSS", "None"]
        existing_compliance = st.session_state["form_buffer"].get("compliance", ["None"])
        valid_compliance = [c for c in existing_compliance if c in compliance_options]
        
        compliance = st.multiselect("Frameworks", compliance_options, default=valid_compliance)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Field Controls**")
        c1, c2, c3 = st.columns(3)
        rls = c1.checkbox("Row-Level Security")
        masking = c2.checkbox("Dynamic Masking")
        geo = c3.selectbox("Data Sovereignty", ["None", "US", "EU", "Other"])
        
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        if col1.button("← PREVIOUS"):
             st.session_state["current_section"] -= 1
             st.rerun()
        if col2.button("NEXT: STRATEGY", type="primary", width='stretch'):
            st.session_state["form_buffer"].update({"compliance": compliance, "row_level_security": rls, "column_masking": masking, "geo_restriction": geo})
            st.session_state["current_section"] += 1
            st.rerun()

    elif section == 5:
        st.markdown("### DESIGN STRATEGY")
        st.markdown("<p style='color: #64748B;'>Select technical preferences for AI generation.</p>", unsafe_allow_html=True)
        st.divider()
        
        c1, c2 = st.columns(2, gap="large")
        with c1:
            priority = st.radio("Optimization", ["Performance", "Cost", "Speed", "Balanced"], index=3, horizontal=True)
            architecture = st.selectbox("Warehouse Architecture", ["AI Recommendation", "Three-tier Architecture", "Cloud Data Warehouse", "Lakehouse Architecture", "Medallion Architecture", "Modern ELT Architecture"], index=0)
            modeling = st.selectbox("Data Modeling Paradigm", ["AI Recommendation", "Star Schema", "Snowflake Schema", "Fact Constellation / Galaxy", "Data Vault"], index=0)
        
        with c2:
            skill = st.radio("Team Skill", ["Junior", "Mid", "Senior"], horizontal=True)
            budget = st.select_slider("Budget Tier", options=["Starter", "Growth", "Enterprise"], value="Growth")
        
        st.markdown("<br>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        if col1.button("← PREVIOUS"):
             st.session_state["current_section"] -= 1
             st.rerun()
        if col2.button("INITIALIZE ARCHITECT", type="primary", width='stretch'):
            st.session_state["form_buffer"].update({
                "priority": priority, 
                "team_skill": skill, 
                "architecture_preference": architecture,
                "modeling_preference": modeling, 
                "budget_tier": budget
            })
            st.session_state["requirements"] = st.session_state["form_buffer"]
            st.session_state["form_complete"] = True
            st.switch_page("pages/2_Data_Profile.py")

if __name__ == "__main__":
    main()
