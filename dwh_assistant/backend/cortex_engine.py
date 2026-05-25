import streamlit as st
import json
import datetime
import time
import re
import threading
from typing import Dict, Any, Optional, List
import hashlib
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Persistent AI Cache Directory
CORTEX_CACHE_DIR = Path(__file__).parent.parent / ".streamlit" / ".cortex_cache"
CORTEX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
# Robust Streamlit Context Propagation (Version-Agnostic)
try:
    from streamlit.runtime.scriptrunner import add_script_run_context, get_script_run_ctx
except ImportError:
    try:
        from streamlit.runtime.script_run_context import add_script_run_context, get_script_run_ctx
    except ImportError:
        try:
            from streamlit.runtime.scriptrunner_utils.script_run_context import add_script_run_ctx as add_script_run_context, get_script_run_ctx
        except ImportError:
            # Fallback for bare execution or unknown structures
            add_script_run_context = lambda thread, ctx: None
            get_script_run_ctx = lambda: None
from snowflake.snowpark import Session
from dwh_assistant.backend.snowflake import MODEL_REGISTRY, TWO_PARAM_ONLY_MODELS
from dwh_assistant.backend.validator import clean_mermaid_code

def clean_json_string(s: str) -> str:
    """
    Surgically repairs common JSON malformations from LLM outputs.
    """
    if not s: return s
    
    # 0. Strip markdown code fences (```json ... ```)
    s = re.sub(r'^```(?:json)?\s*', '', s.strip(), flags=re.IGNORECASE)
    s = re.sub(r'\s*```$', '', s)
    
    # 1. Remove all types of comments first (including inline and block)
    s = re.sub(r'//.*?\n|/\*.*?\*/', '', s, flags=re.DOTALL)
    s = re.sub(r'^\s*#.*$', '', s, flags=re.MULTILINE)
    
    # 2. Fix single quotes used as delimiters (common with Mixtral/Llama)
    # Only if not preceded by a letter (to avoid breaking possessives in text)
    # Improved: Use non-greedy match and avoid matching escaped quotes
    s = re.sub(r"(?<!\w)\'(\w+)\'\s*:", r'"\1":', s)
    # Only replace if the entire value is wrapped in single quotes and contains no internal unescaped single quotes
    s = re.sub(r":\s*\'([^'\\]*(?:\\.[^'\\]*)*)\'", r': "\1"', s)
    
    # 3. Improved comma injector: 
    # This looks for a closing marker (quote, number, ], }) 
    # followed by whitespace/newlines and then an opening quote
    s = re.sub(r'([\"|0-9|e|\]|\}])\s*\n\s*\"', r'\1,\n"', s)
    
    # BUG02 FIX: Replace the entire rstrip block with regex-based trailing comma removal
    # Step 1: Remove only a trailing comma that precedes the final closing structure
    s = re.sub(r',(\s*[}\]])$', r'\1', s.strip())
    # Step 2: Remove standalone trailing comma at very end (no structure after it)
    s = re.sub(r',\s*$', '', s)
    # Do NOT strip closing braces/brackets — let fix_truncated_json handle structure
    
    # 5. Fix illegal escapes (JSON only allows \", \\, \/, \b, \f, \n, \r, \t, \u)
    # Common AI mistake: \' (single quote) - replace with just '
    s = s.replace("\\'", "'")
    
    # 4. JSON Escape Sanitizer: Fix illegal single backslashes (common in AI SQL)
    # Improved: Match any backslash that isn't part of a valid JSON escape sequence
    # Valid escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
    # BUG 9: Expanded lookahead for SQL regex characters (\d, \w, \S, etc)
    s = re.sub(r'\\(?![\\\"\/bfnrtuwWdDsSpP\(\)\[\]\{\}\.\*\+\?\^\$\|])', r'\\\\', s)

    return s.strip()

def fix_truncated_json(s: str) -> str:
    """
    Attempts to close unclosed JSON structures (braces, brackets, quotes).
    """
    stack = []
    in_string = False
    escape = False
    fixed = ""
    
    for i, char in enumerate(s):
        if escape:
            fixed += char
            escape = False
            continue
        if char == '\\':
            fixed += char
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            fixed += char
            continue
        
        if not in_string:
            if char == '{': stack.append('}')
            elif char == '[': stack.append(']')
            elif char == '}':
                if stack and stack[-1] == '}': stack.pop()
            elif char == ']':
                if stack and stack[-1] == ']': stack.pop()
        
        fixed += char
    
    if in_string:
        fixed += '"'
    
    while stack:
        fixed += stack.pop()
        
    return fixed

def safe_json_parse(raw: Any, task_type: str = None) -> Dict[str, Any]:
    """
    Highly robust multi-strategy JSON extractor for Cortex responses.
    Handles nested wrappers, escaped SQL strings, and mid-stream truncation.
    """
    if not raw: return {}
    decoded = {}

    def extract_inner(raw_str: str) -> str:
        """Extract inner JSON string from Cortex wrapper using json.loads — no regex."""
        try:
            # Handle potential markdown wrapper before parsing outer
            s = raw_str.strip()
            s = re.sub(r'^```(?:json)?\s*', '', s, flags=re.IGNORECASE)
            s = re.sub(r'\s*```$', '', s)
            
            outer = json.loads(s, strict=False)
            if isinstance(outer, dict):
                if "choices" in outer and len(outer["choices"]) > 0:
                    choice = outer["choices"][0]
                    msg = choice.get("messages") or choice.get("message") or {}
                else:
                    msg = outer.get("messages") or outer.get("message") or outer
                
                if isinstance(msg, str): return msg
                if isinstance(msg, dict):
                    c = msg.get("content", "")
                    if isinstance(c, list):
                        return "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                    return c or ""
        except: pass
        return ""

    def unbox(obj):
        if isinstance(obj, list) and len(obj) > 0:
            return unbox(obj[0])
        if not isinstance(obj, dict): return obj
        
        # Check for standard Cortex/OpenAI wrappers
        if isinstance(obj, dict):
            # Check for 'choices' envelope
            if "choices" in obj and len(obj["choices"]) > 0:
                choice = obj["choices"][0]
                msg = choice.get("messages") or choice.get("message") or {}
                content = ""
                if isinstance(msg, str): content = msg
                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content = "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
                
                if content: 
                    # RECURSIVE UNWRAP: In case of multiple envelopes
                    inner_parsed = safe_json_parse(content, task_type)
                    if isinstance(inner_parsed, dict) and inner_parsed:
                        return inner_parsed
            
            # Check for direct 'message' or 'content' keys
            if "message" in obj and isinstance(obj["message"], dict):
                return unbox(obj["message"])
            if "content" in obj and isinstance(obj["content"], str):
                return safe_json_parse(obj["content"], task_type)
                
        return obj

    if isinstance(raw, dict): 
        unboxed = unbox(raw)
        if isinstance(unboxed, dict): return unboxed
        if isinstance(unboxed, str): raw = unboxed
    
    if isinstance(raw, list) and len(raw) > 0: 
        unboxed = unbox(raw[0])
        if isinstance(unboxed, dict): return unboxed
        if isinstance(unboxed, str): raw = unboxed
        
    if not isinstance(raw, str): return {}

    # 1. TASK-SPECIFIC SCRAPING (SQL)
    if task_type == "ddl_generation":
        sql_blocks = re.findall(r'```(?:sql)?\s*(.*?)\s*```', raw, re.DOTALL | re.IGNORECASE)
        # Filter out blocks that are clearly JSON
        sql_blocks = [b for b in sql_blocks if not b.strip().startswith("{")]
        if sql_blocks:
            return {
                "ddl_sql": sql_blocks[0].strip(),
                "grant_sql": sql_blocks[1].strip() if len(sql_blocks) > 1 else "",
                "transform_sql": sql_blocks[2].strip() if len(sql_blocks) > 2 else "-- No transforms required"
            }

    # STRATEGY 1: Full outer parse + unbox (handles complete responses)
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            decoded = json.loads(raw[start:end+1], strict=False)
            result = unbox(decoded)
            if result is not decoded: return result
            return result
    except Exception as e:
        print(f"[DEBUG] Strategy 1 failed: {e}")

    # STRATEGY 2: Extract inner string via json.loads (handles SQL escapes correctly)
    inner = extract_inner(raw)
    if inner:
        inner = re.sub(r'^```(?:json)?\s*', '', inner.strip(), flags=re.IGNORECASE)
        inner = re.sub(r'\s*```$', '', inner)
        
        brace_start = inner.find("{")
        if brace_start != -1:
            inner_json = inner[brace_start:]
            try:
                decoded = json.loads(inner_json, strict=False)
                return decoded
            except:
                try:
                    fixed = fix_truncated_json(inner_json)
                    return json.loads(fixed, strict=False)
                except Exception as fe:
                    print(f"[DEBUG] Strategy 2 repair failed: {fe}")

    # STRATEGY 3: Structural repair on raw (Last resort)
    start = raw.find("{")
    if start != -1:
        try:
            fixed = fix_truncated_json(raw[start:])
            decoded = json.loads(fixed, strict=False)
            return unbox(decoded)
        except: pass

    # ALIAS MAPPING for downstream stability
    if isinstance(decoded, dict):
        aliases = {
            "type": "architecture_type", "strategy": "architecture_strategy",
            "diagram": "mermaid_diagram", "mermaid": "mermaid_diagram",
            "pillars": "strategic_pillars", "design": "design_summary", "flow": "data_flow",
            "masking_type": "type", "masking": "masking_policies",
            "rbac": "roles", "privileges": "grants",
            "summary_text": "summary", "docs": "documentation"
        }
        
        # Deep Alias Injection
        def inject_aliases(obj):
            if not isinstance(obj, dict): return
            new_keys = {}
            for k, v in obj.items():
                if k in aliases and aliases[k] not in obj:
                    new_keys[aliases[k]] = v
                if isinstance(v, dict): inject_aliases(v)
                elif isinstance(v, list):
                    for item in v: 
                        if isinstance(item, dict): inject_aliases(item)
            obj.update(new_keys)

        inject_aliases(decoded)
        return decoded

    return {}

# These are now imported from snowflake_conn

def _is_truncated(text: str) -> bool:
    """Robust heuristic to check if JSON response was likely cut off."""
    t = text.strip()
    if not t: return False
    
    if t.endswith("```"):
        t = re.sub(r'\s*```$', '', t).strip()
        
    if t.endswith("}") or t.endswith("]"):
        return False
        
    # 1. Check for balanced structural markers
    open_braces = t.count('{')
    close_braces = t.count('}')
    open_brackets = t.count('[')
    close_brackets = t.count(']')
    
    if open_braces > close_braces or open_brackets > close_brackets:
        return True
        
    # 2. Check if it ends with a dangling delimiter
    if any(t.endswith(c) for c in [',', ':', '[', '{', '"']):
        return True
        
    # 3. Check for valid JSON literal completion
    # If it ends with letters, they must form a complete literal: true, false, null
    last_word = re.search(r'([a-z]+)$', t, re.IGNORECASE)
    if last_word:
        word = last_word.group(1).lower()
        if word not in ['true', 'false', 'null']:
            return True
            
    return False

def call_cortex(
    session: Session,
    prompt: str,
    task_type: str,
    model: str = "claude-3-7-sonnet",
    max_retries: int = 3,
    _is_fallback: bool = False
) -> Dict[str, Any]:
    """
    Snowflake Cortex caller with continuation logic and smart model routing.
    """
    clean_model = str(model).strip().lower()
    
    # 2. CACHE LOOKUP
    cache_key = hashlib.sha256(f"{clean_model}:{prompt}".encode()).hexdigest()
    cache_path = CORTEX_CACHE_DIR / f"{cache_key}.json"
    
    if cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
            return cached_data
        except: pass

    # No manual string escaping (session.sql handles it safely)
    safe_prompt = prompt
    
    # DYNAMIC TOKEN LIMITS
    if task_type in ["ddl_generation", "documentation_summary", "schema_design", "schema_details"] or str(task_type).startswith("details_"):
        token_limit = 8192 
    elif task_type in ["pipeline_design", "governance_security", "schema_relationships", "architecture_strategy", "architecture_diagram", "schema_inventory"]:
        token_limit = 6144
    else:
        token_limit = 4096
    
    token_limit = min(token_limit, 8192)
    raw_output = ""

    for attempt in range(max_retries):
        try:
            # Snowflake Cortex max_tokens cap is model-specific.
            # We use temperature 0.0 for structural precision in JSON outputs.
            MODEL_MAX_TOKENS = {
                "mistral": 8192,
                "llama": 8192,
                "gemma": 8192,
                "jamba": 8192,
                "claude": 128000
            }
            
            model_cap = 128000 # Default generous cap
            for m_key, cap in MODEL_MAX_TOKENS.items():
                if m_key in model.lower():
                    model_cap = cap
                    break
                    
            # Scale tokens per attempt, strictly bounded by the model's actual physical limit
            current_limit = min(token_limit + (attempt * 32768), model_cap)
            
            print(f"[EXEC] [{task_type.upper()}] model={model} attempt={attempt + 1} limit={current_limit}")

            # Use standard GA built-in SNOWFLAKE.CORTEX.COMPLETE signature
            use_2_param = model.lower() in TWO_PARAM_ONLY_MODELS
            if use_2_param:
                sql_complete = """
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    ?::VARCHAR,
                    ?::VARCHAR
                )
                """
                params = [model, safe_prompt]
            else:
                sql_complete = """
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    ?::VARCHAR,
                    ARRAY_CONSTRUCT(OBJECT_CONSTRUCT('role', 'user', 'content', ?::VARCHAR)),
                    OBJECT_CONSTRUCT('temperature', 0.0, 'max_tokens', ?::INT)
                )
                """
                params = [model, safe_prompt, current_limit]
            
            try:
                res = session.sql(sql_complete, params=params).collect()
                
                raw_chunk = res[0][0] if res and len(res) > 0 else None
                if not raw_chunk: raise Exception("Empty response")
                raw_output = raw_chunk
            except Exception as e:
                print(f"[ERROR] Attempt {attempt+1} failed: {e}")
                continue

            # ═══════════════════════════════════════════════
            # CONTINUATION LOGIC (Fix 5)
            # ═══════════════════════════════════════════════
            if _is_truncated(raw_output) and attempt < max_retries - 1:
                print(f"[TRUNCATED] Response for {task_type} is incomplete. Attempting continuation...")
                from dwh_assistant.backend.prompt_library import CONTINUATION_PROMPT
                # Request the rest of the JSON
                cont_prompt = f"{prompt}\n\n[PREVIOUS_RAW_OUTPUT]:\n{raw_output[-300:]}\n\n{CONTINUATION_PROMPT}"
                
                try:
                    cont_params = [model, cont_prompt] if use_2_param else [model, cont_prompt, current_limit]
                    res_cont = session.sql(sql_complete, params=cont_params).collect()
                    if res_cont and len(res_cont) > 0:
                        cont_chunk = res_cont[0][0]
                        if cont_chunk:
                            print(f"[HEALED] Merging continuation fragment for {task_type}")
                            raw_output += cont_chunk
                except Exception as ce:
                    print(f"[WARN] Continuation failed: {ce}")

            # ═══════════════════════════════════════════════
            # VALIDATION & PARSING
            # ═══════════════════════════════════════════════
            parsed = safe_json_parse(raw_output, task_type=task_type)

            if isinstance(parsed, dict):
                # Apply defaults
                if task_type == "ddl_generation":
                    parsed.setdefault("transform_sql", "-- No initial transforms required")
                    parsed.setdefault("grant_sql", "")
                elif task_type == "governance_security":
                    parsed.setdefault("auditing_strategy", "Standard Snowflake query history auditing")
                    parsed.setdefault("object_tags", [])

            if not _step_is_complete(task_type, parsed, is_last_attempt=(attempt == max_retries - 1)):
                if attempt == max_retries - 1:
                    # FINAL ATTEMPT: Force inject missing keys with safe defaults
                    required = STEP_REQUIRED_KEYS.get(task_type, [])
                    if isinstance(parsed, dict):
                        for k in required:
                            if k not in parsed:
                                print(f"[SAFETY] Injecting default for missing key: {k}")
                                parsed[k] = [] if "list" in str(STEP_SCHEMA_SPECS.get(task_type, {}).get(k, "")) else {}
                    else:
                        parsed = {k: [] for k in required}
                else:
                    missing = [k for k in STEP_REQUIRED_KEYS.get(task_type, []) if k not in (parsed if isinstance(parsed, dict) else {})]
                    raise Exception(f"Validation failed for {task_type}. Missing: {missing}")

            result = {
                "success": True,
                "output":  parsed,
                "raw":     raw_output,
                "model":   model,
                "attempt": attempt + 1
            }
            
            try:
                with open(cache_path, 'w') as f:
                    json.dump(result, f)
            except: pass
            
            return result

        except Exception as e:
            print(f"[FAIL] {task_type} attempt {attempt + 1}: {e}")
            if "rate limit" in str(e).lower():
                time.sleep(10)
            continue

    return {"success": False, "error": f"Failed after {max_retries} attempts"}

# Tiered validation: Critical keys MUST be present. Optional keys can be 
# filled with placeholders if truncation occurs on the last attempt.
# STRICT SCHEMA DEFINITION: All keys are mandatory to ensure UI stability.
STEP_REQUIRED_KEYS = {
    "architecture_strategy": ["architecture_type", "modeling_paradigm", "layers"],
    "architecture_diagram":  ["mermaid_diagram"],
    "schema_inventory":     ["table_names"],
    "schema_atomic":        ["t_name", "cols"],
    "schema_design":        ["tables", "relationships"],
    "pipeline_design":      ["tasks"],
    "gov_rbac":             ["roles"],
    "gov_policies":         ["masking_policies"],
    "gov_compliance":       ["compliance_checklist"],
    "ddl_generation":       ["ddl"],
    "art_dbt":              ["sql"],
    "art_orch":             ["snowflake_task_dag"],
    "art_ui":               ["streamlit_app_skeleton"],
    "documentation_summary":["summary"],
    "history":              ["version", "generated_at"]
}

# Optional keys are now mostly migrated to Required for strictness.
STEP_OPTIONAL_KEYS = {
    "architecture_strategy": ["complexity", "estimated_cost_tier", "reasoning"],
    "documentation_design": ["data_dictionary", "mermaid_diagram"]
}

# Detailed Type-Safe Schema Definitions
STEP_SCHEMA_SPECS = {
    "architecture_strategy": {
        "architecture_type": str, "modeling_paradigm": str, "layers": list
    },
    "schema_atomic": {
        "t_name": str, "cols": list
    },
    "schema_design": {
        "tables": list, "relationships": list
    },
    "pipeline_design": {
        "tasks": list
    },
    "gov_rbac": {
        "roles": list
    },
    "gov_policies": {
        "masking_policies": list
    },
    "ddl_generation": {
        "ddl": str
    },
    "art_dbt": {
        "sql": str
    }
}

def _step_is_complete(step_name: str, data: Any, is_last_attempt: bool = False) -> bool:
    """
    Perform multi-level strict validation:
    1. Key presence
    2. Data types
    3. Value non-emptiness (for critical fields)
    """
    if not isinstance(data, dict): 
        print(f"[FAIL] {step_name}: Response is not a dictionary.")
        return False

    required = STEP_REQUIRED_KEYS.get(step_name, [])
    missing = [k for k in required if k not in data]
    
    if missing:
        print(f"[INCOMPLETE] {step_name} missing keys: {missing}")
        return False
    
    # 2. TYPE ENFORCEMENT
    specs = STEP_SCHEMA_SPECS.get(step_name, {})
    for key, expected_type in specs.items():
        if key in data and not isinstance(data[key], expected_type):
            print(f"[TYPE-FAIL] {step_name}.{key}: Expected {expected_type}, got {type(data[key])}")
            return False

    # 3. QUALITY CHECK (NON-EMPTY)
    if "mermaid_diagram" in data:
        val = str(data["mermaid_diagram"]).strip()
        if not val or len(val) < 20: # Sanity check for diagram length
            print(f"[QUALITY-FAIL] {step_name}: mermaid_diagram is suspiciously short or empty")
            return False
            
    if "tables" in data:
        if not isinstance(data["tables"], list) or len(data["tables"]) == 0:
            if step_name in ["schema_details", "schema_design"]:
                print(f"[QUALITY-FAIL] {step_name}: tables list is empty")
                return False
                
    return True


def run_all(session: Session, requirements: Dict[str, Any], data_profile: Dict[str, Any], model: str = "claude-3-7-sonnet", status_callback=None, initial_results: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Highly Optimized AI generation runner.
    Supports stateful resuming and sequential execution.
    """
    from dwh_assistant.backend.prompt_library import build_prompt
    
    results = initial_results if initial_results else {}
    effective_models = set()
    
    def run_step(step_name, current_results, preferred_model=None, retry_count=0, last_error=None):
        target_model = preferred_model if preferred_model else model
        
        cached = current_results.get(step_name)
        if _step_is_complete(step_name, cached):
            print(f"[SKIP] {step_name} — already complete")
            if status_callback: status_callback(step_name, "done", cached)
            return cached

        if status_callback: status_callback(step_name, "running")
        
        prompt = build_prompt(step_name, requirements, data_profile, current_results)
        
        # CORRECTIVE RETRY: If we have a previous error, tell the model exactly what to fix
        if last_error:
            prompt += f"\n\n[CRITICAL ERROR]: Your previous attempt failed validation: {last_error}. FIX THIS IMMEDIATELY. Output ONLY valid JSON with all required keys."

        response = call_cortex(session, prompt, step_name, model=target_model)
        
        if response["success"]:
            output = response["output"]
            used_model = str(response.get("model", target_model))
            effective_models.add(used_model)
            st.session_state[f"{step_name}_raw"] = response.get("raw", "")

            if status_callback: status_callback(step_name, "done", output)
            return output
        else:
            # TARGETED MODEL SWAP
            if target_model != "llama3.1-405b":
                print(f"[FALLBACK] {target_model} failed, retrying {step_name} with llama3.1-405b")
                return run_step(step_name, current_results, preferred_model="llama3.1-405b", 
                                retry_count=retry_count+1, last_error=response.get("error"))
            
            if status_callback: status_callback(step_name, "error", response)
            raise Exception(f"Step {step_name} failed after adaptive fallbacks: {response.get('error')}")

            chunk_size = 10 # Increased from 3 to reduce sequential calls
            chunks = [table_names[i:i + chunk_size] for i in range(0, len(table_names), chunk_size)]
            
            ctx = get_script_run_ctx()
            raw_store = {}
            # Fix 5: Sequential processing (max_workers=1) to prevent race conditions and Cortex throttling
            with ThreadPoolExecutor(max_workers=1) as executor:
                futures = {executor.submit(process_chunk, layer, chunk, i, ctx): f"details_{layer}_{i}"
                           for i, chunk in enumerate(chunks)}
                for future in as_completed(futures):
                    key = futures[future]
                    tables_result, raw = future.result()
                    raw_store[key] = raw
                    all_tables.extend(tables_result)

            for k, v in raw_store.items():
                st.session_state[f"{k}_raw"] = v

        table_summary = [
            {
                "name": t.get("name"), "layer": t.get("layer"),
                "columns": [{"name": c.get("name"), "is_pk": c.get("is_pk"), "is_fk": c.get("is_fk")}
                            for c in t.get("columns", []) if c.get("is_pk") or c.get("is_fk")]
            } for t in all_tables
        ]
        
        rel_prompt = build_prompt("schema_relationships", requirements, data_profile, {"all_tables": table_summary})
        rel_res = call_cortex(session, rel_prompt, "schema_relationships", model=target_model)
        
        res = {
            "tables": all_tables,
            "relationships": rel_res["output"].get("relationships", []) if rel_res["success"] else [],
            "mermaid_diagram": rel_res["output"].get("mermaid_diagram", "") if rel_res["success"] else "graph TD\n  Fail[Diagram Failed]"
        }
        
        if status_callback:
            status_callback("schema_design", "done", res)
        return res

    def run_step_schema_atomic(current_results: Dict[str, Any], model: str = None) -> Dict[str, Any]:
        """Generates schema table-by-table in parallel for maximum precision and zero truncation."""
        inventory = current_results.get("schema_inventory", {}).get("table_names", [])
        layers = current_results.get("architecture_selection", {}).get("layers", ["Bronze", "Silver", "Gold"])
        
        all_designed_tables = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            for layer in layers:
                layer_tables = [t for t in inventory if t.lower().startswith(layer[:3].lower()) or layer in t]
                if not layer_tables and layer == "Gold":
                    layer_tables = [t for t in inventory if t.lower().startswith(("fct_", "dim_", "fact_"))]
                
                for table_name in layer_tables:
                    ctx = current_results.copy()
                    ctx["target_layer"] = layer
                    ctx["target_table"] = table_name
                    ctx["context_tables"] = [t for t in inventory if t != table_name]
                    
                    fut = executor.submit(context_wrapper, run_step, "schema_atomic", ctx, preferred_model=model)
                    futures[fut] = (table_name, layer)
            
            for fut in as_completed(futures):
                t_name, l_name = futures[fut]
                try:
                    res = fut.result()
                    if res and isinstance(res, dict):
                        # NORMALIZE COMPRESSED KEYS
                        cols = []
                        for c in res.get("cols", []):
                            cols.append({
                                "name": c.get("n", "unknown"),
                                "type": c.get("t", "VARCHAR"),
                                "is_pk": c.get("pk", False),
                                "is_fk": c.get("fk", False),
                                "references": c.get("ref"),
                                "description": c.get("desc", ""),
                                "pii": c.get("pii", False)
                            })

                        all_designed_tables.append({
                            "name": t_name,
                            "layer": l_name,
                            "type": res.get("t_type"),
                            "columns": cols
                        })
                except Exception as e:
                    print(f"[FAIL] Atomic schema for {t_name} failed: {e}")
        
        # Finally, generate relationships in one small call
        rel_ctx = current_results.copy()
        rel_ctx["schema_design"] = {"tables": all_designed_tables}
        rel_res = run_step("schema_design", rel_ctx, preferred_model=model)
        
        return {
            "tables": all_designed_tables,
            "relationships": rel_res.get("relationships", []) if rel_res else [],
            "mermaid_diagram": rel_res.get("mermaid_diagram", "") if rel_res else ""
        }

    def run_step_pipeline_batched(current_results: Dict[str, Any], model: str = None) -> Dict[str, Any]:
        layers = current_results.get("architecture_selection", {}).get("layers", ["Bronze", "Silver", "Gold"])
        schema_results = current_results.get("schema_design", {})
        all_tables_metadata = schema_results.get("tables", [])
        
        all_tasks = []
        full_mermaid = ["graph TD"]
        
        for layer in layers:
            layer_tables = [t.get("name") for t in all_tables_metadata if t.get("layer") == layer]
            if not layer_tables: continue
            
            # Intra-layer chunking to prevent 8k token truncation
            chunk_size = 6
            chunks = [layer_tables[i:i + chunk_size] for i in range(0, len(layer_tables), chunk_size)]
            
            for i, chunk in enumerate(chunks):
                ctx = current_results.copy()
                ctx["target_layer"] = layer
                ctx["target_tables"] = chunk # Narrow the AI's focus
                
                res = run_step("pipeline_design", ctx, preferred_model=model)
                if res and isinstance(res, dict):
                    # NORMALIZE COMPRESSED KEYS
                    tasks = []
                    for t in res.get("tasks", []):
                        tasks.append({
                            "name": t.get("n", "unknown"),
                            "source": t.get("src", ""),
                            "target": t.get("tgt", ""),
                            "logic": t.get("logic", "")
                        })
                    all_tasks.extend(tasks)
                    diag = res.get("mermaid_diagram", "")
                    if diag and isinstance(diag, str):
                        full_mermaid.append(diag.replace("graph TD", "").replace("graph LR", "").strip())
        
        return {
            "tasks": all_tasks,
            "mermaid_diagram": "\n  ".join(full_mermaid)
        }

    def run_step_ddl_batched(current_results: Dict[str, Any], model: str = None) -> Dict[str, Any]:
        """Generates DDL in parallel for each table to maximize speed while maintaining atomic reliability."""
        schema_results = current_results.get("schema_design", {})
        all_tables = schema_results.get("tables", [])
        
        results_map = {}
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            for table in all_tables:
                ctx = current_results.copy()
                ctx["target_layer"] = table.get("layer", "UNKNOWN")
                ctx["target_table"] = table["name"]
                ctx["target_table_schema"] = table
                
                fut = executor.submit(context_wrapper, run_step, "ddl_generation", ctx, preferred_model=model)
                futures[fut] = table["name"]
            
            for fut in as_completed(futures):
                t_name = futures[fut]
                try:
                    res = fut.result()
                    if res and isinstance(res, dict) and res.get("ddl"):
                        results_map[t_name] = res["ddl"]
                except Exception as e:
                    print(f"[FAIL-SOFT] DDL for {t_name} failed: {e}")

        # Maintain order based on schema design
        ddl_parts = [f"-- {t['name']}\n{results_map[t['name']]}" for t in all_tables if t['name'] in results_map]
        
        return {
            "table_name": "Unified Schema",
            "ddl": "\n\n".join(ddl_parts),
            "ddl_sql": "\n\n".join(ddl_parts)
        }

    def run_step_gov_batched(current_results: Dict[str, Any], model: str = None) -> Dict[str, Any]:
        """Segments Governance into 3 parallel sub-tasks to prevent truncation."""
        with ThreadPoolExecutor(max_workers=3) as executor:
            fut_rbac = executor.submit(context_wrapper, run_step, "gov_rbac", current_results, preferred_model=model)
            fut_pols = executor.submit(context_wrapper, run_step, "gov_policies", current_results, preferred_model=model)
            fut_comp = executor.submit(context_wrapper, run_step, "gov_compliance", current_results, preferred_model=model)
            
            res_rbac = fut_rbac.result()
            res_pols = fut_pols.result()
            res_comp = fut_comp.result()
            
        return {
            **res_rbac, **res_pols, **res_comp
        }

    def run_step_art_batched(current_results: Dict[str, Any], model: str = None) -> Dict[str, Any]:
        """Segments Artifacts into truly parallel sub-tasks."""
        schema_results = current_results.get("schema_design", {})
        all_tables = schema_results.get("tables", [])
        dbt_parts = []
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Dispatch dbt models
            dbt_futs = {}
            for table in all_tables[:20]:
                ctx = current_results.copy()
                ctx["target_table_schema"] = table
                fut = executor.submit(context_wrapper, run_step, "art_dbt", ctx, preferred_model=model)
                dbt_futs[fut] = table["name"]
            
            # Dispatch others
            fut_orch = executor.submit(context_wrapper, run_step, "art_orch", current_results, preferred_model=model)
            fut_ui = executor.submit(context_wrapper, run_step, "art_ui", current_results, preferred_model=model)
            
            # Collect dbt results
            for fut in as_completed(dbt_futs):
                t_name = dbt_futs[fut]
                try:
                    res_dbt = fut.result()
                    if res_dbt and res_dbt.get("sql"):
                        dbt_parts.append(f"-- {t_name}\n{res_dbt['sql']}")
                except Exception as e:
                    print(f"[FAIL] dbt model for {t_name}: {e}")
            
            res_orch = fut_orch.result()
            res_ui = fut_ui.result()
            
        return {
            "dbt_models": dbt_parts,
            "dbt_schema_yaml": "version: 2\nmodels: []",
            **res_orch, **res_ui
        }

    def run_step_doc_batched(current_results: Dict[str, Any], model: str = None) -> Dict[str, Any]:
        layers = current_results.get("architecture_selection", {}).get("layers", ["Bronze", "Silver", "Gold"])
        all_docs = []
        all_dict = []
        
        for layer in layers:
            ctx = current_results.copy()
            ctx["target_layer"] = layer
            
            # Batch Documentation
            doc_res = run_step("documentation_summary", ctx, preferred_model=model)
            if doc_res and isinstance(doc_res, dict):
                doc_text = doc_res.get("documentation", "")
                if doc_text: all_docs.append(f"### {layer} Layer Documentation\n{doc_text}")
            
            # Batch Data Dictionary
            dict_res = run_step("data_dictionary", ctx, preferred_model=model)
            if dict_res and isinstance(dict_res, dict):
                dict_data = dict_res.get("data_dictionary", [])
                if isinstance(dict_data, list): all_dict.extend(dict_data)

        return {
            "documentation": "\n\n".join(all_docs),
            "data_dictionary": all_dict,
            "design_summary": "Unified Architectural Design for all layers."
        }

    try:
        # Optimization: Inject Streamlit ScriptRunContext into background threads to allow UI updates
        ctx = get_script_run_ctx()
        def context_wrapper(func, *args, **kwargs):
            if ctx: add_script_run_context(threading.current_thread(), ctx)
            return func(*args, **kwargs)

        # ═══════════════════════════════════════════════
        # PHASE 1: STRATEGIC BLUEPRINT
        # ═══════════════════════════════════════════════
        print("[PHASE 1] Initializing Strategic Blueprint...")
        with ThreadPoolExecutor(max_workers=2) as executor:
            fut_strat = executor.submit(context_wrapper, run_step, "architecture_strategy", results, preferred_model=model)
            fut_diag = executor.submit(context_wrapper, run_step, "architecture_diagram", results, preferred_model=model)
            
            results["architecture_strategy"] = fut_strat.result()
            results["architecture_diagram"] = fut_diag.result()
            results["architecture_selection"] = {**results["architecture_strategy"], **results["architecture_diagram"]}

        # ═══════════════════════════════════════════════
        # PHASE 2: LOGICAL MODELING & GOVERNANCE
        # ═══════════════════════════════════════════════
        print("[PHASE 2] Executing Logical Modeling & Governance...")
        # 1. Schema first (Dependency for others)
        results["schema_design"] = run_step_schema_atomic(results, model)
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            fut_pipe = executor.submit(context_wrapper, run_step_pipeline_batched, results, model)
            fut_gov = executor.submit(context_wrapper, run_step_gov_batched, results, model)
            
            # AI Intelligence Layers
            fut_search = executor.submit(context_wrapper, run_step, "cortex_search_design", results, preferred_model=model)
            fut_analyst = executor.submit(context_wrapper, run_step, "cortex_analyst_design", results, preferred_model=model)
            
            results["pipeline_design"] = fut_pipe.result()
            results["governance_security"] = fut_gov.result()
            results["cortex_search_design"] = fut_search.result()
            results["cortex_analyst_design"] = fut_analyst.result()
            
            results["cortex_ai_design"] = {
                **(results.get("cortex_search_design") or {}),
                **(results.get("cortex_analyst_design") or {})
            }
            effective_models.add(model)

        # ═══════════════════════════════════════════════
        # PHASE 3: PHYSICAL IMPLEMENTATION & ARTIFACTS
        # ═══════════════════════════════════════════════
        print("[PHASE 3] Generating Physical Artifacts & Documentation...")
        with ThreadPoolExecutor(max_workers=3) as executor:
            # DDL and Documentation already use entity-level chunking internally
            fut_ddl = executor.submit(context_wrapper, run_step_ddl_batched, results, model=model)
            fut_arts = executor.submit(context_wrapper, run_step_art_batched, results, model=model)
            fut_docs = executor.submit(context_wrapper, run_step_doc_batched, results, model=model)
            
            results["ddl_generation"] = fut_ddl.result()
            results["artifacts_generation"] = fut_arts.result()
            results["documentation_design"] = fut_docs.result()

        # ═══════════════════════════════════════════════
        # FINAL MAPPING & CONTRACTS
        # ═══════════════════════════════════════════════
        results["architecture"] = results.get("architecture_selection", {})
        results["schema"] = results.get("schema_design", {})
        results["pipeline"] = results.get("pipeline_design", {})
        results["governance"] = results.get("governance_security", {})
        results["history"] = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Success",
            "models_involved": list(effective_models),
            "project_name": requirements.get("project_name", "Untitled DWH")
        }
        results["artifacts"] = {
            "ddl_sql": results.get("ddl_generation", {}).get("ddl_sql", ""),
            "transform_sql": results.get("ddl_generation", {}).get("transform_sql", "-- N/A"),
            "grant_sql": results.get("ddl_generation", {}).get("grant_sql", ""),
            "dbt_models": results.get("artifacts_generation", {}).get("dbt_models", []),
            "dbt_schema": results.get("artifacts_generation", {}).get("dbt_schema_yaml", ""),
            "data_contracts": results.get("artifacts_generation", {}).get("data_contracts", []),
            "cortex_ai": results.get("cortex_ai_design", {}),
            "documentation": results.get("documentation_design", {})
        }

        return {
            "success": True, 
            "outputs": results,
            "effective_models": list(effective_models)
        }

    except Exception as e:
        import traceback
        print(f"[ERROR] run_all failed: {e}")
        traceback.print_exc()
        
        # FINAL SAFETY: Merge any successfully generated partials into session state
        if results:
            for k, v in results.items():
                if v and isinstance(v, dict):
                    # Only merge non-error results
                    if not v.get("error"):
                        st.session_state[k] = v
                        
        return {"success": False, "error": str(e), "partial_outputs": results}
