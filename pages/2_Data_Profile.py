import streamlit as st
import pandas as pd
from dwh_assistant.backend.snowflake import ensure_session
from dwh_assistant.backend.executor import profile_sources
from dwh_assistant.utils.data_registry import get_template, get_tpch_sample_config
from dwh_assistant.utils.ui import apply_premium_style, render_ai_sidebar, render_page_header

st.set_page_config(page_title="Data Profile | AI DWH", layout="wide")
apply_premium_style()

def main():
    # Sidebar for consistent model selection
    selected_model, active_session = render_ai_sidebar()
    st.divider()

    if not st.session_state.get("form_complete"):
        st.warning("Please complete the Intake Form first.")
        if st.button("Go to Intake Form"):
            st.switch_page("pages/1_Intake_Form.py")
        return

    # Standalone Header Glass-Card
    render_page_header("Data", "Scanning source metadata and sampling content to inform architectural models.", "Intelligence")
    
    reqs = st.session_state["requirements"]
    location = reqs.get("data_location")
    active_session = ensure_session()
    session = active_session
    
    profile_data = None
    
    # Using a container for the "work" area
    work_area = st.container()
    
    with st.spinner("Analyzing source patterns and classifying data types..."):
        if location == "My Snowflake Tables":
            db = reqs.get("db")
            schema = reqs.get("schema")
            tables = reqs.get("tables")
            
            if not session:
                st.error("Snowflake Session Lost. Please refresh or reconnect in the sidebar.")
            elif not tables:
                st.error("No tables selected for profiling. Please return to the Intake Form.")
            else:
                limit = reqs.get("profile_sample_size", 10)
                profile_data = profile_sources(session, db, schema, tables, limit=limit)
                st.session_state["profile_source"] = "live"
        
        elif location == "Use Snowflake Sample Data":
            config = get_tpch_sample_config(reqs.get("industry"))
            if session:
                limit = reqs.get("profile_sample_size", 10)
                profile_data = profile_sources(session, config["database"], config["schema"], config["tables"], limit=limit)
                st.session_state["profile_source"] = "tpch"
            else:
                st.error("Snowflake connection required for sample data.")
                
        elif location == "Use Industry Template":
            profile_data = get_template(reqs.get("industry"))
            st.session_state["profile_source"] = "template"
            
        elif location == "Generate Synthetic Data":
            profile_data = get_template(reqs.get("industry")) 
            st.session_state["profile_source"] = "synthetic"

    if profile_data:
        st.session_state["data_profile"] = profile_data
        
        # 1. Visualization Dashboard
        st.markdown("### Architecture Insights")
        
        # Dashboard Card Wrapper
        st.markdown('<div style="background: white; padding: 30px; border-radius: 20px; border: 1px solid rgba(0,0,0,0.05); margin-bottom: 30px;">', unsafe_allow_html=True)
        vcol1, vcol2 = st.columns([2, 1])
        
        # Prep data for viz
        table_stats = []
        type_counts = {}
        for t in profile_data.get('tables', []):
            table_stats.append({"Table": t.get('name', 'Unknown'), "Rows": t.get('row_count', 0)})
            for c in t.get('columns', []):
                # Handle both dict-based columns and string-based columns for safety
                if isinstance(c, dict):
                    t_key = c.get('type', 'TEXT').split("(")[0]
                else:
                    t_key = "TEXT"
                type_counts[t_key] = type_counts.get(t_key, 0) + 1
        
        with vcol1:
            st.markdown("<p style='font-size: 0.9rem; color: #64748B; font-weight: 600; text-transform: uppercase;'>Source Entity Distribution</p>", unsafe_allow_html=True)
            stats_df = pd.DataFrame(table_stats)
            st.bar_chart(stats_df.set_index("Table"), color="#002244", use_container_width=True)
            
        with vcol2:
            st.markdown("<p style='font-size: 0.9rem; color: #64748B; font-weight: 600; text-transform: uppercase;'>DataType Composition</p>", unsafe_allow_html=True)
            type_df = pd.DataFrame([{"Type": k, "Count": v} for k, v in type_counts.items()])
            st.vega_lite_chart(type_df, {
                'mark': {'type': 'arc', 'innerRadius': 50, 'stroke': '#fff'},
                'encoding': {
                    'theta': {'field': 'Count', 'type': 'quantitative'},
                    'color': {'field': 'Type', 'type': 'nominal', 'scale': {'range': ['#002244', '#38BDF8', '#1E40AF', '#10B981', '#F59E0B']}}
                },
                'height': 200
            }, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 2. Entity Discovery Section
        st.markdown("### Enterprise Entity Explorer")
        
        # Control bar
        c1, c2 = st.columns([2, 1])
        table_names = [t.get('name', 'Unknown') for t in profile_data.get('tables', [])]
        selected_name = c1.selectbox("Focus Entity", table_names, index=0)
        
        table = next((t for t in profile_data.get('tables', []) if t.get('name') == selected_name), {})
        
        # Detail Canvas
        st.markdown(f"""
            <div style="background: white; border: 1px solid #E2E8F0; border-radius: 16px; padding: 35px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; padding-bottom: 15px; border-bottom: 1px solid #F1F5F9;">
                    <div>
                        <h2 style="margin: 0; color: #002244; font-size: 1.8rem; font-weight: 700;">{table.get('name', 'UNKNOWN').upper()}</h2>
                        <p style="margin: 5px 0 0; color: #64748B;">Detailed Schema & Governance Profile</p>
                    </div>
                    <div style="text-align: right;">
                        <span style="background: #F1F5F9; padding: 8px 16px; border-radius: 30px; font-weight: 700; font-size: 0.9rem; color: #002244;">
                            {table.get('row_count', 0):,} RECORDS
                        </span>
                    </div>
                </div>
        """, unsafe_allow_html=True)
        
        sc1, sc2 = st.columns([1, 2])
        with sc1:
            st.markdown("<p style='font-size: 0.8rem; color: #64748B; font-weight: 700;'>LOGICAL ATTRIBUTES</p>", unsafe_allow_html=True)
            raw_cols = table.get("columns", [])
            # Normalize to dicts if they are strings
            normalized_cols = []
            for c in raw_cols:
                if isinstance(c, dict):
                    normalized_cols.append(c)
                else:
                    normalized_cols.append({"name": str(c), "type": "TEXT", "nullable": True})
            
            if normalized_cols:
                cols_df = pd.DataFrame(normalized_cols)
                # Ensure all required columns exist in the DF for filtering
                for required_col in ["name", "type", "nullable"]:
                    if required_col not in cols_df.columns:
                        cols_df[required_col] = "N/A"
                
                cols_df = cols_df[["name", "type", "nullable"]]
                cols_df.columns = ["Field", "Type", "Null?"]
                st.dataframe(cols_df, use_container_width=True, hide_index=True)
            else:
                st.info("No columns defined for this entity.")
            
        with sc2:
            st.markdown("<p style='font-size: 0.8rem; color: #64748B; font-weight: 700;'>INTELLIGENT CONTENT SAMPLE</p>", unsafe_allow_html=True)
            if "sample" in table and table["sample"] and len(table["sample"]) > 0:
                st.dataframe(pd.DataFrame(table["sample"]), use_container_width=True, hide_index=True)
            else:
                st.info("No content sample available for this entity.")
        
        # Policy & Key Badges
        keys = [c.get('name') for c in table.get('columns', []) if isinstance(c, dict) and c.get('is_key')]
        pii = [c.get('name') for c in table.get('columns', []) if isinstance(c, dict) and c.get('is_pii')]
        
        if keys or pii:
            st.markdown("<hr style='border: 0; border-top: 1px solid #F1F5F9; margin: 25px 0;'>", unsafe_allow_html=True)
            mc1, mc2 = st.columns(2)
            if keys:
                mc1.markdown(f"""
                    <div style='background: #EFF6FF; padding: 12px 18px; border-radius: 10px; border-left: 4px solid #1E40AF;'>
                        <p style='font-size: 0.75rem; color: #1E40AF; font-weight: 700; margin: 0;'>RECOGNIZED BUSINESS KEYS</p>
                        <p style='color: #002244; font-weight: 600; font-size: 1rem; margin: 5px 0 0;'>{', '.join(keys)}</p>
                    </div>
                """, unsafe_allow_html=True)
            if pii:
                mc2.markdown(f"""
                    <div style='background: #FEF2F2; padding: 12px 18px; border-radius: 10px; border-left: 4px solid #B91C1C;'>
                        <p style='font-size: 0.75rem; color: #B91C1C; font-weight: 700; margin: 0;'>SENSITIVE PII DETECTED</p>
                        <p style='color: #991B1B; font-weight: 600; font-size: 1rem; margin: 5px 0 0;'>{', '.join(pii)}</p>
                    </div>
                """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
                
        # 3. Final Navigation
        st.markdown("<br><br>", unsafe_allow_html=True)
        fc1, fc2, fc3 = st.columns([1, 2, 1])
        if fc2.button("INITIALIZE ARCHITECTURAL BLUEPRINT", type="primary", use_container_width=True):
            st.switch_page("pages/3_AI_Generation.py")
            
    else:
        st.error("Engine failed to profile the selected source data.")

if __name__ == "__main__":
    main()
