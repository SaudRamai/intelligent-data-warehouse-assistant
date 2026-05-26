import streamlit as st
import time
import json
import uuid
from snowflake.snowpark import Session
from typing import Optional, Any

# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

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

# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

MODEL_REGISTRY = [
    {"id": "claude-sonnet-4-6", "tier": 1, "params": 3, "context": 200000},
    {"id": "mistral-large2",    "tier": 1, "params": 3, "context": 128000},
]

TWO_PARAM_ONLY_MODELS = {m["id"] for m in MODEL_REGISTRY if m["params"] == 2}
MODEL_TOKEN_CAPS       = {m["id"]: m["context"] for m in MODEL_REGISTRY}

# ---------------------------------------------------------------------------
# Session management — SiS-first, st.secrets fallback
# ---------------------------------------------------------------------------

def _build_session_from_secrets() -> Optional[Session]:
    """Attempt to create a Snowpark session from st.secrets (local dev only)."""
    try:
        secrets = dict(st.secrets)
    except Exception:
        return None

    account = secrets.get("SNOWFLAKE_ACCOUNT")
    user    = secrets.get("SNOWFLAKE_USER")
    if not account or not user:
        return None

    params: dict = {
        "account":   account,
        "user":      user,
        "password":  secrets.get("SNOWFLAKE_PASSWORD"),
        "warehouse": secrets.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        "database":  secrets.get("SNOWFLAKE_DATABASE",  "ARCHITECTURE_STORE"),
        "schema":    secrets.get("SNOWFLAKE_SCHEMA",    "PUBLIC"),
        "role":      secrets.get("SNOWFLAKE_ROLE",      "ACCOUNTADMIN"),
    }

    authenticator = secrets.get("SNOWFLAKE_AUTHENTICATOR")
    if authenticator:
        params["authenticator"] = authenticator
    passcode = secrets.get("SNOWFLAKE_PASSCODE")
    if passcode:
        params["passcode"] = str(passcode)

    return Session.builder.configs(params).create()


def _create_session_internal() -> tuple[Optional[Session], Optional[str]]:
    """Return (session, error_string). Tries SiS get_active_session first."""
    # 1. Streamlit in Snowflake — use the ambient session (no creds needed)
    try:
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
        if session:
            return session, None
    except Exception:
        pass

    # 2. Local development — read credentials from st.secrets
    try:
        session = _build_session_from_secrets()
        if session:
            return session, None
        return None, "No credentials found in st.secrets. Add them to .streamlit/secrets.toml for local dev."
    except Exception as e:
        return None, str(e)


@st.cache_resource(show_spinner="Connecting to Snowflake...")
def get_snowflake_session() -> tuple[Optional[Session], Optional[str]]:
    return _create_session_internal()


def create_parallel_session() -> Optional[Session]:
    """Creates a fresh, uncached session for background threads."""
    session, _ = _create_session_internal()
    return session


def ensure_session() -> Session:
    """
    Returns a live Snowflake session from session_state, reconnecting if needed.
    Also auto-initialises the ARCHITECTURE_STORE DB on first use.
    """
    session = st.session_state.get("snowflake_session")

    # Heartbeat check
    if session:
        try:
            session.sql("SELECT 1").collect()
        except Exception:
            session = None

    if not session:
        get_snowflake_session.clear()
        session, err = get_snowflake_session()
        if not session:
            raise Exception(f"Snowflake Connection Failed: {err}")
        st.session_state["snowflake_session"]  = session
        st.session_state["snowflake_connected"] = True

    # Auto-initialise DB once per app session
    if not st.session_state.get("snowflake_init_complete"):
        try:
            db_check = session.sql("SHOW DATABASES LIKE 'ARCHITECTURE_STORE'").collect()
            if not db_check:
                run_setup_script(session)

            # Self-healing schema migrations
            session.sql('ALTER TABLE ARCHITECTURE_STORE.PUBLIC.PROJECTS ADD COLUMN IF NOT EXISTS "MERMAID_DIAGRAM" TEXT').collect()
            session.sql('ALTER TABLE ARCHITECTURE_STORE.PUBLIC.PROJECTS ADD COLUMN IF NOT EXISTS "METADATA" VARIANT').collect()
            session.sql('ALTER TABLE ARCHITECTURE_STORE.PUBLIC.PROJECTS ADD COLUMN IF NOT EXISTS "HISTORY" VARIANT').collect()

            # Auto-enable Cortex cross-region if running as ACCOUNTADMIN
            active_role = session.get_current_role() or ""
            if "ACCOUNTADMIN" in active_role.upper():
                try:
                    session.sql("ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION'").collect()
                    print("[SYSTEM] Auto-enabled cross-region Cortex LLM models.")
                except Exception as e:
                    print(f"[SYSTEM] Could not enable cross-region models: {e}")

                try:
                    grants = session.sql(f"SHOW GRANTS TO ROLE {active_role}").collect()
                    if not any('CORTEX_USER' in str(r) for r in grants):
                        session.sql(f"GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE {active_role}").collect()
                        print(f"[SYSTEM] Granted CORTEX_USER to {active_role}")
                except Exception as e:
                    print(f"[SYSTEM] Grant check/apply failed: {e}")

            st.session_state["snowflake_init_complete"] = True
        except Exception as e:
            print(f"[WARNING] Snowflake Auto-Init failed: {e}")

    return session

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def check_connection(session: Session) -> bool:
    """Returns True if the session is alive."""
    if session is None:
        return False
    try:
        session.sql("SELECT 1").collect()
        return True
    except Exception:
        return False


def get_available_cortex_models(session: Session) -> list:
    """Returns the list of Cortex models from the central registry."""
    return [m["id"] for m in MODEL_REGISTRY]

# ---------------------------------------------------------------------------
# Project persistence
# ---------------------------------------------------------------------------

def save_project_to_store(session: Session, project_id: str, requirements: dict, data_profile: dict, outputs: dict) -> bool:
    """Saves the complete project state to ARCHITECTURE_STORE.PUBLIC.PROJECTS."""
    try:
        arch      = outputs.get("architecture", outputs.get("architecture_selection", outputs.get("architecture_strategy", {})))
        schema    = outputs.get("schema_modeling", outputs.get("schema", outputs.get("schema_design", {})))
        pipe      = outputs.get("pipeline", outputs.get("pipeline_design", {}))
        gov       = outputs.get("governance", outputs.get("governance_security", {}))
        artifacts = outputs.get("artifacts", outputs.get("ddl_generation", {}))
        history   = outputs.get("history", {})

        ddl_sql  = artifacts.get("ddl_sql", outputs.get("ddl_generation", {}).get("ddl_sql", ""))
        doc_data = artifacts.get("documentation", outputs.get("documentation_design", {}))

        # Flatten documentation dict → markdown string
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
                    parts += [f"- {e}" for e in entities] if isinstance(entities, list) else [str(entities)]
                    parts.append("")
                for k, v in doc_data.items():
                    if k not in {"executive_summary", "architecture_decision", "key_entities", "mermaid_diagram", "documentation"}:
                        parts.append(f"## {k.replace('_', ' ').title()}\n{v}\n")
                doc_text = "\n".join(parts)
        else:
            doc_text = str(doc_data)

        mermaid = (
            outputs.get("mermaid_diagram", doc_data.get("mermaid_diagram", ""))
            if isinstance(doc_data, dict)
            else outputs.get("mermaid_diagram", "")
        )

        if not project_id:
            project_id = st.session_state.get("project_id") or str(uuid.uuid4())
            st.session_state["project_id"] = project_id
            print(f"[REPAIR] Generated missing project_id: {project_id}")

        metadata = {
            "model":                st.session_state.get("selected_model"),
            "timestamp":            time.time(),
            "relationship_design":  outputs.get("relationship_design", {}),
            "final_blueprint":      outputs.get("final_blueprint", {}),
        }

        exists = session.sql(
            "SELECT ID FROM ARCHITECTURE_STORE.PUBLIC.PROJECTS WHERE ID = ?",
            params=[project_id]
        ).collect()

        if exists:
            session.sql("""
                UPDATE ARCHITECTURE_STORE.PUBLIC.PROJECTS SET
                "REQUIREMENTS"  = PARSE_JSON(?),
                "DATA_PROFILE"  = PARSE_JSON(?),
                "ARCHITECTURE"  = PARSE_JSON(?),
                "SCHEMA_DESIGN" = PARSE_JSON(?),
                "PIPELINE"      = PARSE_JSON(?),
                "GOVERNANCE"    = PARSE_JSON(?),
                "DDL_SQL"       = ?,
                "DOCUMENTATION" = ?,
                "MERMAID_DIAGRAM" = ?,
                "METADATA"      = PARSE_JSON(?),
                "HISTORY"       = PARSE_JSON(?),
                "STATUS"        = 'generated'
                WHERE "ID" = ?
            """, params=[
                safe_dumps(requirements), safe_dumps(data_profile),
                safe_dumps(arch), safe_dumps(schema), safe_dumps(pipe), safe_dumps(gov),
                str(ddl_sql), str(doc_text), str(mermaid),
                safe_dumps(metadata), safe_dumps(history),
                project_id,
            ]).collect()
        else:
            session.sql("""
                INSERT INTO ARCHITECTURE_STORE.PUBLIC.PROJECTS
                ("ID","REQUIREMENTS","DATA_PROFILE","ARCHITECTURE","SCHEMA_DESIGN",
                 "PIPELINE","GOVERNANCE","DDL_SQL","DOCUMENTATION","MERMAID_DIAGRAM",
                 "METADATA","HISTORY","STATUS")
                SELECT ?,PARSE_JSON(?),PARSE_JSON(?),PARSE_JSON(?),PARSE_JSON(?),
                       PARSE_JSON(?),PARSE_JSON(?),?,?,?,PARSE_JSON(?),PARSE_JSON(?),'generated'
            """, params=[
                project_id,
                safe_dumps(requirements), safe_dumps(data_profile),
                safe_dumps(arch), safe_dumps(schema), safe_dumps(pipe), safe_dumps(gov),
                str(ddl_sql), str(doc_text), str(mermaid),
                safe_dumps(metadata), safe_dumps(history),
            ]).collect()

        return True

    except Exception as e:
        err_msg = str(e)
        # Self-heal: add missing HISTORY column and retry once
        if "HISTORY" in err_msg or "identifier" in err_msg:
            try:
                session.sql('ALTER TABLE ARCHITECTURE_STORE.PUBLIC.PROJECTS ADD COLUMN IF NOT EXISTS "HISTORY" VARIANT').collect()
                if not getattr(save_project_to_store, "_retrying", False):
                    save_project_to_store._retrying = True
                    result = save_project_to_store(session, project_id, requirements, data_profile, outputs)
                    save_project_to_store._retrying = False
                    return result
            except Exception:
                pass
        print(f"Failed to save project: {err_msg}")
        return False


def run_setup_script(session: Session):
    """Initialises ARCHITECTURE_STORE database and required tables."""
    try:
        session.sql("CREATE DATABASE IF NOT EXISTS ARCHITECTURE_STORE").collect()
        session.sql("CREATE SCHEMA IF NOT EXISTS ARCHITECTURE_STORE.PUBLIC").collect()
        session.sql("""
            CREATE TABLE IF NOT EXISTS ARCHITECTURE_STORE.PUBLIC.PROJECTS (
                ID              STRING PRIMARY KEY,
                CREATED_AT      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                REQUIREMENTS    VARIANT,
                DATA_PROFILE    VARIANT,
                ARCHITECTURE    VARIANT,
                SCHEMA_DESIGN   VARIANT,
                PIPELINE        VARIANT,
                GOVERNANCE      VARIANT,
                DDL_SQL         TEXT,
                DOCUMENTATION   TEXT,
                MERMAID_DIAGRAM TEXT,
                METADATA        VARIANT,
                HISTORY         VARIANT,
                STATUS          STRING
            )
        """).collect()
        session.sql("""
            CREATE TABLE IF NOT EXISTS ARCHITECTURE_STORE.PUBLIC.DEPLOY_LOG (
                TIMESTAMP       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                PROJECT_ID      STRING,
                TARGET_DB       STRING,
                TARGET_SCHEMA   STRING,
                STATEMENTS_RUN  INTEGER,
                STATUS          STRING,
                ERRORS          VARIANT
            )
        """).collect()
    except Exception as e:
        print(f"Setup failed: {e}")


def log_deployment(session: Session, project_id: str, target_db: str, target_schema: str,
                   statements_run: int, status: str, errors: Any = None):
    """Logs a deployment outcome to ARCHITECTURE_STORE.PUBLIC.DEPLOY_LOG."""
    try:
        session.sql("""
            INSERT INTO ARCHITECTURE_STORE.PUBLIC.DEPLOY_LOG
            (PROJECT_ID, TARGET_DB, TARGET_SCHEMA, STATEMENTS_RUN, STATUS, ERRORS)
            SELECT ?, ?, ?, ?, ?, PARSE_JSON(?)
        """, params=[
            project_id, target_db, target_schema, statements_run, status,
            safe_dumps(errors) if errors else None,
        ]).collect()
    except Exception as e:
        print(f"Failed to log deployment: {e}")


@st.cache_data(ttl=300, show_spinner="Fetching project history...")
def get_all_projects(_session: Session) -> list:
    """Fetches all stored projects from ARCHITECTURE_STORE."""
    try:
        rows = _session.sql(
            "SELECT ID, CREATED_AT, STATUS, DDL_SQL, ARCHITECTURE "
            "FROM ARCHITECTURE_STORE.PUBLIC.PROJECTS ORDER BY CREATED_AT DESC"
        ).collect()
        return [r.as_dict() for r in rows]
    except Exception as e:
        print(f"Failed to fetch projects: {e}")
        return []


def load_project_by_id(session: Session, project_id: str) -> Optional[dict]:
    """Loads a project by ID and returns a fully-resolved dict."""
    try:
        res = session.sql(
            "SELECT * FROM ARCHITECTURE_STORE.PUBLIC.PROJECTS WHERE ID = ?",
            params=[project_id]
        ).collect()
        if not res:
            return None

        row = {k.upper(): v for k, v in res[0].as_dict().items()}

        def parse_variant(val):
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return {}
            return val if val else {}

        arch   = parse_variant(row.get("ARCHITECTURE"))
        schema = parse_variant(row.get("SCHEMA_DESIGN"))
        pipe   = parse_variant(row.get("PIPELINE"))
        gov    = parse_variant(row.get("GOVERNANCE"))
        docs   = {"documentation": row.get("DOCUMENTATION", ""), "mermaid_diagram": row.get("MERMAID_DIAGRAM", "")}
        meta   = parse_variant(row.get("METADATA"))

        return {
            "project_id":           row.get("ID"),
            "requirements":         parse_variant(row.get("REQUIREMENTS")),
            "data_profile":         parse_variant(row.get("DATA_PROFILE")),
            "architecture_selection": arch,
            "schema_design":        schema,
            "pipeline_design":      pipe,
            "governance_security":  gov,
            "ddl_generation":       {"ddl_sql": row.get("DDL_SQL", "")},
            "documentation_design": docs,
            "relationship_design":  meta.get("relationship_design", {}),
            "final_blueprint":      meta.get("final_blueprint", {}),
            "final":                meta.get("final_blueprint", {}),
            # Canonical master keys
            "architecture":         arch,
            "schema":               schema,
            "pipeline":             pipe,
            "governance":           gov,
            "artifacts":            {"ddl_sql": row.get("DDL_SQL", ""), "documentation": docs},
            "history":              parse_variant(row.get("HISTORY")),
            "status":               row.get("STATUS", "draft"),
        }
    except Exception as e:
        print(f"Failed to load project {project_id}: {e}")
        return None
