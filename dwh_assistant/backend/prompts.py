import json
from typing import Dict, Any, List
import datetime

# ═══════════════════════════════════════════════
# 1. MASTER SYSTEM PROMPT (Industrial Enforcement)
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

STRICT UNIFICATION & CONSISTENCY RULES:
1. Output ONLY valid JSON.
2. No explanations, no markdown, no comments.
3. Never truncate output.
4. Maintain absolute consistent naming across all layers. Every layer, table, and task must match the selected architecture type and modeling paradigm.
5. All downstream tabs (Schema, Pipeline, Governance, DDL, Lineage) must be fully unified and generated from the same Phase 1 architectural decision.
6. The system must NOT use static templates or hardcoded placeholders (like 'T1', 'T2', 'SRC', or 'LNZ'). Every element must dynamically adapt based on the selected architecture and dataset context.
7. Each dataset must produce a completely different, context-aware result across all tabs while maintaining full consistency and alignment between them.
8. Use surrogate keys (*_sk) for all relationships. Business keys (*_id) are attributes only.
9. Separate pipeline design from schema design strictly.
10. Never mix architecture, schema, and UI logic.
11. CRITICAL MERMAID JSON RULE: Never use unescaped double quotes inside the mermaid_diagram string value. For node labels, use single quotes or raw text inside brackets (e.g. Node[Label] or Node['Label']). Never use double quotes inside node definitions. Ensure all newlines in the diagram string are properly escaped as \n.
12. MERMAID NODE LABEL SYNTAX (MANDATORY): For node labels with spaces or special characters, use ONLY:
    CORRECT: node_id[Plain text label]         <- preferred, no quotes needed
    CORRECT: node_id['Single quoted label']    <- acceptable with single quotes
    WRONG:   node_id["Double quoted label"]    <- FATAL ERROR: breaks JSON string parsing
13. SNOWFLAKE TABLE TYPE RULE: Always generate standard tables (`CREATE TABLE`). Do NOT generate Hybrid Tables (`CREATE HYBRID TABLE`) or mix hybrid and standard tables.

SUPPORTED ARCHITECTURES:
- Three-tier Architecture: Standard separation of storage, processing, and reporting.
- Cloud Data Warehouse Architecture: Separate compute and storage (e.g. Snowflake, BigQuery, Redshift) with elastic scalability.
- Lakehouse Architecture: Combines data lake flexibility with warehouse querying and governance.
- Medallion Architecture: Sequential processing layers: Bronze (raw), Silver (cleaned), and Gold (business-ready).
- Modern ELT Architecture: Load raw source data first, then perform transformations directly inside the warehouse.

SUPPORTED DATA MODELING PARADIGMS:
- Star Schema: Common dimensional design using central Fact tables and surrounding Dimension tables.
- Snowflake Schema: Dimensional design where dimensions are normalized into multiple sub-tables.
- Fact Constellation / Galaxy Schema: Dimensional design where multiple Fact tables share common Dimension tables.
- Data Vault: Uses Hubs (business keys), Links (relationships), and Satellites (context/history) to organize data.

INDEPENDENT DESIGN MANDATE:
Each dataset and profile must be analyzed independently on its own technical merits. Do NOT reuse generic templates, assumptions, or warehouse-first defaults.

PIPELINE VIEW RULES (Architecture Tab):
- Show a flowchart representing the high-level data flow through the architecture layers.
- The diagram must be fully dynamic and driven by the AI-generated structure.
- Do NOT hardcode or output a predefined or statically coded layout.
- Use ONLY: flowchart LR or graph LR.
- Show ONLY high-level data layers (e.g., Bronze, Silver, Gold, Ingestion, Serving) and core stages of the system flow.
- Do NOT include individual database table names, schema objects, or detailed source/target names within those layers.

SCHEMA VIEW RULES (Warehouse Tab):
- Use ONLY: erDiagram.
- Must include Fact/Dimension tables (or Hub/Link/Satellites for Data Vault), columns, types, PK, FK, and relationships.
- Must NOT include source systems, ingestion layers, or pipeline flows.
"""



# ═══════════════════════════════════════════════
# ARCHITECTURE & PARADIGM REGISTRIES
# ═══════════════════════════════════════════════

ARCH_TYPES = {
    "three_tier": "Three-tier Architecture",
    "cloud_dwh": "Cloud Data Warehouse Architecture",
    "lakehouse": "Lakehouse Architecture",
    "medallion": "Medallion Architecture",
    "modern_elt": "Modern ELT Architecture"
}

PARADIGM_RULES = {
    "STAR_SCHEMA": "Star Schema Modeling",
    "SNOWFLAKE": "Snowflake Schema Modeling",
    "GALAXY": "Galaxy Schema (Fact Constellation)",
    "DATA_VAULT": "Data Vault 2.0 Modeling",
    "NORMALIZED": "Normalized 3NF Modeling",
    "EVENT_STREAM": "Event Stream / Topic Modeling"
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
Step: Architecture Strategy

Profile: __profile__
Requirements: __req__

ANALYZE AND DECIDE:

Evaluate profile characteristics:
- Data volume, velocity, variety
- Source systems (warehouse/files/APIs/streams)
- Team capabilities (junior/mid/senior)
- Latency tolerance (real-time/hourly/daily/weekly)
- Compliance requirements
- Growth trajectory
- Cost constraints

Consider architecture options:
- Three-tier: Traditional separation, on-prem or cloud
- Cloud DWH: Elastic compute-storage, native governance
- Lakehouse: Open formats, ML + BI unified
- Medallion: Bronze-Silver-Gold refinement layers
- Modern ELT: Load raw, transform in-warehouse

Consider modeling paradigms:
- Star: Single process, denormalized dims
- Galaxy: Multiple processes, shared dims
- Snowflake: Normalized dim hierarchies
- Data Vault: Multi-source, extreme auditability
- Normalized: OLTP-style, high integrity
- Event Stream: Real-time, append-only

REASON THROUGH:
- What patterns in profile point to specific architecture?
- What constraints eliminate options?
- What trade-offs matter most for this case?
- Which paradigm fits data relationships?

CRITICAL EVALUATION RULES:
1. If `architecture_preference` or `modeling_preference` is "AI Recommendation", you MUST independently evaluate the best fit based on the data.
2. DO NOT default to Medallion Architecture or Galaxy Schema simply because they are advanced. You MUST prove why a simpler or different architecture (e.g., Star Schema, Cloud DWH, Three-tier) isn't a better fit.
3. Compare multiple candidate architectures and schema strategies.
4. Justify the final selection with clear reasoning tied directly to workload characteristics (latency, scalability, governance, transformation complexity, ingestion patterns, analytical use cases).
5. Generate adaptive, context-aware outputs without any hardcoded architectural bias or forced template mapping.
6. VOLUME CONSTRAINTS: If Data Volume is <1GB or 1-10GB, you are STRICTLY FORBIDDEN from selecting Medallion Architecture or Lakehouse Architecture, as they are severe overkill for small datasets. You must default to a simpler architecture like Cloud Data Warehouse or Three-tier.

MERMAID DIAGRAM STRUCTURE GUIDE:
You must generate a "mermaid_diagram" that visualizes your chosen architecture using a `flowchart LR` format.
Design the diagram to look like a high-level Technical Pipeline DAG, showing the high-level data flow through your selected layers.

MANDATORY Adaptation Rules — you MUST follow all of these:
1. Visualize the data flow as a clean, high-level pipeline DAG. Connect the layers sequentially to show how data moves from source to consumption.
2. Identify and visualize the REAL layer names that fit YOUR chosen architecture (e.g., Stage → Conformed → Curated, Landing → Raw → Cleaned, Bronze → Silver → Gold).
3. The source nodes must name the REAL source systems from the data profile.
4. Consumer nodes must reflect the REAL consumers from the requirements.
5. Include a Governance node that lists the ACTUAL compliance frameworks and link it to the layers.
6. Use `classDef` and `class` statements to style your layers professionally. Use distinct colors for each architectural stage.
7. Output ONLY high-level architectural layers and core stages. NO table names, NO column names, NO schema objects.

OUTPUT (JSON):
{
  "architecture_type": "YOUR_CHOICE",
  "modeling_paradigm": "YOUR_CHOICE",
  "layers": ["Custom layers matching your architecture"],
  "mermaid_diagram": "flowchart LR\\n  [YOUR DYNAMIC FLOW DESIGN ADAPTED TO THE REFERENCE TEMPLATE]",
  "reasoning": "Multi-paragraph explanation of WHY this architecture and paradigm fit THIS profile better than alternatives. Reference specific metrics from profile.",
  "alternatives_considered": [
    {"option": "X", "why_rejected": "Specific reason from profile"},
    {"option": "Y", "why_rejected": "Specific reason from profile"}
  ],
  "fitness_metrics": {"Complexity": N, "Cost": N, "Scalability": N, "Performance": N, "Security": N}
}
"""

# STEP 2: Physical Schema Modeling
SCHEMA_MODELING_PROMPT = """
Step: Schema Design

Architecture: __arch_type__
Paradigm: __paradigm__
Blueprint: __blueprint__
Profile: __batch_context__

DESIGN MANDATE:
Create schema matching YOUR chosen paradigm and architecture.

Paradigm Guidelines (not rules):
- Star: Facts + denormalized dims, *_sk joins
- Galaxy: Multiple facts sharing conformed dims
- Snowflake: Facts + normalized dim sub-tables
- Data Vault: Hubs (keys) + Links (rels) + Satellites (attrs)
- Normalized: 3NF, minimal redundancy
- Event Stream: Immutable events, time-ordered

Layer Guidelines (adapt to your architecture):
- Use layer names that make sense for your architecture
- Align with layers defined in architecture step
- Place entities in appropriate lifecycle stage

Naming Conventions:
- Use conventions that match paradigm
- Star/Galaxy: FACT_*, DIM_* common but not mandatory
- Data Vault: hub_*, lnk_*, sat_* standard
- Pick consistent pattern, stick with it

Key Rules (minimal constraints):
- Primary keys must exist
- Foreign keys must reference valid targets
- No circular references
- Each entity in one layer
- Relationships must be logical
- Mermaid ERD Structure: Group and structure the erDiagram layer by layer with comment headers (e.g. `%% ─── BRONZE LAYER ───`, `%% ─── SILVER LAYER ───`). Only clean visual types (string, int, float, boolean, date, timestamp) are allowed. Never include parameters/parentheses in type declarations (e.g. use varchar or string, NOT varchar(50)). Table names must collapse extra underscores and be clean (e.g. no C___G_S).

CRITICAL: Design for THIS data model. Not generic template.

Inventory available: [__inventory__]
Use as guidance, adapt as needed for paradigm.

OUTPUT (JSON):
{
  "mermaid_diagram": "erDiagram\\n  [YOUR DESIGN]",
  "tables": [
    {
      "name": "your_table_name",
      "layer": "your_layer_name",
      "description": "Why this entity exists",
      "columns": [
        {"name": "col_name", "type": "type", "pk": bool, "fk": bool, "ref": "table.col if fk"}
      ]
    }
  ],
  "design_rationale": "Why this schema structure fits the chosen paradigm and architecture"
}
"""

# STEP 2.5: Metadata Analysis
METADATA_PROMPT = """
Step: Metadata & Lineage Analysis
Schema: __schema__

Analyze the provided schema and architecture definition. You must perform data lineage tracing and governance tagging.

REQUIREMENTS:
1. Identify all sensitive columns in the tables (e.g., columns containing names, emails, phones, SSNs, financial/medical data, passwords, etc.). Tag them as "PII", "SENSITIVE", or "CONFIDENTIAL" in the "tags" array.
2. Build a full column-level data lineage flow ("lin") from the raw source tables/fields to the target warehouse tables.
3. Every entry in "lin" should contain:
   - "s": The source object or field (e.g., "src_system.field_name" or a raw landing field)
   - "t": The target warehouse table name and column (e.g., "DIM_CUSTOMER.EMAIL_ADDRESS" or "hub_customer.customer_id")
4. Do NOT use static or placeholder values. Map actual source fields to actual target tables and columns generated in the Schema Modeling step.

OUTPUT FORMAT (JSON ONLY):
{
  "lin": [
    {"s": "source_system.column", "t": "TARGET_TABLE.COLUMN"}
  ],
  "tags": [
    {"o": "TARGET_TABLE.COLUMN", "tag": "PII | SENSITIVE | CONFIDENTIAL"}
  ]
}
"""

# STEP 3: Relationship Design
RELATIONSHIP_PROMPT = """
Step: Relationship Design
Schema: __schema__

Analyze the provided schema and create the primary-to-foreign key relationships.

CRITICAL MANDATE:
1. Relationships MUST be designed between the actual tables generated in Phase 2.
2. Use ONLY surrogate keys (`*_sk`) for all relationships.
3. Business keys (`*_id`) exist ONLY as attributes, NOT for defining relationships or foreign key mappings.
4. Ensure all foreign keys reference surrogate keys consistently.
5. Create a clean Mermaid erDiagram displaying these relationships. Use the erDiagram syntax (e.g., TABLE1 ||--o{ TABLE2 : relationship). Do NOT include attributes in this ER diagram (only table relationships).
6. Mermaid ERD Structure: Group and structure the erDiagram layer by layer with comment headers (e.g. `%% ─── BRONZE LAYER ───`, `%% ─── SILVER LAYER ───`). Group cross-layer relationships at the end under `%% ─── CROSS-LAYER RELATIONSHIPS ───`. Table names must be clean and not contain redundant underscores (e.g. C___G_S).

OUTPUT FORMAT (JSON ONLY):
{
  "rel": [
    {"f": "FROM_TABLE", "t": "TO_TABLE", "c": "1:N | 1:1 | N:M"}
  ],
  "mermaid_diagram": "erDiagram\\n  FROM_TABLE ||--o{ TO_TABLE : references\\n"
}
"""

# STEP 3: Derivative Steps
PIPELINE_PROMPT = """
Step: Pipeline Design

Architecture: __arch_type__
Paradigm: __paradigm__
Layers: __layers__
Schema: __schema__

DESIGN MANDATE:
Create transformation pipeline matching YOUR architecture and schema.

Flow patterns vary by architecture:
- Medallion: Raw → Bronze → Silver → Gold
- Cloud DWH: Staging → Conformed → Curated
- Lakehouse: Landing → Cleaned → Enriched
- Modern ELT: Load → Transform → Serve
- Three-tier: Extract → Process → Present

Design tasks that:
- Move data through your layers logically
- Transform appropriately for each stage
- Match grain and granularity needs
- Handle your specific data types

NO TEMPLATES. Design for THIS data flow.

OUTPUT (JSON):
{
  "mermaid_diagram": "flowchart LR\\n  [YOUR PIPELINE]",
  "tasks": [
    {"n": "task_name", "s": "source", "t": "target", "l": "what it does"}
  ],
  "pipeline_rationale": "Why this flow matches architecture and data characteristics"
}
"""

GOV_RBAC_PROMPT = """
Step: Governance Design

Architecture: __arch_type__
Schema: __schema__

DESIGN MANDATE:
Create security model for THIS dataset and compliance requirements.

Analyze:
- What sensitive data exists in schema?
- What compliance frameworks apply?
- What user roles make sense for this domain?
- What access patterns are needed?

Design:
- Roles appropriate for this use case
- Masking policies for sensitive columns
- Row-level security if needed
- Audit requirements

NO GENERIC ROLES. Design for THIS dataset domain.

OUTPUT (JSON):
{
  "mermaid_diagram": "graph LR\\n  [YOUR ACCESS MODEL]",
  "roles": [
    {"n": "ROLE_NAME", "g": [{"o": "object", "p": ["perms"]}]}
  ],
  "mask": [
    {"n": "column", "t": "mask_type", "e": "role"}
  ],
  "compliance_checklist": ["Items specific to this data domain"],
  "governance_rationale": "Why this security model fits requirements"
}
"""

DDL_PROMPT = """
Step: DDL & Deployment SQL Generation
Architecture: __arch_type__ | Paradigm: __paradigm__
Schema Context (Layer → Schema mapping and grouped tables): __schema_context__

Generate the target Snowflake SQL scripts derived EXCLUSIVELY from the schema_context above.
The schema_context defines each architecture layer, its resolved Snowflake schema name, and the tables belonging to that layer.

STRICT DDL RULES:
1. ALWAYS use standard `CREATE TABLE` statement syntax. Do NOT use `CREATE HYBRID TABLE`.
2. For each architecture layer in the schema_context:
   a. Emit: CREATE SCHEMA IF NOT EXISTS <schema_name>;
   b. Then emit: CREATE TABLE IF NOT EXISTS <schema_name>.<table_name> (...) for every table in that layer.
3. Use fully-qualified table names: <schema_name>.<table_name> throughout ALL statements.
4. Column types must use Snowflake-native types: NUMBER, VARCHAR, TIMESTAMP_NTZ, BOOLEAN, DATE, FLOAT.
5. Declare PRIMARY KEY constraints inline. Declare FOREIGN KEY constraints referencing the fully-qualified parent table.
6. NEVER use bind variables (e.g., `:batch_id`, `:date`) or session variables in your SQL. The code is executed directly by a driver that does not supply bindings. Use hardcoded mock values or SQL functions (e.g., `CURRENT_TIMESTAMP()`) instead.
7. Output the following three keys:
   - "ddl_sql": All CREATE SCHEMA + CREATE TABLE statements, ordered layer by layer.
   - "grant_sql": GRANT USAGE ON SCHEMA, GRANT SELECT/INSERT on tables, aligned to the RBAC roles in the architecture.
   - "transform_sql": One representative INSERT INTO or MERGE statement per layer showing the data load pattern. 
       CRITICAL: In `transform_sql`, NEVER reference invented streams, stages, or tables (e.g. `EXTERNAL_STAGE_...`). You must `SELECT` exclusively from the fully-qualified tables defined in the `schema_context` (e.g. querying the Bronze tables to load Silver).

NAMING CONTRACT:
- Schema names are pre-resolved in the schema_context — do NOT rename, abbreviate, or alter them.
- Table names are pre-resolved in the schema_context — do NOT rename or invent new tables.
- All FK references must use the fully-qualified <schema_name>.<parent_table> form.

OUTPUT FORMAT (JSON ONLY):
{
  "ddl_sql": "CREATE SCHEMA IF NOT EXISTS BRONZE;\nCREATE TABLE IF NOT EXISTS BRONZE.raw_orders (...);\n\nCREATE SCHEMA IF NOT EXISTS GOLD;\nCREATE TABLE IF NOT EXISTS GOLD.FACT_SALES (...);",
  "grant_sql": "GRANT USAGE ON SCHEMA BRONZE TO ROLE DATA_ENGINEER;\nGRANT SELECT ON TABLE GOLD.FACT_SALES TO ROLE BI_ANALYST;",
  "transform_sql": "INSERT INTO GOLD.FACT_SALES SELECT ... FROM SILVER.conformed_orders;"
}
"""

HISTORY_PROMPT = """
Step: History & Architectural Assumptions
Canonical Architecture: __arch_type__
Modeling Paradigm: __paradigm__
Architecture Layers: __layers__
Schema: __schema__

CRITICAL INHERITANCE MANDATE:
The architecture type, paradigm, and layers above are the SINGLE SOURCE OF TRUTH inherited from Phase 1.
All assumptions and change log entries MUST directly reference these exact architecture type, layers, and conformed table names. Do NOT fabricate or generalize.

Review the chosen architecture strategy, layers, and conformed tables. Generate the key structural assumptions and change log.

REQUIREMENTS:
1. Identify 3-5 critical technical and operational assumptions made for this design based on the selected architecture type and naming conventions.
2. Generate a change log history entry detailing the design steps taken (e.g., "v1.0 initial model setup using DATA_VAULT modeling paradigm").
3. All assumptions and change logs must relate directly to the chosen architecture, paradigm, and actual table names in the schema.
4. Output the current ISO timestamp as "generated_at".

OUTPUT FORMAT (JSON ONLY):
{
  "version": "v1.0",
  "generated_at": "__now__",
  "assumptions": [
    "Assumption statement tailored to the chosen architecture and dataset"
  ],
  "change_log": [
    "Change log description/revision detail tailored to the chosen architecture and dataset"
  ]
}
"""

# STEP 6: Final Blueprint
FINAL_BLUEPRINT_PROMPT = """
Step: Final Blueprint Synthesis
Results: __results__

Synthesize a comprehensive final architectural blueprint and technical documentation summarizing the completed unified warehouse design.

REQUIREMENTS:
1. "summary": A concise 10-word summary of the finalized data warehouse design.
2. "score": An architectural readiness and compliance score from 0 to 100 based on standard modeling practices.
3. "documentation": A dictionary containing:
   - "executive_summary": A detailed summary of the entire warehouse design, explaining how the selected architecture meets the business requirements and listing the specific layers.
   - "architecture_decision": A comprehensive technical justification of the chosen modeling paradigm (e.g. Star, Data Vault), storage design, security guardrails, and transformation flow.
   - "key_entities": A list of the key conformed tables and their specific business and architectural roles in the system.

OUTPUT FORMAT (JSON ONLY):
{
  "summary": "Concise 10-word summary",
  "score": 95,
  "documentation": {
    "executive_summary": "Detailed high-level business and technical summary...",
    "architecture_decision": "In-depth technical modeling and layer justifications...",
    "key_entities": [
      "TABLE_NAME: Brief explanation of its role"
    ]
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
        print(f"      [CONTEXT] Pruned {len(all_tables) - max_t} tables from profile to prevent token overflow.")
        
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
        "architecture_type": arch.get("architecture_type", "AI Recommended"),
        "modeling_paradigm": arch.get("modeling_paradigm", "Dynamic Paradigm"),
        "layers": arch.get("layers", ["Dynamic Layers"]),
        "data_model_blueprint": arch.get("data_model_blueprint", {}),
        "data_flow": arch.get("data_flow", {}),
        "governance": arch.get("governance", {})
    }
    
    if arch and step_name != "architecture":
        print(f"      [ARCHITECTURE REUSE] Reusing canonical context ({arch_subset['architecture_type']} / {arch_subset['modeling_paradigm']}) for {step_name}")

    if step_name == "pipeline":
        safe_tables = []
        for t in tables[:30]:
            if isinstance(t, dict):
                cols = [{"n": c.get("name"), "t": c.get("type")} for c in t.get("columns", []) if isinstance(c, dict)]
                safe_tables.append({"n": t.get("name"), "l": t.get("layer"), "cols": cols})
        return {"arch": arch_subset, "tables": safe_tables}

    elif step_name == "gov_rbac":
        safe_tables = []
        for t in tables[:30]:
            if isinstance(t, dict):
                cols = [{"n": c.get("name"), "t": c.get("type"), "flags": c.get("flags", [])} for c in t.get("columns", []) if isinstance(c, dict)]
                safe_tables.append({"n": t.get("name"), "l": t.get("layer"), "cols": cols})
        return {"arch": arch_subset, "tables": safe_tables}
        
    elif step_name == "relationship_design":
        light_tables = []
        for t in tables:
            if isinstance(t, dict):
                cols = [{"n": c.get("name"), "t": c.get("type"), "pk": c.get("pk"), "fk": c.get("fk"), "ref": c.get("ref")} for c in t.get("columns", []) if isinstance(c, dict) and (c.get("pk") or c.get("fk") or "sk" in str(c.get("name")) or "id" in str(c.get("name")))]
                light_tables.append({"n": t.get("name"), "l": t.get("layer"), "cols": cols})
        return {"arch": arch_subset, "tables": light_tables}
        
    elif step_name == "metadata_analysis":
        safe_tables = []
        for t in tables[:40]:
            if isinstance(t, dict):
                cols = [{"n": c.get("name"), "t": c.get("type"), "flags": c.get("flags", [])} for c in t.get("columns", []) if isinstance(c, dict)]
                safe_tables.append({"n": t.get("name"), "l": t.get("layer"), "cols": cols})
        return {"arch": arch_subset, "tables": safe_tables}
        
    elif step_name == "history":
        safe_tables = []
        for t in tables[:30]:
            if isinstance(t, dict):
                safe_tables.append({"n": t.get("name"), "l": t.get("layer")})
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
    if not isinstance(arch, dict): arch = {}
    paradigm = str(arch.get("modeling_paradigm", "DYNAMIC_PARADIGM")).upper().replace(" ", "_")
    arch_type = str(arch.get("architecture_type", "AI_RECOMMENDED")).upper().replace(" ", "_")
    layers_txt = ", ".join(arch.get("layers", ["Dynamic Layers"])) if isinstance(arch.get("layers"), list) else str(arch.get("layers", "Dynamic Layers"))

    if step in ["architecture", "architecture_strategy"]:
        p = ARCH_STRATEGY_PROMPT.replace("__req__", req_txt).replace("__profile__", profile_txt)
    elif step == "schema_modeling":
        layers = ", ".join(arch.get("layers", ["Dynamic Layers"]))
        batch_ctx = requirements.get("batch_context", "Full Model")
        inventory = ", ".join(requirements.get("global_inventory", []))
        blueprint_info = json.dumps(arch.get("data_model_blueprint", {}), indent=2)
        p = SCHEMA_MODELING_PROMPT.replace("__layers__", layers).replace("__arch_type__", str(arch.get("architecture_type", ""))).replace("__paradigm__", paradigm).replace("__profile__", profile_txt).replace("__batch_context__", batch_ctx).replace("__inventory__", inventory).replace("__blueprint__", blueprint_info)
        if batch_ctx != "Full Model":
            p += "\n\nCRITICAL BATCH GENERATION INSTRUCTION: You are processing a partial batch of tables. To prevent response truncation or token limits exhaustion, output ONLY the 'tables' list and 'design_rationale' in the JSON, and set 'mermaid_diagram' to a minimal placeholder (e.g. 'erDiagram\\n  %% Minimal diagram for batch'). Do NOT generate a large or detailed ER diagram now, as it will be designed in a later step."
    elif step == "pipeline":
        p = (PIPELINE_PROMPT
             .replace("__arch_type__", arch_type)
             .replace("__paradigm__", paradigm)
             .replace("__layers__", layers_txt)
             .replace("__schema__", json.dumps(pruned)))
    elif step == "gov_rbac":
        p = (GOV_RBAC_PROMPT
             .replace("__arch_type__", arch_type)
             .replace("__paradigm__", paradigm)
             .replace("__layers__", layers_txt)
             .replace("__schema__", json.dumps(pruned)))
    elif step == "ddl":
        # Build schema_context from pre-computed entry (set by orchestrator build_schema_context)
        # Falls back to prune_for_ddl on raw schema if context not yet available
        schema_ctx = results.get("schema_context") or {}
        if not schema_ctx:
            schema_src = results.get("target_table_schema") or results.get("schema_modeling") or {}
            schema_ctx = {"layers": [{"layer_name": "Warehouse", "schema_name": "WAREHOUSE", "tables": prune_for_ddl(schema_src).get("tables", [])}]}
        p = (DDL_PROMPT
             .replace("__arch_type__", arch_type)
             .replace("__paradigm__", paradigm)
             .replace("__schema_context__", json.dumps(schema_ctx, separators=(',', ':'))))
    elif step == "history":
        p = (HISTORY_PROMPT
             .replace("__arch_type__", arch_type)
             .replace("__paradigm__", paradigm)
             .replace("__layers__", layers_txt)
             .replace("__now__", datetime.datetime.now().isoformat())
             .replace("__schema__", json.dumps(pruned)))
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
            "architecture_type":          {"type": "string"},
            "modeling_paradigm":          {"type": "string"},
            "layers":                     {"type": "array",  "items": {"type": "string"}},
            "mermaid_diagram":            {"type": "string"},
            "complexity":                 {"type": "string"},
            "reasoning_summary":          {"type": "string"},
            "fitness_metrics":            {"type": "object"},
            "architecture_justification": {
                "type": "object",
                "properties": {
                    "why_chosen":             {"type": "string"},
                    "alternatives_rejected":  {"type": "array", "items": {"type": "string"}},
                    "assumptions_made":       {"type": "array", "items": {"type": "string"}},
                    "constraints_influenced": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["why_chosen", "alternatives_rejected", "assumptions_made", "constraints_influenced"]
            },
            "data_flow":                  {"type": "object"},
            "governance":                 {"type": "object"},
        },
        "required": ["architecture_type", "modeling_paradigm", "layers", "mermaid_diagram", "architecture_justification"]
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
            "version":      {"type": "string"},
            "generated_at": {"type": "string"},
            "assumptions":  {"type": "array", "items": {"type": "string"}},
            "change_log":   {"type": "array", "items": {"type": "string"}}
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
  * For Three-tier Architecture: Storage, Processing, Reporting layers.
  * For Cloud Data Warehouse Architecture: Staging, Conformed, Enriched layers.
  * For Lakehouse Architecture: Raw/Landing, Cleaned/Conformed, Curated/Enriched layers.
  * For Medallion Architecture: Bronze, Silver, Gold, Consumption layers.
  * For Modern ELT Architecture: Staging, Raw Warehouse, Transformed layers.
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
- Must include all necessary tables and layers for the specifically chosen architecture model and modeling paradigm.
- Ensure the schema aligns perfectly with the chosen architecture strategy (e.g. Medallion, Data Vault, Lakehouse).
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

10. UNIFIED FLOW & NO PLACEHOLDERS
- All downstream stages (Pipeline, Governance, DDL, Lineage) must strictly reference the actual table names, column schemas, and types generated in the Schema Modeling stage.
- Do NOT use generic placeholders or static stubs like 'T1', 'T2', 'SRC', or 'LNZ' in any diagram or list. Build a completely dynamic, context-aware layout unique to the input data.

═══════════════════════════════════════════════
ARCHITECTURE FIX RULES
═══════════════════════════════════════════════
- Represent the high-level data flow of the chosen architecture.
- Do NOT hardcode a static sequence (e.g. Sources -> Ingestion -> Bronze -> Silver -> Gold -> Consumption). Instead, dynamically build the flowchart using subgraphs representing layers and nodes representing sources, processing zones, and serving systems.
- Show ONLY high-level data layers (e.g., Bronze, Silver, Gold, Ingestion, Serving) and core structure.
- Do NOT include detailed table names or individual schema objects inside those layers.
- No low-level columns or PK/FK details.

═══════════════════════════════════════════════
SCHEMA FIX RULES
═══════════════════════════════════════════════
- Must include full warehouse design
- Must include all layers appropriate to the selected architecture
- Must include modeling structures matching the paradigm (e.g., Fact/Dimension for Star Schema or Snowflake Schema, Hub/Link/Satellite for Data Vault, shared dimensions for Galaxy Schema)
- If using Star Schema, Snowflake Schema, or Fact Constellation / Galaxy Schema: Must prefix dimension tables in the curated/reporting layer with 'DIM_' and fact tables with 'FACT_' (in UPPERCASE).
- If using Data Vault: Follow Hub (`hub_`), Link (`lnk_`), Satellite (`sat_`) naming conventions. Do NOT use fact or dimension tables.
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

# ═══════════════════════════════════════════════
# CONTINUATION PROMPT FOR TRUNCATED OUTPUTS
# ═══════════════════════════════════════════════
CONTINUATION_PROMPT = """
Your previous output was truncated. Please continue generating the JSON content from the exact character where it left off. Do not repeat the previous content, do not start a new JSON block, and do not wrap in markdown tags. Output ONLY the remaining valid JSON characters.
"""