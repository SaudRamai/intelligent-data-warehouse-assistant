import uuid

def get_default_state():
    return {
        "snowflake_session": None,
        "snowflake_connected": False,
        "requirements": {},
        "form_complete": False,
        "data_profile": {},
        "profile_source": None,
        "selected_model": "claude-sonnet-4-6",
        "generation_running": False,
        "generation_results": {},
        "project_id": str(uuid.uuid4())
    }

STATE_PREFIXES_TO_CLEAN = [
    "flow_state_", "mini_erd_", "dag_state_",
    "editor_", "toggle_", "slider_", "sel_"
]

STATE_EXACT_KEYS_TO_CLEAN = [
    "architecture_selection", "architecture", "architecture_strategy",
    "schema_modeling", "schema", "schema_context",
    "pipeline_design", "pipeline", "governance_security", "governance",
    "ddl_generation", "artifacts", "documentation_design", "final_blueprint", "blueprint",
    "history", "edited_schema_creation", "edited_ddl_sql", "edited_grant_sql", "edited_transform_sql",
    "artifacts_original_payload", "profile_source", "architecture_strategy_raw",
    "schema_modeling_raw", "metadata_analysis_raw", "relationship_design_raw",
    "pipeline_design_raw", "governance_security_raw", "ddl_generation_raw",
    "final_blueprint_raw", "history_raw", "cortex_memory_cache"
]
