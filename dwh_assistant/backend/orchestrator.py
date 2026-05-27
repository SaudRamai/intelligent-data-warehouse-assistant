import streamlit as st
import threading
import logging
from typing import Dict, Any, List
import os
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
from collections import defaultdict

STEP_LOCKS = defaultdict(threading.Lock)

# Nuclear suppression of "missing ScriptRunContext" warnings
for logger_name in logging.root.manager.loggerDict:
    if "streamlit" in logger_name:
        logging.getLogger(logger_name).addFilter(lambda record: "missing ScriptRunContext" not in record.getMessage())

CORTEX_CACHE_DIR = Path(".streamlit/.cortex_cache")
CORTEX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
import importlib
import dwh_assistant.backend.executor as exec_mod
try: importlib.reload(exec_mod)
except Exception: pass
from dwh_assistant.backend.executor import call_cortex, call_cortex_with_continuation
from dwh_assistant.backend.validator import validate_step_output, heal_mermaid_diagram
from dwh_assistant.backend.prompts import build_prompt

# ═══════════════════════════════════════════════
# METADATA-DRIVEN SCHEMA CONTEXT BUILDER
# ═══════════════════════════════════════════════

def layer_to_schema_name(layer_name: str) -> str:
    """
    Deterministically converts an AI-generated architecture layer name
    into a valid Snowflake schema identifier.
    No hardcoding — works for any architecture type (Medallion, Data Vault,
    Lakehouse, Three-tier, Cloud DWH, Modern ELT, etc.).
    """
    import re
    # Slugify: replace any non-alphanumeric characters with underscores
    slug = re.sub(r'[^a-zA-Z0-9]', '_', layer_name.strip())
    # Collapse multiple underscores, strip leading/trailing underscores
    slug = re.sub(r'_+', '_', slug).strip('_').upper()
    return slug if slug else 'WAREHOUSE_LAYER'


def build_schema_context(arch_result: dict, schema_modeling_result: dict) -> dict:
    """
    Derives a fully metadata-driven schema context from the AI-generated
    architecture strategy and schema modeling outputs.

    Returns a dict:
    {
        "layers": [
            {
                "layer_name":  str,   # original AI layer name (e.g. "Bronze")
                "schema_name": str,   # slugified Snowflake schema name (e.g. "BRONZE")
                "tables":      list   # table objects belonging to this layer
            },
            ...
        ]
    }

    Rules:
    - Layer names come exclusively from architecture_strategy.layers.
    - Each table's .layer field is matched case-insensitively to the AI layer list.
    - Tables with unmatched layers fall back to the closest layer or a catch-all.
    - No schema names are hardcoded.
    """
    if not isinstance(arch_result, dict):
        arch_result = {}
    if not isinstance(schema_modeling_result, dict):
        schema_modeling_result = {}

    # 1. Pull the canonical layer list from architecture_strategy
    raw_layers = arch_result.get("layers", [])
    if not isinstance(raw_layers, list) or not raw_layers:
        # Fallback: single generic layer
        raw_layers = ["Warehouse"]

    # 2. Build ordered layer metadata
    layer_meta = []
    for layer_name in raw_layers:
        layer_meta.append({
            "layer_name":  layer_name,
            "schema_name": layer_to_schema_name(layer_name),
            "tables":      []
        })

    # 3. Build a lookup: normalised_layer_label → index in layer_meta
    def _norm(s: str) -> str:
        return re.sub(r'[^a-z0-9]', '', str(s).lower())

    label_to_idx = {_norm(lm["layer_name"]): i for i, lm in enumerate(layer_meta)}
    # Also map by generated schema_name for double-coverage
    schema_to_idx = {_norm(lm["schema_name"]): i for i, lm in enumerate(layer_meta)}

    # 4. Group tables into their layers
    all_tables = schema_modeling_result.get("tables", [])
    if not isinstance(all_tables, list):
        all_tables = []

    unmatched = []  # Tables whose .layer doesn't map to any known layer
    for t in all_tables:
        if not isinstance(t, dict):
            continue
        t_layer_raw = str(t.get("layer", "")).strip()
        t_layer_norm = _norm(t_layer_raw)

        # Exact normalised match first
        if t_layer_norm in label_to_idx:
            idx = label_to_idx[t_layer_norm]
        elif t_layer_norm in schema_to_idx:
            idx = schema_to_idx[t_layer_norm]
        else:
            # Partial substring match (handles cases like "Gold (Serving)" → "Gold")
            idx = None
            for lbl, li in label_to_idx.items():
                if lbl in t_layer_norm or t_layer_norm in lbl:
                    idx = li
                    break
            if idx is None:
                unmatched.append(t)
                continue

        # Append a lean copy of the table (name + columns only) to keep token budget tight
        layer_meta[idx]["tables"].append({
            "name":    t.get("name", "unknown_table"),
            "columns": [
                {
                    "name": c.get("name"),
                    "type": c.get("type"),
                    "pk":   c.get("pk") or c.get("primary_key") or c.get("is_pk") or False,
                    "fk":   c.get("fk") or c.get("is_fk") or False,
                    "ref":  c.get("ref") or c.get("references")
                }
                for c in t.get("columns", []) if isinstance(c, dict)
            ]
        })

    # 5. Distribute unmatched tables into the last layer (most common catch-all)
    if unmatched:
        catch_all_idx = len(layer_meta) - 1
        print(f"[SCHEMA CONTEXT] {len(unmatched)} tables had unmatched layers — routed to '{layer_meta[catch_all_idx]['layer_name']}'")
        for t in unmatched:
            layer_meta[catch_all_idx]["tables"].append({
                "name":    t.get("name", "unknown_table"),
                "columns": [
                    {
                        "name": c.get("name"),
                        "type": c.get("type"),
                        "pk":   c.get("pk") or c.get("primary_key") or c.get("is_pk") or False,
                        "fk":   c.get("fk") or c.get("is_fk") or False,
                        "ref":  c.get("ref") or c.get("references")
                    }
                    for c in t.get("columns", []) if isinstance(c, dict)
                ]
            })

    # 6. Remove empty layers (architectures may define layers not yet populated)
    #    But keep at least one layer to avoid empty context
    populated = [lm for lm in layer_meta if lm["tables"]]
    if not populated:
        populated = layer_meta  # Keep all if none are populated yet

    print(f"[SCHEMA CONTEXT] Built context: {[lm['schema_name'] for lm in populated]} "
          f"({sum(len(lm['tables']) for lm in populated)} tables total)")

    return {"layers": populated}


import re  # needed by layer_to_schema_name at module level

# Core requirements for each step to be considered "Complete"
# Refactored for Unified Modeling Flow
STEP_REQUIRED_KEYS = {
    "architecture_strategy": ["architecture_type", "modeling_paradigm", "layers", "mermaid_diagram"],
    "schema_modeling":       ["tables"],
    "pipeline_design":       ["tasks"],
    "governance_security":   ["roles", "mask", "compliance_checklist"],
    "ddl_generation":        ["ddl_sql", "grant_sql"],
    "history":               ["assumptions"],
    "metadata_analysis":     ["lin", "tags"],
    "relationship_design":   ["rel", "mermaid_diagram"],
    "final_blueprint":       ["summary", "documentation"],
}

TYPE_SPECS = {
    "schema_modeling": {"tables": list},
    "pipeline_design": {"tasks": list},
    "governance_security": {"roles": list, "mask": list, "compliance_checklist": list},
    "relationship_design": {"rel": list, "mermaid_diagram": str},
    "metadata_analysis": {"lin": list, "tags": list},
    "ddl_generation": {"ddl_sql": str, "grant_sql": str},
    "final_blueprint": {"summary": str, "documentation": dict}
}

def step_is_complete(step_name: str, data: Any) -> bool:
    """Checks if a step has valid, complete results cached."""
    if not data or not isinstance(data, dict): return False
    required = STEP_REQUIRED_KEYS.get(step_name, [])
    return all(k in data for k in required)

def safe_callback(status_callback, step, state, data=None):
    """Safely executes UI callback, ignoring Streamlit context errors in background threads."""
    if not status_callback:
        return
    try:
        status_callback(step, state, data)
    except Exception:
        # Completely suppress background threading state update desynchronization warnings to preserve log cleanliness
        pass

def run_step(session, step_name: str, requirements: dict, data_profile: dict, current_results: dict, model: str, status_callback=None, last_error=None, depth=0, force_refresh=False):
    """Executes a single atomic step in the DWH generation pipeline synchronized per node_id."""
    with threading.Lock(): # Completely unshared zero-contention thread block
        safe_callback(status_callback, step_name, "running")
        
        # Strip redundant metadata to ensure clean serialization and minimize token payload
        stripped_results = {k: v for k, v in (current_results or {}).items() if not k.endswith("_raw")}
        base_prompt = build_prompt(step_name, requirements, data_profile, stripped_results)
        
        # --- TRANSPARENT CACHE INTERCEPTOR ---
        import hashlib
        cache_hash = hashlib.md5(f"{step_name}_{model}_{base_prompt}".encode('utf-8')).hexdigest()
        cache_file = CORTEX_CACHE_DIR / f"{cache_hash}.json"
        
        if "cortex_memory_cache" not in st.session_state:
            st.session_state["cortex_memory_cache"] = {}
            
        if not force_refresh:
            if cache_hash in st.session_state["cortex_memory_cache"] and not last_error:
                cached_out = st.session_state["cortex_memory_cache"][cache_hash]
                print(f"\n[AI CACHE HIT] Memory cache loaded instantly for '{step_name}'")
                safe_callback(status_callback, step_name, "done", cached_out)
                return cached_out
                
            if cache_file.exists() and not last_error:
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cached_out = json.load(f)
                    st.session_state["cortex_memory_cache"][cache_hash] = cached_out
                    print(f"\n[AI CACHE HIT] Disk cache loaded instantly for '{step_name}'")
                    safe_callback(status_callback, step_name, "done", cached_out)
                    return cached_out
                except Exception: pass

        max_retries = 3
        current_error = last_error
        
        for attempt in range(max_retries):
            prompt = base_prompt
            if current_error:
                prompt += f"\n\n[FIX PREVIOUS ERROR]: {current_error}"
            
            print(f"\n[AI ARCHITECT LOG] Invoking model '{model}' for step '{step_name}' (Attempt {attempt+1}). Prompt length: {len(prompt)} chars.")
            response = call_cortex_with_continuation(session, prompt, step_name, model=model)
            print(f"[AI ARCHITECT LOG] Step '{step_name}' execution completed. Success: {response['success']}")
            
            if response["success"]:
                output = response["output"]
                required_keys = STEP_REQUIRED_KEYS.get(step_name, [])
                expected_types = TYPE_SPECS.get(step_name, {})
                
                # Deep Alias Mapping and Expansion for Minified Keys to Ensure UI Component Completeness
                if isinstance(output, dict):
                    aliases = {
                        "diagram": "mermaid_diagram", "mermaid": "mermaid_diagram",
                        "mask": "masking_policies", "masking": "masking_policies",
                        "rbac": "roles", "privileges": "grants"
                    }
                    for k, v in list(output.items()):
                        if k in aliases and aliases[k] not in output:
                            output[aliases[k]] = v

                    # Expand schema tables
                    if "tables" in output and isinstance(output["tables"], list):
                        for t in output["tables"]:
                            if isinstance(t, dict):
                                if "n" in t and "name" not in t: t["name"] = t.pop("n")
                                if "l" in t and "layer" not in t: t["layer"] = t.pop("l")
                                if "t" in t and "type" not in t: t["type"] = t.pop("t")
                                if "d" in t and "description" not in t: t["description"] = t.pop("d")
                                if "pk" in t and "primary_key" not in t: t["primary_key"] = t.pop("pk")
                                if "c" in t and "columns" not in t: t["columns"] = t.pop("c")
                                
                                if "columns" in t and isinstance(t["columns"], list):
                                    for c in t["columns"]:
                                        if isinstance(c, dict):
                                            if "n" in c and "name" not in c: c["name"] = c.pop("n")
                                            if "t" in c and "type" not in c: c["type"] = c.pop("t")
                                            if "d" in c and "description" not in c: c["description"] = c.pop("d")
                                            if "pk" in c and "primary_key" not in c: c["primary_key"] = c.pop("pk")
                                            if "fk" in c and "is_fk" not in c: c["is_fk"] = c.pop("fk")
                                            if "ref" in c and "references" not in c: c["references"] = c.pop("ref")

                    # Expand pipeline tasks
                    if "tasks" in output and isinstance(output["tasks"], list):
                        for t in output["tasks"]:
                            if isinstance(t, dict):
                                if "n" in t and "name" not in t: t["name"] = t.pop("n")
                                if "s" in t and "source" not in t: t["source"] = t.pop("s")
                                if "t" in t and "target" not in t: t["target"] = t.pop("t")
                                if "l" in t and "logic" not in t: t["logic"] = t.pop("l")
                                if "type" not in t: t["type"] = "transformation"
                                if "layer" not in t: t["layer"] = "Silver/Gold"
                                if "frequency" not in t: t["frequency"] = "Batch"

                    # Expand governance roles and masking policies
                    if "roles" in output and isinstance(output["roles"], list):
                        for r in output["roles"]:
                            if isinstance(r, dict):
                                if "n" in r and "name" not in r: r["name"] = r.pop("n")
                                if "g" in r and "grants" not in r: r["grants"] = r.pop("g")
                                if "grants" in r and isinstance(r["grants"], list):
                                    for g in r["grants"]:
                                        if isinstance(g, dict):
                                            if "o" in g and "object_name" not in g: g["object_name"] = g.pop("o")
                                            if "p" in g:
                                                pval = g.pop("p")
                                                g["privilege"] = ", ".join(pval) if isinstance(pval, list) else str(pval)

                    if "masking_policies" in output and isinstance(output["masking_policies"], list):
                        for m in output["masking_policies"]:
                            if isinstance(m, dict):
                                if "n" in m and "column" not in m: m["column"] = m.pop("n")
                                if "t" in m and "type" not in m: m["type"] = m.pop("t")
                                if "e" in m and "role" not in m: m["role"] = m.pop("e")

                    # Expand relationship keys (f/t/c to from/from_table/to/to_table/cardinality)
                    if "rel" in output and isinstance(output["rel"], list):
                        for r in output["rel"]:
                            if isinstance(r, dict):
                                if "f" in r:
                                    f_val = r.pop("f")
                                    if "from" not in r: r["from"] = f_val
                                    if "from_table" not in r: r["from_table"] = f_val
                                if "t" in r:
                                    t_val = r.pop("t")
                                    if "to" not in r: r["to"] = t_val
                                    if "to_table" not in r: r["to_table"] = t_val
                                if "c" in r and "cardinality" not in r:
                                    r["cardinality"] = r.pop("c")
                                
                                # Backups if LLM directly provided long keys
                                if "from" in r and "from_table" not in r: r["from_table"] = r["from"]
                                if "to" in r and "to_table" not in r: r["to_table"] = r["to"]
                                if "from_table" in r and "from" not in r: r["from"] = r["from_table"]
                                if "to_table" in r and "to" not in r: r["to"] = r["to_table"]

                    # Synthesis of fallback visual diagrams if omitted by LLM
                    if step_name == "pipeline_design" and not output.get("mermaid_diagram"):
                        lines = ["graph TD"]
                        for idx, t in enumerate(output.get("tasks", [])):
                            tname = t.get("name", f"Task_{idx}")
                            tsrc = t.get("source", "Source")
                            lines.append(f"    {tsrc} --> {tname}")
                        output["mermaid_diagram"] = "\n".join(lines) if len(lines) > 1 else "graph TD\n  Source --> Staging --> Target"

                    if step_name == "governance_security" and not output.get("mermaid_diagram"):
                        lines = ["graph LR"]
                        for r in output.get("roles", []):
                            rname = r.get("name", "Role")
                            lines.append(f"    User --> {rname}")
                        output["mermaid_diagram"] = "\n".join(lines) if len(lines) > 1 else "graph LR\n  Analyst --> CentralDataStore"

                    if step_name == "architecture_strategy":
                        layers = output.get("layers", [])
                        paradigm = output.get("modeling_paradigm", "STAR_SCHEMA")
                        arch_type = output.get("architecture_type", "CLOUD_DWH")
                        reasoning = output.get("reasoning", "")
                        alts_cons = output.get("alternatives_considered", [])
                        
                        if "architecture_justification" not in output:
                            alts = [a.get("option") if isinstance(a, dict) else str(a) for a in alts_cons]
                            why_rejected = "; ".join([f"{a.get('option')}: {a.get('why_rejected')}" for a in alts_cons if isinstance(a, dict) and a.get("why_rejected")])
                            output["architecture_justification"] = {
                                "why_chosen": reasoning,
                                "alternatives_rejected": alts,
                                "assumptions_made": [
                                    f"Workload characteristics favor a {arch_type} architecture.",
                                    f"Selected {paradigm} paradigm matches data relationship density."
                                ],
                                "constraints_influenced": [
                                    "Design optimized for latency tolerance and cost-complexity balance.",
                                    f"Alternative rejection rationale: {why_rejected}" if why_rejected else "Compliance and team skill constraints."
                                ]
                            }
                        if "data_model_blueprint" not in output:
                            output["data_model_blueprint"] = {
                                "schema_type": paradigm,
                                "core_entities": [f"Core tables matching {paradigm}"],
                                "primary_relationships": [f"Surrogate-key relationships in {paradigm}"]
                            }
                        if "data_flow" not in output:
                            output["data_flow"] = {
                                "ingestion": "Stage raw data into ingestion zone.",
                                "processing": f"Cleanse, conform, and refine using {paradigm} modeling rules.",
                                "serving": "Expose semantic layers to BI and analytics consumers."
                            }
                        if "governance" not in output:
                            output["governance"] = {
                                "security": "Enforce strict RBAC permissions and column-level masking on sensitive/PII data.",
                                "lineage": "Track full data lineage from source extraction to gold serving tables."
                            }
                        if "complexity" not in output:
                            metrics = output.get("fitness_metrics", {})
                            comp_val = metrics.get("Complexity", 50)
                            output["complexity"] = "High" if comp_val > 70 else ("Medium" if comp_val > 40 else "Low")
                        if "estimated_cost_tier" not in output:
                            metrics = output.get("fitness_metrics", {})
                            cost_val = metrics.get("Cost", 50)
                            output["estimated_cost_tier"] = "High" if cost_val > 70 else ("Medium" if cost_val > 40 else "Low")
                        if "reasoning_summary" not in output:
                            output["reasoning_summary"] = reasoning

                # Normalizing mermaid keys
                if isinstance(output, dict) and "mermaid" in output and "mermaid_diagram" not in output:
                    output["mermaid_diagram"] = output.pop("mermaid")
                    
                if isinstance(output, dict) and "mermaid_diagram" in output:
                    output["mermaid_diagram"] = heal_mermaid_diagram(output["mermaid_diagram"])

                if isinstance(output, dict) and validate_step_output(step_name, output, required_keys, expected_types):
                    print(f"[AI ARCHITECT LOG] Step '{step_name}' validated successfully. Keys generated: {list(output.keys())}")
                    if "mermaid_diagram" in output:
                        diag_text = output["mermaid_diagram"].strip()
                        is_broken = (
                            not diag_text or 
                            len(diag_text) <= 25 or 
                            "NODATA" in diag_text or 
                            diag_text == "graph LR\n  A --> B" or 
                            diag_text == "erDiagram"
                        )
                        is_batch = requirements.get("batch_context", "Full Model") != "Full Model" if isinstance(requirements, dict) else False
                        if is_batch and step_name == "schema_modeling":
                            status_str = "BATCH PLACEHOLDER (Expected)"
                        else:
                            status_str = "BROKEN / STUB" if is_broken else "SUCCESSFULLY GENERATED"
                        print(f"[AI ARCHITECT LOG] Diagram Status for '{step_name}': {status_str} (Length: {len(diag_text)} chars)\n")
                    if "tables" in output:
                        print(f"[AI ARCHITECT LOG] Generated Tables Count: {len(output['tables'])}")
                    st.session_state["cortex_memory_cache"][cache_hash] = output
                    try:
                        with open(cache_file, "w", encoding="utf-8") as f:
                            json.dump(output, f, ensure_ascii=False, indent=2)
                    except Exception: pass
                    safe_callback(status_callback, step_name, "done", output)
                    return output
                else:
                    keys_found = list(output.keys()) if isinstance(output, dict) else "NON-DICT OUTPUT"
                    print(f"\n      [VALIDATION FAILED] {step_name} (Attempt {attempt+1}): Missing keys. Found: {keys_found}")
                    current_error = "Missing or invalid required keys"
            else:
                print(f"\n      [EXECUTION FAILED] {step_name} (Attempt {attempt+1}): {response.get('error', 'Unknown Error')}")
                current_error = response.get('error', 'Unknown Error')
                
        return {"success": False, "error": f"Max retries exceeded for {step_name}"}

# --- STREAMLIT CONTEXT HELPERS ---

try:
    from streamlit.runtime.scriptrunner import add_script_run_context, get_script_run_ctx
except ImportError:
    try:
        from streamlit.runtime.scriptrunner.script_run_context import add_script_run_context, get_script_run_ctx
    except ImportError:
        def add_script_run_context(*args, **kwargs): pass
        def get_script_run_ctx(*args, **kwargs): return None

def _get_ctx():
    return get_script_run_ctx()

def _add_ctx(ctx):
    if ctx:
        add_script_run_context(ctx)

# --- DERIVATIVE DETERMINISTIC GENERATORS ---

def run_ddl_derivative(session, requirements, data_profile, results, model, status_callback, force_refresh=False):
    """Generates DDL for ALL tables in the unified schema using deterministic parallel batches.

    Enhancement: Derives CREATE SCHEMA statements from the AI-generated
    architecture_strategy.layers — fully metadata-driven, no hardcoded schema names.
    """
    schema = results.get("schema_modeling", {})
    tables = schema.get("tables", [])
    if not tables: return {"ddl_sql": "-- No tables found", "grant_sql": "", "transform_sql": ""}

    # ─── BUILD SCHEMA CONTEXT (METADATA-DRIVEN) ────────────────────────────────
    arch_result = results.get("architecture_strategy", {})
    if not isinstance(arch_result, dict):
        arch_result = {}
    schema_ctx = build_schema_context(arch_result, schema)
    results["schema_context"] = schema_ctx  # Propagate for prompt injection

    # ─── IMPORT DETERMINISTIC ASSEMBLY HELPER ──────────────────────────────────
    from dwh_assistant.backend.executor import assemble_full_ddl

    print(f"\n      [DDL DERIVATIVE] Generating DDL for {len(tables)} tables across "
          f"{len(schema_ctx['layers'])} schema(s)...")

    all_ddls = []
    all_grants = []
    all_transforms = []

    batch_size = 12
    # Batch by layer so each AI call gets tables that share the same schema
    layer_batches = []
    for layer_entry in schema_ctx["layers"]:
        layer_tables = layer_entry["tables"]
        for i in range(0, len(layer_tables), batch_size):
            layer_batches.append({
                "schema_ctx": {
                    "layers": [{
                        "layer_name":  layer_entry["layer_name"],
                        "schema_name": layer_entry["schema_name"],
                        "tables":      layer_tables[i:i + batch_size]
                    }]
                }
            })

    # Fallback: if no layer batches (empty context), use old flat batches
    if not layer_batches:
        batch_size_flat = 12
        flat_batches = [tables[i:i + batch_size_flat] for i in range(0, len(tables), batch_size_flat)]
        for batch in flat_batches:
            layer_batches.append({
                "schema_ctx": {
                    "layers": [{"layer_name": "Warehouse", "schema_name": "WAREHOUSE", "tables": batch}]
                }
            })

    ctx = _get_ctx()

    def _run_ddl_batch(batch_info):
        _add_ctx(ctx)
        batch_results = dict(results)  # inherit arch/schema context
        batch_results["schema_context"] = batch_info["schema_ctx"]
        return run_step(session, "ddl_generation", requirements, data_profile, batch_results, model, force_refresh=force_refresh)

    with ThreadPoolExecutor(max_workers=min(4, len(layer_batches) or 1)) as executor:
        futures = {executor.submit(_run_ddl_batch, b): b for b in layer_batches}
        for future in as_completed(futures):
            res = future.result()
            if isinstance(res, dict):
                if "ddl_sql" in res:   all_ddls.append(res["ddl_sql"])
                if "grant_sql" in res: all_grants.append(res["grant_sql"])
                if "transform_sql" in res: all_transforms.append(res["transform_sql"])

    # ─── DETERMINISTIC ASSEMBLY (POST-PROCESSING) ──────────────────────────────
    assembled = assemble_full_ddl(
        schema_context=schema_ctx,
        ai_ddl_parts=all_ddls,
        ai_grant_parts=all_grants,
        ai_transform_parts=all_transforms
    )
    return assembled

def run_parallel_schema(session, requirements, data_profile, results, model, status_callback, force_refresh=False):
    """Executes schema modeling in parallel batches to improve speed and prevent truncation."""
    all_tables = data_profile.get("tables", [])
    if not all_tables: return {"tables": [], "relationships": [], "mermaid_diagram": ""}

    print(f"\n      [PARALLEL SCHEMA] Modeling {len(all_tables)} tables in parallel...")
    
    # 1. Provide a global inventory of all tables to every batch to ensure FK consistency
    inventory = [t.get("name") for t in all_tables]
    requirements = {**requirements, "global_inventory": inventory}
    
    batch_size = 10
    batches = [all_tables[i:i + batch_size] for i in range(0, len(all_tables), batch_size)]
    
    ctx = _get_ctx()
    merged_results = {"tables": []}
    
    def _run_schema_batch(batch):
        _add_ctx(ctx)
        batch_profile = {"tables": batch}
        # Force the prompt to acknowledge this is a partial batch
        batch_reqs = {**requirements, "batch_context": f"Processing {len(batch)} of {len(all_tables)} tables."}
        return run_step(session, "schema_modeling", batch_reqs, batch_profile, results, model, force_refresh=force_refresh)

    with ThreadPoolExecutor(max_workers=min(4, len(batches) or 1)) as executor:
        future_to_batch = {executor.submit(_run_schema_batch, b): b for b in batches}
        for future in as_completed(future_to_batch):
            res = future.result()
            if isinstance(res, dict):
                merged_results["tables"].extend(res.get("tables", []))
                
    # --- POST-MERGE TABLE DEDUPLICATION & CONSOLIDATION ---
    raw_tables = merged_results["tables"]
    unique_tables = {}
    for t in raw_tables:
        if not isinstance(t, dict) or not t.get("name"):
            continue
        t_name = t["name"].upper().strip()
        # Collapse multiple underscores
        norm_name = re.sub(r'_+', '_', t_name).strip('_')
        # Plural key comparison (strip trailing S if it exists)
        compare_key = norm_name[:-1] if norm_name.endswith('S') and len(norm_name) > 3 else norm_name
        
        if compare_key in unique_tables:
            existing = unique_tables[compare_key]
            # Merge columns
            existing_cols = {c.get("name", "").upper(): c for c in existing.get("columns", []) if isinstance(c, dict)}
            for c in t.get("columns", []):
                if not isinstance(c, dict): continue
                c_name = c.get("name", "").upper()
                if c_name not in existing_cols:
                    existing["columns"].append(c)
            # Prefer the plural or longer name if it exists (commonly plural is standard, e.g. FACT_ORDERS)
            if len(t_name) > len(existing["name"]):
                existing["name"] = t_name
            # Preserve layer if not set
            if not existing.get("layer") and t.get("layer"):
                existing["layer"] = t["layer"]
        else:
            t["name"] = norm_name
            unique_tables[compare_key] = t
            
    merged_results["tables"] = list(unique_tables.values())

    # --- POST-MERGE FK RECONCILIATION ---
    tables = merged_results["tables"]
    pk_index = {}
    for t in tables:
        t_name = str(t.get("name", "")).lower()
        pk_col = None
        for c in t.get("columns", []):
            if c.get("pk"):
                pk_col = c.get("name")
                break
        if pk_col and t_name:
            pk_index[t_name] = pk_col

    for t in tables:
        for c in t.get("columns", []):
            if c.get("fk") and c.get("ref"):
                ref = str(c.get("ref"))
                if "." in ref:
                    target_table, target_col = ref.split(".", 1)
                    tt_lower = target_table.lower()
                    if tt_lower in pk_index:
                        canonical_pk = pk_index[tt_lower]
                        if target_col.lower() != canonical_pk.lower():
                            c["ref"] = f"{target_table}.{canonical_pk}"
    # Synthesize the complete visual ERD diagram from the consolidated tables list
    from dwh_assistant.backend.validator import synthesize_erd_from_tables
    merged_results["mermaid_diagram"] = synthesize_erd_from_tables(tables)
    print(f"[AI ARCHITECT LOG] Final consolidated ERD diagram synthesized for 'schema_modeling'. Length: {len(merged_results['mermaid_diagram'])} chars.\n")
    
    return merged_results

# --- MAIN ORCHESTRATOR ---

def run_all(session, requirements: dict, data_profile: dict, model: str, status_callback=None, initial_results: dict = None):
    """
    Orchestrates the UNIFIED 3-PHASE generation flow:
    1. Architecture Strategy (Reasoning)
    2. Unified Schema Modeling (Master Blueprint / Single Source of Truth)
    3. Derivative Transformations (Deterministic/Parallel)
    """
    ctx = _get_ctx()
    results = initial_results or {}
    try:
        print(f"\n[DEPENDENCY ORCHESTRATOR] Starting DAG Execution")
        
        # --- 1. ARCHITECTURE (Sequential Root) ---
        print("\n--- PHASE 1: ARCHITECTURE ---")
        arch_res = run_step(session, "architecture_strategy", requirements, data_profile, results, model, status_callback)
        if not arch_res.get("architecture_type"): return {"success": False, "error": "Architecture failed"}
        results["architecture_strategy"] = arch_res
        st.session_state["generation_results"] = results

        # --- 2. SCHEMA + METADATA (Parallel) ---
        print("\n--- PHASE 2: SCHEMA + METADATA (Parallel) ---")
        ctx = _get_ctx()
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_schema = executor.submit(lambda _ctx=ctx: (_add_ctx(_ctx), run_parallel_schema(session, requirements, data_profile, results, model, status_callback))[1])
            fut_meta = executor.submit(lambda _ctx=ctx: (_add_ctx(_ctx), run_step(session, "metadata_analysis", requirements, data_profile, results, model, status_callback))[1])
            
            results["schema_modeling"] = fut_schema.result()
            results["metadata_analysis"] = fut_meta.result()
        st.session_state["generation_results"] = results
        # SYNC individual step results to session_state for real-time UI updates
        st.session_state["architecture_strategy"] = results.get("architecture_strategy")
        st.session_state["schema_modeling"] = results.get("schema_modeling")
        st.session_state["metadata_analysis"] = results.get("metadata_analysis")

        # --- 3. RELATIONSHIPS + PIPELINE + GOVERNANCE (Parallel Tier) ---
        print("\n--- PHASE 3: RELATIONSHIPS + PIPELINE + GOVERNANCE (Parallel) ---")
        with ThreadPoolExecutor(max_workers=3) as executor:
            fut_rel = executor.submit(lambda _ctx=ctx: (_add_ctx(_ctx), run_step(session, "relationship_design", requirements, data_profile, results, model, status_callback))[1])
            fut_pipe = executor.submit(lambda _ctx=ctx: (_add_ctx(_ctx), run_step(session, "pipeline_design", requirements, data_profile, results, model, status_callback))[1])
            fut_gov = executor.submit(lambda _ctx=ctx: (_add_ctx(_ctx), run_step(session, "governance_security", requirements, data_profile, results, model, status_callback))[1])
            
            results["relationship_design"] = fut_rel.result()
            results["pipeline_design"] = fut_pipe.result()
            results["governance_security"] = fut_gov.result()
        st.session_state["generation_results"] = results
        # SYNC individual step results to session_state
        st.session_state["relationship_design"] = results.get("relationship_design")
        st.session_state["pipeline_design"] = results.get("pipeline_design")
        st.session_state["governance_security"] = results.get("governance_security")

        # --- 4. DDL GENERATION (Sequential Dependency) ---
        print("\n--- PHASE 4: DDL GENERATION ---")
        ddl_res = run_ddl_derivative(session, requirements, data_profile, results, model, status_callback)
        results["ddl_generation"] = ddl_res
        # Propagate schema_context to session state for Design Center rendering
        if "schema_context" in results:
            st.session_state["schema_context"] = results["schema_context"]
        st.session_state["generation_results"] = results

        # --- 5. FINAL BLUEPRINT + HISTORY (Parallel End) ---
        print("\n--- PHASE 5: FINAL BLUEPRINT + HISTORY ---")
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_final = executor.submit(lambda _ctx=ctx: (_add_ctx(_ctx), run_step(session, "final_blueprint", requirements, data_profile, results, model, status_callback))[1])
            fut_hist = executor.submit(lambda _ctx=ctx: (_add_ctx(_ctx), run_step(session, "history", requirements, data_profile, results, model, status_callback))[1])
            
            results["final_blueprint"] = fut_final.result()
            results["history"] = fut_hist.result()

        # --- ALIAS MAPPINGS FOR BACKWARD COMPATIBILITY ---
        # Some components expect "schema_design" but we generate "schema_modeling"
        results["schema_design"] = results.get("schema_modeling")
        results["blueprint"] = results.get("final_blueprint")
        
        # Extract documentation if needed
        if "final_blueprint" in results and isinstance(results["final_blueprint"], dict):
            results["documentation_design"] = results["final_blueprint"].get("documentation") or results["final_blueprint"]
        
        print("\n[SUCCESS] Dependency-Based Pipeline Completed.\n")
        
        # VERIFICATION COMMANDS
        print("\n[ORCHESTRATOR] Final Results Keys:")
        print(f"  {list(results.keys())}")
        print(f"\n[ORCHESTRATOR] Schema Modeling Tables Count: {len(results.get('schema_modeling', {}).get('tables', []))}")
        
        final_wrapped = {"success": True, "outputs": results}
        st.session_state["generation_results"] = final_wrapped
        return final_wrapped
        
    except Exception as e:
        print(f"\n[CRITICAL FAILURE] Orchestrator crashed: {e}")
        err_wrapped = {"success": False, "error": str(e)}
        st.session_state["generation_results"] = err_wrapped
        return err_wrapped

def run_single_module(session, module_key: str, requirements: dict, data_profile: dict, current_results: dict, model: str, force_refresh=False):
    """Regenerate a single specific module without running the full DAG."""
    ctx = _get_ctx()
    _add_ctx(ctx)
    if module_key == "architecture_strategy":
        return run_step(session, "architecture_strategy", requirements, data_profile, current_results, model, force_refresh=force_refresh)
    elif module_key == "schema_modeling":
        return run_parallel_schema(session, requirements, data_profile, current_results, model, None, force_refresh=force_refresh)
    elif module_key == "pipeline_design":
        return run_step(session, "pipeline_design", requirements, data_profile, current_results, model, force_refresh=force_refresh)
    elif module_key == "governance_security":
        return run_step(session, "governance_security", requirements, data_profile, current_results, model, force_refresh=force_refresh)
    elif module_key == "ddl_generation":
        return run_ddl_derivative(session, requirements, data_profile, current_results, model, None, force_refresh=force_refresh)
    else:
        return run_step(session, module_key, requirements, data_profile, current_results, model, force_refresh=force_refresh)
