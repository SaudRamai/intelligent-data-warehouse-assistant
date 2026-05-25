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
Step: Architecture Strategy & Master Blueprint
Context: __req__ | Profile: __profile__

CRITICAL ARCHITECTURE TAB MANDATE (Pipeline View Only):
1. MUST display the high-level data pipeline flow dynamically generated based on the selected architecture type and data sources.
2. The diagram MUST NOT be a static sequence like "Sources --> Ingestion --> Bronze --> Silver --> Gold --> Consumption". It must be a custom flowchart detailing the actual data sources from the profile (e.g., source tables or APIs), passing through subgraphs representing the architecture's layers, and ending with specific consumption nodes (e.g., dashboards, reporting, apps).
3. Do NOT include tables, attributes, or PK/FK details. The flowchart represents the structural data flow only.
4. The layers (subgraphs) must reflect the chosen architecture type (e.g. Three-tier, Cloud DWH, Lakehouse, Medallion, Modern ELT).
5. CRITICAL RECOMMENDATION MANDATE: Analyze the data profile and dynamically select the optimal architecture type and modeling paradigm. Do NOT default to Medallion or Star Schema unless explicitly justified by workload characteristics (e.g. Bronze/Silver/Gold flow fits Medallion, clean separation fits Three-tier).
6. INDEPENDENT DESIGN MANDATE: Each dataset and profile must be analyzed independently on its own technical merits. Do NOT reuse generic templates, assumptions, or warehouse-first defaults unless they are explicitly required and justified by this specific dataset's volume, latency, security, and workload characteristics.

STRICT OUTPUT (JSON ONLY):
{
  "mermaid_diagram": "flowchart LR\\n  subgraph Ingestion\\n    src_api[API Source]\\n  end\\n  subgraph Storage\\n    raw_zone[Raw Zone]\\n  end\\n  src_api --> raw_zone",
  "architecture_type": "THREE_TIER | CLOUD_DWH | LAKEHOUSE | MEDALLION | MODERN_ELT",
  "modeling_paradigm": "STAR_SCHEMA | SNOWFLAKE | GALAXY_SCHEMA | DATA_VAULT",
  "layers": ["List of layers matching architecture type"],
  "complexity": "L/M/H",
  "estimated_cost_tier": "L/M/H",
  "fitness_metrics": {"Complexity": 50, "Cost": 50, "Scalability": 80, "Performance": 80, "Security": 90},
  "reasoning_summary": "Detailed, multi-sentence architectural reasoning explaining why this specific architecture and paradigm were chosen over others.",
  "architecture_justification": {
    "why_chosen": "Specific technical reasons based on data volume, skills, latency, compliance, workload, etc.",
    "alternatives_rejected": ["List of alternative architectures analyzed and why they were rejected for this case"],
    "assumptions_made": ["Key technical or organizational assumptions made"],
    "constraints_influenced": ["Physical or business constraints that guided the decision"]
  },
  "data_model_blueprint": {
    "schema_type": "Star/Vault/Lakehouse/Normalized/Graph/EventStream",
    "core_entities": ["List"],
    "primary_relationships": ["List"]
  },
  "data_flow": {"ingestion": "Direct/Stream/Batch", "processing": "Dynamic/Normalized/Vault", "serving": "Analyst/API/Views"},
  "governance": {"security": "Mandate", "lineage": "Mandate"}
}
"""

# STEP 2: Physical Schema Modeling
SCHEMA_MODELING_PROMPT = """
Step: Physical Tables (Max 3 keywords per desc)
Arch: __arch_type__ | Paradigm: __paradigm__
Blueprint: __blueprint__
Context: __batch_context__

CRITICAL ROOT MANDATE: The pre-validated 'canonical_architecture' context and 'Blueprint' are the SINGLE SOURCE OF TRUTH.
Do NOT re-architect, rename layers, or change the modeling paradigm. Strictly inherit defined layer naming, architectural layer hierarchy, and FK relationships.
You MUST base your physical tables, columns, and ER diagram relationships strictly on the provided Blueprint's core_entities and primary_relationships.

MANDATORY SCHEMA TAB REQUIREMENTS (Detailed Schema Model Only):
1. MUST show the complete schema design derived from the Architecture and the Blueprint.
2. The schema details and entity structures MUST align with the chosen modeling paradigm and Blueprint:
   - For Star Schema: Entities must match facts/dimensions from the Blueprint. Must prefix dimension tables in the curated/reporting layer with 'DIM_' and fact tables with 'FACT_' (in UPPERCASE).
   - For Snowflake Schema: Dimensional design where dimensions are normalized into separate sub-tables.
   - For Fact Constellation / Galaxy Schema: Shared dimensions across multiple fact tables.
   - For Data Vault: Entities must be Hubs (`hub_`), Links (`lnk_`), and Satellites (`sat_`). Do NOT generate facts or dimensions.
3. Mandatory Requirements:
   - Must include full table structures with columns and data types
   - Must define all Primary Keys (PK)
   - Must define all Foreign Keys (FK)
   - Must include relationships between tables
   - Naming must match the chosen paradigm exactly
   - Must be fully derived from the Architecture strategy
4. Key Rule: ONLY schema/modeling entities are allowed. No source systems, ingestion, or pipeline layers. No high-level architecture elements.
5. Dependency Rule Between Tabs: Architecture = pipeline flow view (high-level only), Schema = detailed warehouse design (low-level relational model). Schema must be generated using Architecture as reference, but only extracting warehouse-relevant entities. Both must be strictly separated with no overlap.

CRITICAL SURROGATE KEY & RELATIONAL MODELING MANDATE:
1. Use ONLY surrogate keys (`*_sk`) for all relationships (PK/FK model).
2. Business keys (`*_id` or similar OLTP identifiers) should exist ONLY as non-key attributes, NOT for defining relationships or foreign key mappings.
3. Ensure all foreign keys reference surrogate keys consistently (e.g., use `patient_sk`, `room_sk` instead of `patient_id`, `room_id`).
4. Avoid duplicate identity representation of the same entity using both business keys and surrogate keys for joins.
5. Maintain strict modeling standards matching the selected paradigm and ensure full referential integrity across all entities.

CRITICAL RULES FOR COLUMNS & ENTITIES:
1. Ensure each entity is absolutely unique. Do NOT output duplicate or repeating table definitions.
2. Normalize all attributes to eliminate semantic overlap.
3. Strictly build foreign keys (PK/FK mappings) exclusively between target warehouse tables. Do NOT reference upstream/external systems.
4. Use ONLY generic Mermaid-compatible primitive data types (int, string, float, date, timestamp, boolean) in child columns and the erDiagram.

CRITICAL RULE: ALL tables and foreign key targets MUST use EXACTLY these names:
[__inventory__]
Do NOT invent tables that are not in this list.
Ensure the mermaid diagram is highly compressed and non-truncated.

OUTPUT (JSON ONLY):
{
  "mermaid_diagram": "erDiagram\\n  TABLE ||--o{ OTHER : rel",
  "tables": [
    {
      "name": "string",
      "layer": "YOUR_DYNAMIC_LAYER_NAME",
      "columns": [{"name": "entity_sk", "type": "int", "pk": true, "fk": true, "ref": "table.entity_sk"}]
    }
  ]
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
Canonical Architecture: __arch_type__
Modeling Paradigm: __paradigm__
Architecture Layers: __layers__
Schema: __schema__

CRITICAL INHERITANCE MANDATE:
The architecture type, paradigm, and layers above are the SINGLE SOURCE OF TRUTH inherited from Phase 1.
Do NOT re-architect, change layer names, or deviate from the canonical structure defined above.
Every pipeline task, subgraph, and node in the Mermaid diagram MUST align with these exact architecture layers.

Analyze the selected architecture strategy and conformed tables, and design the ELT/ETL transformation pipeline tasks.

REQUIREMENTS:
1. Design realistic orchestration tasks that flow data sequentially through the chosen architecture's layers:
   - If MEDALLION: flow must go from Raw Source Files -> Bronze tables, Bronze -> Silver (cleansing/transformation), Silver -> Gold (business metrics, fact/dim tables).
   - If DATA_VAULT: flow must go from Staging tables -> parallel Hub/Link/Satellite loading, Hubs/Links/Satellites -> Info Marts.
   - If LAKEHOUSE or CLOUD_DWH: flow must go from Landing -> Conformed -> Curated.
   - If THREE_TIER: flow must go from Operational Sources -> Storage Layer -> Processing Layer -> Reporting Layer.
   - If MODERN_ELT: flow must go from Sources -> Raw Warehouse -> Transformed/Serving Layer.
2. For each task, define:
   - "n": A clear name representing the task (e.g., "load_dim_customer" or "transform_silver_orders")
   - "s": The input source table or source file path (e.g., "raw.customer_csv" or "bronze.customer_raw")
   - "t": The target conformed warehouse table name (which must be a real table name from the conformed schema)
   - "l": A description of the transformation logic applied (e.g., cleansing, joining, type-casting, MD5 hashing of keys)
3. Construct a visual Mermaid flowchart diagram representing this execution DAG.
   - Group the processing tasks into subgraphs matching the architectural layers defined in 'Architecture Layers' above.
   - The nodes in the diagram MUST be the actual warehouse table names and sources. Do NOT use static place-holders like T1, T2, SRC, or LNZ.
   - Use "flowchart LR" or "graph LR" for the diagram.

OUTPUT FORMAT (JSON ONLY):
{
  "mermaid_diagram": "flowchart LR\\n  subgraph LayerName\\n    table_id['Table Label']\\n  end\\n  src --> table_id",
  "tasks": [
    {"n": "task_name", "s": "source_table_or_file", "t": "target_table", "l": "transformation_logic_description"}
  ]
}
"""

GOV_RBAC_PROMPT = """
Step: Governance & Security Design
Canonical Architecture: __arch_type__
Modeling Paradigm: __paradigm__
Architecture Layers: __layers__
Schema: __schema__

CRITICAL INHERITANCE MANDATE:
The architecture type, paradigm, and layers above are the SINGLE SOURCE OF TRUTH inherited from Phase 1.
Do NOT re-architect or change the governance model. All roles, grants, and table references in the diagram must strictly match the conformed tables and layers from this architecture.

Analyze the provided conformed schema columns (specifically focusing on columns marked with sensitive/PII flags) and the selected architecture strategy. Design the security roles, column-level masking policies, compliance checklists, and access flow.

REQUIREMENTS:
1. Define a list of RBAC roles ("roles") appropriate for the chosen architecture (e.g. INGEST_OPERATOR for raw ingestion, DATA_ENGINEER for conformed storage, BI_ANALYST for final consumption).
   - "n": Name of the role
   - "g": List of grants. Each grant must specify:
     - "o": The database object name (e.g., specific target tables or schemas)
     - "p": The access privilege list (e.g., ["SELECT", "INSERT", "USAGE"])
2. Define masking policies ("mask") for the actual sensitive/PII columns detected in the conformed schema (e.g. patient name, email, salary, SSN).
   - "n": Name of the column to mask (must be a real column name from the conformed schema)
   - "t": Masking algorithm or method (e.g., "SHA2", "PARTIAL_MASK", "FULL_MASK")
   - "e": The role to which this mask is enforced (e.g., "BI_ANALYST")
3. Generate a compliance checklist ("compliance_checklist") outlining specific audit and privacy compliance steps tailored to the dataset domain (e.g. HIPAA audit logging, GDPR right-to-be-forgotten mapping).
4. Construct a Mermaid flowchart ("mermaid_diagram") depicting how users, roles, security masking policies, and conformed schema tables are related.
   - Use "graph LR" or "flowchart LR".
   - The nodes MUST represent the actual conformed table names and defined roles. Do NOT use static placeholders like SRC or LNZ.

OUTPUT FORMAT (JSON ONLY):
{
  "mermaid_diagram": "graph LR\\n  subgraph Access\\n    role_id['Role Label']\\n  end\\n  role_id --> table_id",
  "roles": [
    {
      "n": "ROLE_NAME",
      "g": [{"o": "OBJECT_NAME", "p": ["SELECT", "USAGE"]}]
    }
  ],
  "mask": [
    {"n": "COLUMN_NAME", "t": "MASKING_TYPE", "e": "ENFORCED_ROLE"}
  ],
  "compliance_checklist": [
    "Compliance checklist item description"
  ]
}
"""

DDL_PROMPT = """
Step: DDL & Deployment SQL Generation
Schema: __table_schema__

Generate the target Snowflake SQL scripts matching the conformed table structures exactly.

STRICT DDL RULES:
1. ALWAYS use standard `CREATE TABLE` statement syntax. Do NOT use `CREATE HYBRID TABLE`.
2. Ensure all columns, primary keys, and foreign keys are created correctly for standard Snowflake tables.
3. Generate the following outputs:
   - "ddl_sql": The CREATE TABLE statements, primary key declarations, and foreign key constraints.
   - "grant_sql": Grant privileges (SELECT, INSERT, UPDATE, USAGE) on the generated schemas and tables to the custom roles designed in the governance step.
   - "transform_sql": A sample INSERT INTO or MERGE statement demonstrating how data is loaded/transformed into the target table from its staging/bronze counterpart.

OUTPUT FORMAT (JSON ONLY):
{
  "ddl_sql": "CREATE TABLE ...",
  "grant_sql": "GRANT SELECT ON ...",
  "transform_sql": "INSERT INTO ..."
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
        # Check both 'target_table_schema' and 'schema_modeling' for DDL generation
        schema_src = results.get("target_table_schema") or results.get("schema_modeling") or {}
        p = DDL_PROMPT.replace("__table_schema__", json.dumps(prune_for_ddl(schema_src)))
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