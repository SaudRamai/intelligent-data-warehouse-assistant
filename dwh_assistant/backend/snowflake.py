import streamlit as st
import os
import time
import json
from pathlib import Path
from snowflake.snowpark import Session
from typing import Tuple, Optional, Any

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if type(obj).__name__ in ['Timestamp', 'DatetimeIndex', 'Period']:
            return str(obj)
        try:
            return super().default(obj)
        except Exception:
            return str(obj)

def safe_dumps(obj) -> str:
    return json.dumps(obj, cls=CustomJSONEncoder)

# Master model registry — tier order = fallback priority
# params: 3 = supports OBJECT_CONSTRUCT options
# params: 2 = only COMPLETE(model, prompt), no options
MODEL_REGISTRY = [
    {"id": "claude-sonnet-4-6", "tier": 1, "params": 3, "context": 200000},
    {"id": "mistral-large2",    "tier": 1, "params": 3, "context": 128000}
]

TWO_PARAM_ONLY_MODELS = {
    m["id"] for m in MODEL_REGISTRY if m["params"] == 2
}

MODEL_TOKEN_CAPS = {
    m["id"]: m["context"] for m in MODEL_REGISTRY
}

# Global Lockout File Path (Relative to app root)
LOCKOUT_FILE = Path(__file__).parent.parent / ".streamlit" / "snowflake_lockout.json"

def _check_lockout():
    """Checks if the CURRENT account/user is in a global cooldown period."""
    if LOCKOUT_FILE.exists():
        try:
            with open(LOCKOUT_FILE, 'r') as f:
                lockout_data = json.load(f)
            
            account = st.secrets.get("SNOWFLAKE_ACCOUNT", "unknown")
            user = st.secrets.get("SNOWFLAKE_USER", "unknown")
            key = f"{account}:{user}"
            
            data = lockout_data.get(key)
            if not data:
                return

            last_fail = data.get("timestamp", 0)
            error = data.get("error", "Unknown auth error")
                
            cooldown = 60 # Reduced to 60s for better UX
            elapsed = time.time() - last_fail
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                raise Exception(f"Snowflake Authentication Locked for {account}. Please wait {remaining}s. Error: {error}")
            else:
                # Cooldown expired for this key, clean up this entry
                lockout_data.pop(key, None)
                if lockout_data:
                    with open(LOCKOUT_FILE, 'w') as f:
                        json.dump(lockout_data, f)
                else:
                    LOCKOUT_FILE.unlink(missing_ok=True)
        except Exception as e:
            if "wait" in str(e): raise e
            # If JSON is corrupt, just remove it
            LOCKOUT_FILE.unlink(missing_ok=True)

def _set_lockout(error_msg: str):
    """Sets the lockout timestamp for the current account/user."""
    account = st.secrets.get("SNOWFLAKE_ACCOUNT", "unknown")
    user = st.secrets.get("SNOWFLAKE_USER", "unknown")
    key = f"{account}:{user}"
    
    lockout_data = {}
    if LOCKOUT_FILE.exists():
        try:
            with open(LOCKOUT_FILE, 'r') as f:
                lockout_data = json.load(f)
        except: pass
        
    lockout_data[key] = {"timestamp": time.time(), "error": str(error_msg)}
    
    with open(LOCKOUT_FILE, 'w') as f:
        json.dump(lockout_data, f)

def _clear_lockout():
    """Clears the lockout for the CURRENT account/user."""
    if LOCKOUT_FILE.exists():
        try:
            with open(LOCKOUT_FILE, 'r') as f:
                lockout_data = json.load(f)
            
            account = st.secrets.get("SNOWFLAKE_ACCOUNT", "unknown")
            user = st.secrets.get("SNOWFLAKE_USER", "unknown")
            key = f"{account}:{user}"
            
            if key in lockout_data:
                lockout_data.pop(key)
                if lockout_data:
                    with open(LOCKOUT_FILE, 'w') as f:
                        json.dump(lockout_data, f)
                else:
                    LOCKOUT_FILE.unlink(missing_ok=True)
        except:
            LOCKOUT_FILE.unlink(missing_ok=True)

def _create_session_internal() -> Tuple[Optional[Session], Optional[str]]:
    """The raw session creation logic."""
    _check_lockout()
    try:
        import toml
        # Try multiple potential paths for secrets.toml
        paths = [
            Path(__file__).parent.parent / ".streamlit" / "secrets.toml",
            Path.cwd() / ".streamlit" / "secrets.toml",
            Path.cwd() / "dwh_assistant" / ".streamlit" / "secrets.toml"
        ]
        
        secrets = {}
        for p in paths:
            if p.exists():
                try:
                    secrets = toml.load(p)
                    if secrets: break
                except: continue
        
        if not secrets:
            secrets = st.secrets

        connection_parameters = {
            "account": secrets.get("SNOWFLAKE_ACCOUNT"),
            "user": secrets.get("SNOWFLAKE_USER"),
            "password": secrets.get("SNOWFLAKE_PASSWORD"),
            "warehouse": secrets.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
            "database": secrets.get("SNOWFLAKE_DATABASE", "ARCHITECTURE_STORE"),
            "schema": secrets.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
            "role": secrets.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        }
        
        # Add support for custom authenticators (like username_password_mfa)
        authenticator = secrets.get("SNOWFLAKE_AUTHENTICATOR")
        if authenticator:
            connection_parameters["authenticator"] = authenticator
            
        passcode = secrets.get("SNOWFLAKE_PASSCODE")
        if passcode:
            connection_parameters["passcode"] = str(passcode)
            
        # Enable MFA token caching to minimize passcode prompts
        connection_parameters["client_request_mfa_token"] = True
        
        if not connection_parameters["account"] or not connection_parameters["user"]:
            return None, f"Credentials not found in paths: {[str(p) for p in paths]}"

        session = Session.builder.configs(connection_parameters).create()
        _clear_lockout()
        return session, None
    except Exception as e:
        _set_lockout(str(e))
        return None, str(e)

@st.cache_resource(show_spinner="Connecting to Snowflake...")
def get_snowflake_session() -> Tuple[Optional[Session], Optional[str]]:
    return _create_session_internal()

def create_parallel_session() -> Optional[Session]:
    """Creates a fresh, un-cached session for background threads."""
    session, _ = _create_session_internal()
    return session




def ensure_session() -> Session:
    """
    Ensures a valid Snowflake session is in state. 
    Includes a global circuit breaker and automatic DB initialization.
    """
    # 1. Check Global Lockout first
    _check_lockout()
    
    # 2. Check Session State
    session = st.session_state.get("snowflake_session")
    
    # Heartbeat check
    is_alive = False
    if session:
        try:
            session.sql("SELECT 1").collect()
            is_alive = True
        except:
            is_alive = False
            
    if not is_alive:
        # 3. Attempt reconnection
        # CRITICAL FIX: We must clear the cache BEFORE calling the function, 
        # otherwise Streamlit returns the cached (expired) session for force_refresh=True.
        get_snowflake_session.clear()
        session, err = get_snowflake_session()
        
        if session:
            st.session_state["snowflake_session"] = session
            st.session_state["snowflake_connected"] = True
            _clear_lockout() 
        else:
            # 4. Trigger Global Lockout on critical auth failures
            err_str = str(err).lower()
            if any(term in err_str for term in ["locked", "invalid", "authentication"]):
                _set_lockout(err)
            raise Exception(f"Snowflake Connection Failed: {err}")

    # 5. AUTO-INITIALIZATION CHECK (Once per session)
    if not st.session_state.get("snowflake_init_complete"):
        try:
            db_check = session.sql("SHOW DATABASES LIKE 'ARCHITECTURE_STORE'").collect()
            if not db_check:
                # Database missing - run setup
                run_setup_script(session)
                
            # SELF-HEALING: Ensure latest schema (Migration handling)
            session.sql('ALTER TABLE ARCHITECTURE_STORE.PUBLIC.PROJECTS ADD COLUMN IF NOT EXISTS "MERMAID_DIAGRAM" TEXT').collect()
            session.sql('ALTER TABLE ARCHITECTURE_STORE.PUBLIC.PROJECTS ADD COLUMN IF NOT EXISTS "METADATA" VARIANT').collect()
            session.sql('ALTER TABLE ARCHITECTURE_STORE.PUBLIC.PROJECTS ADD COLUMN IF NOT EXISTS "HISTORY" VARIANT').collect()
            
            # 6. AUTOMATED CORTEX PERMISSION & MODEL ENABLEMENT CHECK
            active_role = session.get_current_role()
            role_from_secrets = st.secrets.get("SNOWFLAKE_ROLE", "").upper()
            if "ACCOUNTADMIN" in role_from_secrets or (active_role and "ACCOUNTADMIN" in active_role.upper()):
                try:
                    session.sql("ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION'").collect()
                    print("[SYSTEM] Auto-enabled cross-region Cortex LLM models for the account.")
                except Exception as e:
                    print(f"[SYSTEM] Could not auto-enable cross-region models: {e}")

            if active_role:
                try:
                    check_grant = session.sql(f"SHOW GRANTS TO ROLE {active_role}").collect()
                    has_cortex = any('CORTEX_USER' in str(row) for row in check_grant)
                    if not has_cortex:
                        session.sql(f"GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE {active_role}").collect()
                        print(f"[SYSTEM] Granted CORTEX_USER to {active_role}")
                except Exception as e:
                    print(f"[SYSTEM] Grant check/apply failed: {e}")
            
            st.session_state["snowflake_init_complete"] = True
        except Exception as e:
            print(f"[WARNING] Snowflake Auto-Init/Cortex Grant Failed: {e}")
            # Don't set init_complete=True so it retries, but don't fail either
            
    return session

def check_connection(session: Session) -> bool:
    """Checks if the session is active by running a simple query."""
    if session is None:
        return False
    try:
        session.sql("SELECT 1").collect()
        return True
    except Exception:
        return False


def get_available_cortex_models(session: Session) -> list:
    """
    Returns a unified list of verified Cortex models from the central registry.
    """
    return [m["id"] for m in MODEL_REGISTRY]

def save_project_to_store(session: Session, project_id: str, requirements: dict, data_profile: dict, outputs: dict):
    """Saves the complete project state to Snowflake ARCHITECTURE_STORE."""
    try:
        arch = outputs.get("architecture", outputs.get("architecture_selection", outputs.get("architecture_strategy", {})))
        # FIX: Try schema_modeling first (actual key), then fallback to aliases
        schema = outputs.get("schema_modeling", outputs.get("schema", outputs.get("schema_design", {})))
        pipe = outputs.get("pipeline", outputs.get("pipeline_design", {}))
        gov = outputs.get("governance", outputs.get("governance_security", {}))
        artifacts = outputs.get("artifacts", outputs.get("ddl_generation", {}))
        history = outputs.get("history", {})
        
        # ddl_gen and doc_design extraction for flat columns
        ddl_sql = artifacts.get("ddl_sql", outputs.get("ddl_generation", {}).get("ddl_sql", ""))
        doc_data = artifacts.get("documentation", outputs.get("documentation_design", {}))
        
        doc_text = ""
        if isinstance(doc_data, dict):
            if "documentation" in doc_data and isinstance(doc_data["documentation"], str):
                doc_text = doc_data["documentation"]
            else:
                parts = ["# Data Warehouse Technical Documentation\n"]
                if "executive_summary" in doc_data:
                    parts.append(f"## Executive Summary\n{doc_data['executive_summary']}\n")
                if "architecture_decision" in doc_data:
                    parts.append(f"## Architecture Decisions\n{doc_data['architecture_decision']}\n")
                if "key_entities" in doc_data:
                    parts.append("## Key Entities")
                    entities = doc_data["key_entities"]
                    if isinstance(entities, list):
                        for e in entities:
                            parts.append(f"- {e}")
                    else:
                        parts.append(str(entities))
                    parts.append("")
                
                # Append any other keys that might be there
                for k, v in doc_data.items():
                    if k not in ["executive_summary", "architecture_decision", "key_entities", "mermaid_diagram", "documentation"]:
                        title = k.replace("_", " ").title()
                        parts.append(f"## {title}\n{v}\n")
                
                doc_text = "\n".join(parts)
        else:
            doc_text = str(doc_data)
            
        mermaid = outputs.get("mermaid_diagram", doc_data.get("mermaid_diagram", "")) if isinstance(doc_data, dict) else outputs.get("mermaid_diagram", "")
        
        import uuid
        if not project_id:
            project_id = st.session_state.get("project_id") or str(uuid.uuid4())
            st.session_state["project_id"] = project_id
            print(f"[REPAIR] Generated missing project_id: {project_id}")
            
        metadata = {
            "model": st.session_state.get("selected_model"),
            "timestamp": time.time(),
            "relationship_design": outputs.get("relationship_design", {}),
            "final_blueprint": outputs.get("final_blueprint", {})
        }
        
        # Check if project exists
        check = session.sql("SELECT ID FROM ARCHITECTURE_STORE.PUBLIC.PROJECTS WHERE ID = ?", params=[project_id]).collect()
        
        if check:
            # Update
            session.sql("""
                UPDATE ARCHITECTURE_STORE.PUBLIC.PROJECTS SET
                "REQUIREMENTS" = PARSE_JSON(?),
                "DATA_PROFILE" = PARSE_JSON(?),
                "ARCHITECTURE" = PARSE_JSON(?),
                "SCHEMA_DESIGN" = PARSE_JSON(?),
                "PIPELINE" = PARSE_JSON(?),
                "GOVERNANCE" = PARSE_JSON(?),
                "DDL_SQL" = ?,
                "DOCUMENTATION" = ?,
                "MERMAID_DIAGRAM" = ?,
                "METADATA" = PARSE_JSON(?),
                "HISTORY" = PARSE_JSON(?),
                "STATUS" = 'generated'
                WHERE "ID" = ?
            """, params=[
                safe_dumps(requirements),
                safe_dumps(data_profile),
                safe_dumps(arch),
                safe_dumps(schema),
                safe_dumps(pipe),
                safe_dumps(gov),
                str(ddl_sql),
                str(doc_text),
                str(mermaid),
                safe_dumps(metadata),
                safe_dumps(history),
                project_id
            ]).collect()
        else:
            # Insert
            session.sql("""
                INSERT INTO ARCHITECTURE_STORE.PUBLIC.PROJECTS 
                ("ID", "REQUIREMENTS", "DATA_PROFILE", "ARCHITECTURE", "SCHEMA_DESIGN", "PIPELINE", "GOVERNANCE", 
                 "DDL_SQL", "DOCUMENTATION", "MERMAID_DIAGRAM", "METADATA", "HISTORY", "STATUS")
                SELECT ?, PARSE_JSON(?), PARSE_JSON(?), PARSE_JSON(?), PARSE_JSON(?), PARSE_JSON(?), PARSE_JSON(?), 
                       ?, ?, ?, PARSE_JSON(?), PARSE_JSON(?), 'generated'
            """, params=[
                project_id,
                # Removed stray setup script placeholder; actual implementation defined later.
                safe_dumps(requirements),
                safe_dumps(data_profile),
                safe_dumps(arch),
                safe_dumps(schema),
                safe_dumps(pipe),
                safe_dumps(gov),
                str(ddl_sql),
                str(doc_text),
                str(mermaid),
                safe_dumps(metadata),
                safe_dumps(history)
            ]).collect()
        
        return True
    except Exception as e:
        err_msg = str(e)
        if "HISTORY" in err_msg or "identifier" in err_msg:
             # Final fallback: Try to add the column and retry once
             try:
                 session.sql('ALTER TABLE ARCHITECTURE_STORE.PUBLIC.PROJECTS ADD COLUMN IF NOT EXISTS "HISTORY" VARIANT').collect()
                 # Retry the whole function recursively once (without infinite loop)
                 if not getattr(save_project_to_store, "_retrying", False):
                     save_project_to_store._retrying = True
                     res = save_project_to_store(session, project_id, requirements, data_profile, outputs)
                     save_project_to_store._retrying = False
                     return res
             except: pass
             
        print(f"Failed to save project: {err_msg}")
        return False

def run_setup_script(session: Session):
    """Initializes the ARCHITECTURE_STORE database and required tables."""
    try:
        session.sql("CREATE DATABASE IF NOT EXISTS ARCHITECTURE_STORE").collect()
        session.sql("CREATE SCHEMA IF NOT EXISTS ARCHITECTURE_STORE.PUBLIC").collect()
        
        # Main Project Store
        session.sql("""
            CREATE TABLE IF NOT EXISTS ARCHITECTURE_STORE.PUBLIC.PROJECTS (
                ID STRING PRIMARY KEY,
                CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                REQUIREMENTS VARIANT,
                DATA_PROFILE VARIANT,
                ARCHITECTURE VARIANT,
                SCHEMA_DESIGN VARIANT,
                PIPELINE VARIANT,
                GOVERNANCE VARIANT,
                DDL_SQL TEXT,
                DOCUMENTATION TEXT,
                MERMAID_DIAGRAM TEXT,
                METADATA VARIANT,
                HISTORY VARIANT,
                STATUS STRING
            )
        """).collect()
        
        # Deployment Logs
        session.sql("""
            CREATE TABLE IF NOT EXISTS ARCHITECTURE_STORE.PUBLIC.DEPLOY_LOG (
                TIMESTAMP TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                PROJECT_ID STRING,
                TARGET_DB STRING,
                TARGET_SCHEMA STRING,
                STATEMENTS_RUN INTEGER,
                STATUS STRING,
                ERRORS VARIANT
            )
        """).collect()
    except Exception as e:
        print(f"Setup failed: {e}")

def log_deployment(session: Session, project_id: str, target_db: str, target_schema: str, statements_run: int, status: str, errors: Any = None):
    """Logs the deployment outcome to ARCHITECTURE_STORE using parameterized SQL."""
    try:
        session.sql("""
            INSERT INTO ARCHITECTURE_STORE.PUBLIC.DEPLOY_LOG 
            (PROJECT_ID, TARGET_DB, TARGET_SCHEMA, STATEMENTS_RUN, STATUS, ERRORS)
            SELECT ?, ?, ?, ?, ?, PARSE_JSON(?)
        """, params=[project_id, target_db, target_schema, statements_run, status, safe_dumps(errors) if errors else None]).collect()
    except Exception as e:
        print(f"Failed to log deployment: {e}")

@st.cache_data(ttl=300, show_spinner="Fetching project history...")
def get_all_projects(_session: Session) -> list:
    """Fetches all stored projects from ARCHITECTURE_STORE."""
    try:
        # Note: selecting essential summary columns to avoid KeyError in UI
        rows = _session.sql("SELECT ID, CREATED_AT, STATUS, DDL_SQL, ARCHITECTURE FROM ARCHITECTURE_STORE.PUBLIC.PROJECTS ORDER BY CREATED_AT DESC").collect()
        return [r.as_dict() for r in rows]
    except Exception as e:
        print(f"Failed to fetch projects: {e}")
        return []

def load_project_by_id(session: Session, project_id: str) -> dict:
    """Loads a specific project by ID and returns a dictionary of all its attributes."""
    try:
        res = session.sql("SELECT * FROM ARCHITECTURE_STORE.PUBLIC.PROJECTS WHERE ID = ?", params=[project_id]).collect()
        if not res:
            return None
        
        # Convert row to case-insensitive dictionary
        row_raw = res[0].as_dict()
        row = {k.upper(): v for k, v in row_raw.items()}
        
        # Snowflake VARIANT columns are automatically converted to dicts/lists by Snowpark if they are valid JSON
        def parse_variant(val):
            if isinstance(val, str):
                try: return json.loads(val)
                except: return {}
            return val if val else {}

        arch_metadata = parse_variant(row.get("ARCHITECTURE"))
        schema_metadata = parse_variant(row.get("SCHEMA_DESIGN"))
        pipe_metadata = parse_variant(row.get("PIPELINE"))
        gov_metadata = parse_variant(row.get("GOVERNANCE"))
        doc_metadata = {
            "documentation": row.get("DOCUMENTATION", ""),
            "mermaid_diagram": row.get("MERMAID_DIAGRAM", "")
        }

        meta_parsed = parse_variant(row.get("METADATA"))
        rel_design = meta_parsed.get("relationship_design", {})
        final_bp = meta_parsed.get("final_blueprint", {})

        return {
            "project_id": row.get("ID"),
            "requirements": parse_variant(row.get("REQUIREMENTS")),
            "data_profile": parse_variant(row.get("DATA_PROFILE")),
            "architecture_selection": arch_metadata,
            "schema_design": schema_metadata,
            "pipeline_design": pipe_metadata,
            "governance_security": gov_metadata,
            "ddl_generation": {"ddl_sql": row.get("DDL_SQL", "")},
            "documentation_design": doc_metadata,
            "relationship_design": rel_design,
            "final_blueprint": final_bp,
            "final": final_bp,
            
            # NEW MASTER KEYS
            "architecture": arch_metadata,
            "schema": schema_metadata,
            "pipeline": pipe_metadata,
            "governance": gov_metadata,
            "artifacts": {
                "ddl_sql": row.get("DDL_SQL", ""),
                "documentation": doc_metadata
            },
            "history": parse_variant(row.get("HISTORY")),
            "status": row.get("STATUS", "draft")
        }
    except Exception as e:
        print(f"Failed to load project {project_id}: {str(e)}")
        return None
