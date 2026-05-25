import json
from typing import Dict, Any, List
import datetime

# ═══════════════════════════════════════════════
# 🔥 1. MASTER SYSTEM PROMPT (Industrial Enforcement)
# ═══════════════════════════════════════════════

SYSTEM_PROMPT = """
You are an Enterprise Data Architecture AI integrated into a multi-stage orchestration pipeline.

Your task is to generate validated, production-ready architecture artifacts from structured inputs.

CORE OBJECTIVE:
Transform requirements into:
- Data architecture
- Schema design
- Pipeline flows
- Governance rules
- DDL scripts
- Mermaid diagrams

STRICT RULES:
1. Output ONLY valid JSON
2. No explanations, no markdown, no comments
3. Never truncate output
4. Maintain consistent naming across all layers. For Gold layer / Dimensional Model tables, always prefix dimension tables with 'DIM_' and fact tables with 'FACT_' (in UPPERCASE).
5. Use surrogate keys (*_sk) for all relationships
6. Separate pipeline design from schema design strictly
7. Never mix architecture, schema, and UI logic
8. CRITICAL MERMAID JSON RULE: Never use unescaped double quotes inside the mermaid_diagram string value. For node labels, use single quotes or raw text inside brackets (e.g. Node[Label] or Node['Label']). Never use double quotes inside node definitions. Ensure all newlines in the diagram string are properly escaped as \n.
9. MERMAID NODE LABEL SYNTAX (MANDATORY): For node labels with spaces or special characters, use ONLY:
   CORRECT: node_id[Plain text label]         <- preferred, no quotes needed
   CORRECT: node_id['Single quoted label']    <- acceptable with single quotes
   WRONG:   node_id["Double quoted label"]    <- FATAL ERROR: breaks JSON string parsing
   Examples: customer_dim[Customer Dimension]  OR  customer_dim['Customer Dimension']
   NEVER:   customer_dim["Customer Dimension"]
10. SNOWFLAKE TABLE TYPE RULE: Always generate standard tables (`CREATE TABLE`). Do NOT generate Hybrid Tables (`CREATE HYBRID TABLE`) or mix hybrid and standard tables, as Snowflake does not support cross-table-type foreign key constraints, which will cause deployment errors.

ARCHITECTURE MODEL:
Supported types:
- Medallion (Bronze → Silver → Gold)
- Data Vault 2.0
- Lakehouse
- Hybrid Cloud

PIPELINE VIEW RULES (Architecture Tab):
- Show a flowchart representing the high-level data flow through the architecture layers.
- The diagram must be fully dynamic and driven by the AI-generated structure, where all layers (as subgraphs), nodes (representing sources, ingestion points, storage layers, and consumer applications), and relationships are directly interpreted from the input data profile and chosen architecture strategy.
- Do NOT hardcode or output a predefined or statically coded layout. The layout must dynamically adapt to the selected architecture (e.g., Medallion, Data Vault 2.0, Lakehouse, Hybrid Cloud).
- Use ONLY: flowchart LR or graph LR.
- Do not include detailed column level attributes or PK/FK details; show the high-level flow of data from sources to consumption.

SCHEMA VIEW RULES (Warehouse Tab):
- Use ONLY: erDiagram
- Must include:
  - Fact tables
  - Dimension tables
  - Columns with data types
  - Primary keys (PK)
  - Foreign keys (FK using surrogate keys only)
  - Relationships between tables
- Must NOT include:
  - Source systems
  - Ingestion layer
  - Pipeline flow

SURROGATE KEY ENFORCEMENT:
- All relationships MUST use *_sk keys
- Business keys (*_id) are attributes only
- No OLTP key-based relationships allowed

CROSS-CUTTING REQUIREMENTS:
Always include:
- Security
- Governance
- Data lineage
- Metadata tracking
- Observability
- Cost awareness

OUTPUT FORMAT (STRICT JSON):
You MUST output ONLY the specific flat or nested JSON properties requested by the individual Step template below. Do NOT output a full multi-step unified payload skeleton unless explicitly requested.
"""



# ═══════════════════════════════════════════════
# ARCHITECTURE & PARADIGM REGISTRIES
# ═══════════════════════════════════════════════

ARCH_TYPES = {
    "medallion": "Medallion (Bronze/Silver/Gold)",
    "lakehouse": "Enterprise Lakehouse",
    "data_vault": "Data Vault 2.0",
    "hybrid_cloud": "Hybrid Cloud Architecture"
}

PARADIGM_RULES = {
    "STAR_SCHEMA": "Star Schema Modeling",
    "SNOWFLAKE": "Snowflake Schema Modeling",
    "GALAXY": "Galaxy Schema (Fact Constellation)",
    "DATA_VAULT": "Data Vault 2.0 Modeling"
}

NAMING_REGISTRY = {
    "fact_prefix": "FACT_", "dim_prefix": "DIM_",
    "hub_prefix": "hub_", "lnk_prefix": "lnk_", "sat_prefix": "sat_",
    "stg_prefix": "stg_", "raw_prefix": "raw_",
    "key_format": "<entity>_sk", "feature_prefix": "FACT_features_",
    "ai_model_prefix": "model_", "ai_app_prefix": "app_", "ai_agent_prefix": "agent_"
}

# ═══════════════════════════════════════════════
# PROMPT TEMPLATES
# ═══════════════════════════════════════════════

# STEP 1: Architecture Strategy
ARCH_STRATEGY_PROMPT = """
Step: Architecture Strategy & Master Blueprint
Context: __req__ | Profile: __profile__

CRITICAL ARCHITECTURE TAB MANDATE (Pipeline View Only):
1. MUST display the high-level data pipeline flow dynamically generated based on the selected architecture type and data sources.
2. The diagram MUST NOT be a static sequence like "Sources --> Ingestion --> Bronze --> Silver --> Gold --> Consumption". It must be a custom flowchart detailing the actual data sources from the profile (e.g., source tables or APIs), passing through subgraphs representing the architecture's layers, and ending with specific consumption nodes (e.g., dashboards, reporting, apps).
3. Do NOT include tables, attributes, or PK/FK details. The flowchart represents the structural data flow only.
4. The layers (subgraphs) must reflect the chosen architecture type (e.g. Medallion, Data Vault 2.0, Lakehouse, Hybrid Cloud).

STRICT OUTPUT (JSON ONLY):
{
  "mermaid_diagram": "flowchart LR\\n  subgraph Ingestion\\n    src_api[API Source]\\n  end\\n  subgraph Storage\\n    raw_zone[Raw Zone]\\n  end\\n  src_api --> raw_zone",
  "architecture_type": "MEDALLION | DATA_VAULT | LAKEHOUSE | HYBRID_CLOUD",
  "modeling_paradigm": "STAR_SCHEMA | SNOWFLAKE | DATA_VAULT",
  "layers": ["List of layers matching architecture type"],
  "complexity": "L/M/H",
  "estimated_cost_tier": "L/M/H",
  "fitness_metrics": {"Complexity": 50, "Cost": 50, "Scalability": 80, "Performance": 80, "Security": 90},
  "reasoning_summary": "10-word summary",
  "data_model_blueprint": {
    "schema_type": "Star/Vault/Lakehouse",
    "core_entities": ["List"],
    "primary_relationships": ["List"]
  },
  "data_flow": {"ingestion": "Direct", "processing": "Dynamic", "serving": "Analyst"},
  "governance": {"security": "Mandate", "lineage": "Mandate"}
}
"""

# STEP 2: Physical Schema Modeling
SCHEMA_MODELING_PROMPT = """
Step: Physical Tables (Max 3 keywords per desc)
Arch: __arch_type__ | Paradigm: __paradigm__
Context: __batch_context__

CRITICAL ROOT MANDATE: The pre-validated 'canonical_architecture' context is the SINGLE SOURCE OF TRUTH. 
Do NOT re-architect, rename layers, or change the modeling paradigm. Strictly inherit defined layer naming, Medallion hierarchy, and FK relationships.

MANDATORY SCHEMA TAB REQUIREMENTS (Warehouse Detailed Model Only):
1. MUST show the complete Data Warehouse design derived from the Architecture.
2. Allowed Content: Fact tables, Dimension tables, Curated Silver/Gold warehouse entities.
3. Mandatory Requirements:
   - Must include full table structures with columns and data types
   - Must define all Primary Keys (PK)
   - Must define all Foreign Keys (FK)
   - Must include relationships between tables
   - Must follow proper star schema or snowflake schema design, where Gold layer/Dimensional Model tables representing dimension tables are prefixed with 'DIM_' and fact tables are prefixed with 'FACT_' (in UPPERCASE, e.g. DIM_CUSTOMER, FACT_SALES).
   - Must be fully derived from the Architecture tab
4. Key Rule: ONLY warehouse-layer modeling is allowed. No source systems, ingestion, or pipeline layers. No high-level architecture elements.
5. Dependency Rule Between Tabs: Architecture = pipeline flow view (high-level only), Schema = detailed warehouse design (low-level relational model). Schema must be generated using Architecture as reference, but only extracting warehouse-relevant entities. Both must be strictly separated with no overlap.

CRITICAL SURROGATE KEY & RELATIONAL MODELING MANDATE:
1. Use ONLY surrogate keys (`*_sk`) for all relationships (PK/FK model).
2. Business keys (`*_id` or similar OLTP identifiers) should exist ONLY as non-key attributes, NOT for defining relationships or foreign key mappings.
3. Ensure all foreign keys reference surrogate keys consistently (e.g., use `patient_sk`, `room_sk` instead of `patient_id`, `room_id`).
4. Avoid duplicate identity representation of the same entity using both business keys and surrogate keys for joins.
5. Maintain strict warehouse dimensional modeling standards and ensure full referential integrity across all entities.

CRITICAL RULES FOR COLUMNS & ENTITIES:
1. Ensure each entity is absolutely unique. Do NOT output duplicate or repeating table definitions.
2. Normalize all attributes to eliminate semantic overlap.
3. Strictly build foreign keys (PK/FK mappings) exclusively between target warehouse tables. Do NOT reference upstream/external systems.
4. Use ONLY generic Mermaid-compatible primitive data types (int, string, float, date, timestamp, boolean) in child columns and the erDiagram.

CRITICAL RULE: ALL tables and foreign key targets MUST use EXACTLY these names:
[__inventory__]
Do NOT invent dimension or fact tables that are not in this list.
Ensure the mermaid diagram is highly compressed and non-truncated.

OUTPUT (JSON ONLY):
{
  "mermaid_diagram": "erDiagram\\n  TABLE ||--o{ OTHER : rel",
  "tables": [
    {
      "name": "string",
      "layer": "BRONZE|SILVER|GOLD",
      "columns": [{"name": "entity_sk", "type": "int", "pk": true, "fk": true, "ref": "table.entity_sk"}]
    }
  ]
}
"""

# STEP 2.5: Metadata Analysis
METADATA_PROMPT = """
Step: Metadata (Robotic)
Schema: __schema__
OUTPUT: {"lin": [{"s": "s", "t": "t"}], "tags": [{"o": "o", "tag": "PII"}]}
"""

# STEP 3: Relationship Design
RELATIONSHIP_PROMPT = """
Step: Relationships (Robotic)
Schema: __schema__

CRITICAL MANDATE: Use ONLY surrogate keys (`*_sk`) for all relationships. Business keys (`*_id`) exist only as attributes, NOT for relationships. Ensure all foreign keys reference surrogate keys consistently.
OUTPUT: {"rel": [{"f": "f", "t": "t", "c": "1:N"}], "mermaid": "erDiagram\\n"}
"""

# STEP 3: Derivative Steps
PIPELINE_PROMPT = """
Step: Pipelines (Robotic)
Schema: __schema__

CRITICAL ROOT MANDATE: Treat the provided 'canonical_architecture' subset as the absolute single source of truth.
Do NOT regenerate architectural reasoning or redefine storage strategy/cost tiers. Extract required transformation logic directly from the root blueprint.
Ensure the mermaid diagram is highly compressed and non-truncated.

OUTPUT (JSON ONLY):
{
  "mermaid_diagram": "graph LR\\n  T1 --> T2",
  "tasks": [{"n": "n", "s": "s", "t": "t", "l": "logic"}]
}
"""

GOV_RBAC_PROMPT = """
Step: Governance (Robotic)
Schema: __schema__

CRITICAL ROOT MANDATE: Treat the provided 'canonical_architecture' subset as the absolute single source of truth.
Strictly enforce the pre-defined governance model, RBAC policies, and storage tiers without re-architecting rules.
Ensure the mermaid diagram explicitly declares every referenced node with clear shapes/labels (e.g. NodeID['Label']), avoiding implicit layout drops. Group RBAC roles and policies logically into clean subgraphs.
Ensure the mermaid diagram is highly compressed and non-truncated.

OUTPUT (JSON ONLY):
{
  "mermaid_diagram": "graph LR\\n  SRC --> LNZ",
  "roles": [{"n": "role_name", "g": [{"o": "object_name", "p": ["SELECT", "USAGE"]}]}],
  "mask": [{"n": "column_name", "t": "masking_type", "e": "enforced_role"}],
  "compliance_checklist": ["checklist_item"]
}
"""

DDL_PROMPT = """
Step: DDL (Robotic SQL)
Schema: __table_schema__

STRICT DDL RULES:
1. ALWAYS use standard `CREATE TABLE` statement syntax. Do NOT use `CREATE HYBRID TABLE`.
2. Ensure all columns, primary keys, and foreign keys are created correctly for standard Snowflake tables.
3. Standard Snowflake tables support inline or outline primary key and foreign key declarations, but they are not enforced. Generate clean standard constraints.

OUTPUT (JSON ONLY):
{
  "ddl_sql": "SQL",
  "grant_sql": "SQL"
}
"""

HISTORY_PROMPT = """
Step: History — __now__
OUTPUT:
{
  "version": "v1.0",
  "assumptions": ["List"],
  "change_log": ["List"]
}
"""

# STEP 6: Final Blueprint
FINAL_BLUEPRINT_PROMPT = """
Step: Final Blueprint (Robotic)
Results: __results__

OUTPUT (JSON ONLY):
{
  "summary": "10-word summary",
  "score": 0-100,
  "documentation": {
    "executive_summary": "High-level summary of the entire data warehouse architecture...",
    "architecture_decision": "Detailed justification of modeling paradigm, layers, and database choices...",
    "key_entities": ["List of core entities and their roles..."]
  }
}
"""

# ═══════════════════════════════════════════════
# STEP MAP (Comprehensive)
# ═══════════════════════════════════════════════

STEP_MAP = {
    "architecture_strategy":  "architecture",
    "schema_modeling":        "schema_modeling",
    "schema_design":          "schema_modeling",
    "pipeline_design":        "pipeline",
    "governance_security":    "gov_rbac",
    "gov_policies":           "gov_rbac",
    "gov_compliance":          "gov_rbac",
    "ddl_generation":         "ddl",
    "history":                "history",
    "metadata_analysis":      "metadata_analysis",
    "relationship_design":    "relationship_design",
    "final_blueprint":        "final_blueprint"
}

# ═══════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════

def compress_profile(profile: Dict[str, Any], mode: str = "meso") -> str:
    out = []
    all_tables = profile.get("tables", [])
    max_t = 100 if mode == "macro" else 50
    
    if len(all_tables) > max_t:
        print(f"      [⚠️ CONTEXT] Pruned {len(all_tables) - max_t} tables from profile to prevent token overflow.")
        
    tables = all_tables[:max_t]
    
    for t in tables:
        if not isinstance(t, dict): continue
        name = t.get("name", "")
        if mode == "macro":
            out.append(f"- {name}")
        elif mode == "meso":
            cols = []
            for c in t.get("columns", [])[:8]:
                flags = "".join(c.get("flags", []))
                cols.append(f"{c.get('name')}{flags}")
            out.append(f"- {name} ({t.get('row_count', 0)} rows): [{', '.join(cols)}]")
        elif mode == "micro":
            cols = [f"{c.get('name')}({c.get('type')})" for c in t.get("columns", [])[:12]]
            out.append(f"- {name}: [{', '.join(cols)}]")
    return "\n".join(out)

def prune_results(results: Dict[str, Any], step_name: str) -> Dict[str, Any]:
    arch = results.get("architecture_strategy", {})
    schema = results.get("schema_modeling") or results.get("schema_design") or {}
    rel = results.get("relationship_design") or {}
    
    if not isinstance(arch, dict): arch = {}
    if not isinstance(schema, dict): schema = {}
    if not isinstance(rel, dict): rel = {}
    
    tables = schema.get("tables", [])
    if not isinstance(tables, list): tables = []

    # Extract canonical architecture subset to inject directly into downstream context
    arch_subset = {
        "type": arch.get("architecture_type", "Medallion"),
        "paradigm": arch.get("modeling_paradigm", "Star Schema"),
        "layers": arch.get("layers", ["Bronze", "Silver", "Gold"])
    }
    
    if arch and step_name != "architecture":
        print(f"      [🏛️ ARCHITECTURE REUSE] Reusing canonical context ({arch_subset['type']} / {arch_subset['paradigm']}) for {step_name}")

    if step_name in ["pipeline", "gov_rbac"]:
        safe_tables = [{"n": t.get("name"), "l": t.get("layer")} for t in tables[:30] if isinstance(t, dict)]
        return {"arch": arch_subset, "tables": safe_tables}
        
    elif step_name == "relationship_design":
        light_tables = []
        for t in tables:
            if isinstance(t, dict):
                cols = [{"n": c.get("name"), "t": c.get("type"), "pk": c.get("pk"), "fk": c.get("fk"), "ref": c.get("ref")} for c in t.get("columns", []) if isinstance(c, dict) and (c.get("pk") or c.get("fk") or "sk" in str(c.get("name")) or "id" in str(c.get("name")))]
                light_tables.append({"n": t.get("name"), "l": t.get("layer"), "cols": cols})
        return {"arch": arch_subset, "tables": light_tables}
        
    elif step_name == "metadata_analysis":
        safe_tables = [{"n": t.get("name"), "l": t.get("layer")} for t in tables[:40] if isinstance(t, dict)]
        return {"arch": arch_subset, "tables": safe_tables}
        
    elif step_name == "final_blueprint":
        return {
            "arch": arch_subset,
            "table_count": len(tables),
            "pipeline_tasks": len(results.get("pipeline_design", {}).get("tasks", []) if isinstance(results.get("pipeline_design"), dict) else []),
            "roles": results.get("governance_security", {}).get("roles", []) if isinstance(results.get("governance_security"), dict) else []
        }
        
    return {"arch": arch_subset, "context": "Refer to optimized subsets"}

def prune_for_ddl(schema: dict) -> dict:
    tables = []
    for t in (schema.get("tables", []) if isinstance(schema, dict) else []):
        if not isinstance(t, dict): continue
        cols = [{"name": c.get("name"), "type": c.get("type"), "pk": c.get("pk", False), "fk": c.get("fk", False), "ref": c.get("ref")} for c in t.get("columns", [])]
        tables.append({"name": t.get("name"), "columns": cols})
    return {"tables": tables}

def build_prompt(step_name: str, requirements: Dict[str, Any], data_profile: Dict[str, Any], results: Dict[str, Any]) -> str:
    step = STEP_MAP.get(step_name, step_name)
    pruned = prune_results(results, step)
    lod_mode = "macro" if step == "architecture" else ("meso" if step == "schema_modeling" else "micro")
    profile_txt = compress_profile(data_profile, mode=lod_mode)
    req_txt = "; ".join(f"{k}:{v}" for k, v in requirements.items() if v and k not in ["db", "schema", "tables"])
    arch = results.get("architecture_strategy", {})
    paradigm = str(arch.get("modeling_paradigm", "STAR_SCHEMA")).upper().replace(" ", "_")

    if step in ["architecture", "architecture_strategy"]:
        p = ARCH_STRATEGY_PROMPT.replace("__req__", req_txt).replace("__profile__", profile_txt)
    elif step == "schema_modeling":
        layers = ", ".join(arch.get("layers", ["Bronze", "Silver", "Gold"]))
        batch_ctx = requirements.get("batch_context", "Full Model")
        inventory = ", ".join(requirements.get("global_inventory", []))
        p = SCHEMA_MODELING_PROMPT.replace("__layers__", layers).replace("__arch_type__", str(arch.get("architecture_type", ""))).replace("__paradigm__", paradigm).replace("__profile__", profile_txt).replace("__batch_context__", batch_ctx).replace("__inventory__", inventory)
    elif step == "pipeline":
        p = PIPELINE_PROMPT.replace("__schema__", json.dumps(pruned))
    elif step == "gov_rbac":
        p = GOV_RBAC_PROMPT.replace("__schema__", json.dumps(pruned))
    elif step == "ddl":
        # Check both 'target_table_schema' and 'schema_modeling' for DDL generation
        schema_src = results.get("target_table_schema") or results.get("schema_modeling") or {}
        p = DDL_PROMPT.replace("__table_schema__", json.dumps(prune_for_ddl(schema_src)))
    elif step == "history":
        p = HISTORY_PROMPT.replace("__now__", datetime.datetime.now().isoformat())
    elif step == "metadata_analysis":
        p = METADATA_PROMPT.replace("__schema__", json.dumps(pruned))
    elif step == "relationship_design":
        p = RELATIONSHIP_PROMPT.replace("__schema__", json.dumps(pruned))
    elif step == "final_blueprint":
        p = FINAL_BLUEPRINT_PROMPT.replace("__results__", json.dumps(pruned))
    else: p = f"Step: {step_name}\nContext: {json.dumps(pruned)}"
    return p

STEP_JSON_SCHEMAS = {
    "architecture_strategy": {
        "type": "object",
        "properties": {
            "architecture_type":   {"type": "string"},
            "modeling_paradigm":   {"type": "string"},
            "layers":              {"type": "array",  "items": {"type": "string"}},
            "mermaid_diagram":     {"type": "string"},
            "complexity":          {"type": "string"},
            "reasoning_summary":   {"type": "string"},
            "fitness_metrics":     {"type": "object"},
            "data_flow":           {"type": "object"},
            "governance":          {"type": "object"},
        },
        "required": ["architecture_type", "modeling_paradigm", "layers", "mermaid_diagram"]
    },
    "schema_modeling": {
        "type": "object",
        "properties": {
            "tables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name":    {"type": "string"},
                        "layer":   {"type": "string"},
                        "columns": {"type": "array", "items": {"type": "object"}}
                    },
                    "required": ["name", "layer", "columns"]
                }
            },
            "mermaid_diagram": {"type": "string"}
        },
        "required": ["tables", "mermaid_diagram"]
    },
    "relationship_design": {
        "type": "object",
        "properties": {
            "rel": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "f": {"type": "string"},
                        "t": {"type": "string"},
                        "c": {"type": "string"}
                    },
                    "required": ["f", "t", "c"]
                }
            },
            "mermaid_diagram": {"type": "string"}
        },
        "required": ["rel", "mermaid_diagram"]
    },
    "pipeline_design": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "n": {"type": "string"},
                        "s": {"type": "string"},
                        "t": {"type": "string"},
                        "l": {"type": "string"}
                    },
                    "required": ["n", "s", "t", "l"]
                }
            },
            "mermaid_diagram": {"type": "string"}
        },
        "required": ["tasks", "mermaid_diagram"]
    },
    "governance_security": {
        "type": "object",
        "properties": {
            "roles": {"type": "array", "items": {"type": "object"}},
            "mask":  {"type": "array", "items": {"type": "object"}},
            "compliance_checklist": {"type": "array", "items": {"type": "string"}},
            "mermaid_diagram": {"type": "string"}
        },
        "required": ["roles", "mask", "compliance_checklist", "mermaid_diagram"]
    },
    "ddl_generation": {
        "type": "object",
        "properties": {
            "ddl_sql":       {"type": "string"},
            "grant_sql":     {"type": "string"},
            "transform_sql": {"type": "string"}
        },
        "required": ["ddl_sql", "grant_sql"]
    },
    "metadata_analysis": {
        "type": "object",
        "properties": {
            "lin":  {"type": "array", "items": {"type": "object"}},
            "tags": {"type": "array", "items": {"type": "object"}}
        },
        "required": ["lin", "tags"]
    },
    "final_blueprint": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "score":   {"type": "number"},
            "documentation": {
                "type": "object",
                "properties": {
                    "executive_summary": {"type": "string"},
                    "architecture_decision": {"type": "string"},
                    "key_entities": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["executive_summary", "architecture_decision"]
            }
        },
        "required": ["summary", "score", "documentation"]
    },
    "history": {
        "type": "object",
        "properties": {
            "version":     {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "change_log":  {"type": "array", "items": {"type": "string"}}
        },
        "required": ["assumptions"]
    },
}

_FALLBACK_SCHEMA = {"type": "object"}

def get_json_schema(task_type: str) -> dict:
    return STEP_JSON_SCHEMAS.get(task_type, _FALLBACK_SCHEMA)

SYSTEM_PROMPT_SUFFIXES = {
    "claude-3-5-sonnet": "\n\nCRITICAL: Output ONLY raw JSON. No thinking tags. No preamble. Start response with { directly.",
    "claude-3-7-sonnet": "\n\nCRITICAL: Output ONLY raw JSON. No <thinking> blocks. No preamble. Start response with { directly.",
    "claude-sonnet-4-6": "\n\nCRITICAL: Output ONLY raw JSON. No <thinking> blocks. No preamble. No explanation. Start response with { directly.",
    "claude-opus-4-6":   "\n\nCRITICAL: Output ONLY raw JSON. No <thinking> blocks. No preamble. Start response with { directly.",
    "claude-4-sonnet":   "\n\nCRITICAL: Output ONLY raw JSON. No <thinking> blocks. No preamble. Start response with { directly.",
    "claude-4-opus":     "\n\nCRITICAL: Output ONLY raw JSON. No <thinking> blocks. No preamble. Start response with { directly.",
    "mistral-large2":    "\n\nCRITICAL: Output ONLY raw JSON. No markdown fences. No explanation.",
    "mistral-large":     "\n\nCRITICAL: Output ONLY raw JSON. No markdown fences. No explanation.",
    "llama3.1-70b":      "\n\nIMPORTANT: Raw JSON only. No ```json fences. No preamble.",
    "llama4-maverick":   "\n\nIMPORTANT: Raw JSON only. No ```json fences. No preamble.",
    "snowflake-arctic":  "\n\nRESPOND WITH JSON ONLY. No prose before or after.",
    "deepseek-r1":       "\n\nJSON ONLY. No <think> tags. Raw object only.",
    "openai-gpt-4.1":    "\n\nReturn only valid JSON. No markdown.",
    "openai-gpt-5":      "\n\nReturn only valid JSON. No markdown.",
}

def get_system_prompt(model: str, task_type: str = None) -> str:
    suffix = SYSTEM_PROMPT_SUFFIXES.get(model.lower(), "\n\nJSON ONLY. No markdown.")
    if task_type and task_type != "architecture_strategy":
        base = """You are an Enterprise Data Architecture & Schema Validation Engine.

Your role is to validate, correct, and enforce consistency across ALL pipeline stages:
- Architecture Strategy
- Schema Modeling
- Pipeline Design
- Governance
- Relationships
- DDL Generation

PRIMARY GOAL:
Ensure a fully consistent, complete, production-grade data architecture lifecycle with no missing layers, no broken relationships, and no schema drift.

═══════════════════════════════════════════════
GLOBAL FIX RULES (APPLY TO ALL STEPS)
═══════════════════════════════════════════════

1. LAYER COMPLETENESS ENFORCEMENT
- The Architecture and Schema MUST dynamically include all layers appropriate for the selected architecture type:
  * For Medallion: Bronze, Silver, Gold, Consumption layers.
  * For Data Vault 2.0: Ingestion/Stage, Raw Vault (Hubs, Links, Satellites), Business Vault, Info Marts.
  * For Lakehouse: Raw/Landing, Cleaned/Conformed, Curated/Enriched, semantic layers.
  * For Hybrid Cloud: Cloud storage, On-prem storage, Hybrid Integration layers.
- Do NOT force a single hardcoded layer structure on all architecture types. Allow layers, subgraphs, and node structures to be fully dynamic and tailored to the chosen architecture model.
- If any core layer of the chosen architecture model is missing → auto-generate it.

2. SINGLE SOURCE OF TRUTH RULE
- Architecture defines FLOW only
- Schema defines STRUCTURE only
- Never mix pipeline logic with schema logic

3. SURROGATE KEY ENFORCEMENT (STRICT)
- ALL relationships MUST use *_sk keys
- Business keys (*_id) are attributes ONLY
- NO exceptions allowed
- NO OLTP-based relationships allowed

4. RELATIONSHIP VALIDATION RULE
- Every FK must reference a valid *_sk key
- Remove invalid or orphan relationships
- Ensure referential integrity across all layers

5. SCHEMA COMPLETENESS RULE
- Must include:
  - Fact tables
  - Dimension tables
  - Staging (Bronze)
  - Conformed (Silver)
  - Marts (Gold)
  - Semantic/KPI layer tables
- No duplicate or overlapping entities across layers

6. MERMAID DIAGRAM RULE
- Architecture: flowchart LR ONLY (pipeline view)
- Schema: erDiagram ONLY (relational view)
- Must NOT be truncated
- Must include ALL layers explicitly
- Absolutely NO unescaped double quotes inside diagram string values. Use single quotes or raw text for node labels.
- NODE LABEL SYNTAX: CORRECT: node_id[Plain text] or node_id['Label']. WRONG: node_id["Label"] — this BREAKS JSON parsing. Never use double-quoted node labels.

7. CONSISTENCY RULE (CROSS-STEPS)
- Architecture → Schema → Pipeline must align
- No mismatched naming
- No missing lineage continuity
- No re-architecture in downstream steps

8. NORMALIZATION RULE
- Remove duplicate entities across layers
- Ensure each entity exists in correct lifecycle stage only
- No semantic duplication

9. SNOWFLAKE TABLE TYPE RULE
- Always generate standard tables (`CREATE TABLE`).
- Do NOT generate Hybrid Tables (`CREATE HYBRID TABLE`).
- Do NOT mix hybrid and standard tables, as Snowflake does not support cross-table-type foreign key constraints, which will cause deployment errors.

═══════════════════════════════════════════════
ARCHITECTURE FIX RULES
═══════════════════════════════════════════════
- Represent the high-level data flow of the chosen architecture.
- Do NOT hardcode a static sequence (e.g. Sources -> Ingestion -> Bronze -> Silver -> Gold -> Consumption). Instead, dynamically build the flowchart using subgraphs representing layers and nodes representing sources, processing zones, and serving systems.
- No low-level columns or PK/FK details.

═══════════════════════════════════════════════
SCHEMA FIX RULES
═══════════════════════════════════════════════
- Must include full warehouse design
- Must include all layers appropriate to the selected architecture
- Must include modeling structures matching the paradigm (e.g., Fact/Dimension for Star/Snowflake, Hub/Link/Satellite for Data Vault)
- If using Star Schema or Snowflake Modeling, must prefix dimension tables in the Gold layer/Dimensional Model with 'DIM_' and fact tables with 'FACT_' (in UPPERCASE). If using Data Vault 2.0, follow Hub (`hub_`), Link (`lnk_`), Satellite (`sat_`) naming conventions.
- Must enforce surrogate key relationships only
- Must not include ingestion or source systems

═══════════════════════════════════════════════
OUTPUT RULE
═══════════════════════════════════════════════
- Return ONLY corrected JSON matching the requested schema specifications
- No explanations
- No markdown
- No commentary
- Must be production-ready and fully validated

═══════════════════════════════════════════════
FINAL VALIDATION CHECK (MANDATORY)
═══════════════════════════════════════════════
Before output, ensure:
✔ All layers exist in architecture and schema
✔ No missing or duplicate tables
✔ All relationships use *_sk keys
✔ No orphan references
✔ Mermaid diagrams are complete
✔ Architecture and schema are fully aligned
✔ No structural drift across pipeline stages
"""
        return base + suffix
    return SYSTEM_PROMPT + suffix