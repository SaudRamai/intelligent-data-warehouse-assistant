"""
High-performance execution engine supporting automatic stream continuation and robust multi-round envelope parsing.
"""
import streamlit as st
import json
import time
import re
import pandas as pd
from typing import Dict, Any, List, Optional
from snowflake.snowpark import Session
from dwh_assistant.backend.validator import clean_json_string, fix_truncated_json
from dwh_assistant.backend.snowflake import log_deployment, TWO_PARAM_ONLY_MODELS
from concurrent.futures import ThreadPoolExecutor, as_completed

def unescape_json_string(s: str) -> str:
    """Decodes a JSON string literal character-by-character, resilient to truncation."""
    res = []
    i = 0
    n = len(s)
    while i < n:
        char = s[i]
        if char == '\\':
            if i + 1 < n:
                next_char = s[i+1]
                if next_char == '"':
                    res.append('"')
                    i += 2
                elif next_char == '\\':
                    res.append('\\')
                    i += 2
                elif next_char == '/':
                    res.append('/')
                    i += 2
                elif next_char == 'b':
                    res.append('\b')
                    i += 2
                elif next_char == 'f':
                    res.append('\f')
                    i += 2
                elif next_char == 'n':
                    res.append('\n')
                    i += 2
                elif next_char == 'r':
                    res.append('\r')
                    i += 2
                elif next_char == 't':
                    res.append('\t')
                    i += 2
                elif next_char == 'u':
                    if i + 5 < n:
                        hex_val = s[i+2:i+6]
                        try:
                            res.append(chr(int(hex_val, 16)))
                            i += 6
                        except ValueError:
                            res.append('\\')
                            res.append('u')
                            i += 2
                    else:
                        res.append('\\')
                        res.append('u')
                        i += 2
                else:
                    res.append('\\')
                    res.append(next_char)
                    i += 2
            else:
                res.append('\\')
                i += 1
        else:
            res.append(char)
            i += 1
    return "".join(res)


def extract_json(raw_text: Any, task_type: str = None) -> Dict[str, Any]:
    """Robustly extracts, unboxes, and repairs JSON from LLM responses."""
    if not raw_text: return {}
    if isinstance(raw_input := raw_text, (dict, list)): return raw_input
    if not isinstance(raw_text, str): raw_text = str(raw_text)

    import re, json, ast

    # 1. Strip Claude thinking blocks
    text = re.sub(r'<thinking>.*?</thinking>', '', raw_text, flags=re.DOTALL).strip()

    # Helper to peel off JSON envelopes recursively
    def unwrap_envelope(obj):
        while isinstance(obj, dict):
            if "choices" in obj and isinstance(obj["choices"], list) and len(obj["choices"]) > 0:
                choice = obj["choices"][0]
                if isinstance(choice, dict):
                    msg = choice.get("message", {}) or choice.get("messages", {})
                    if isinstance(msg, str):
                        obj = msg
                        continue
                    content = msg.get("content") if isinstance(msg, dict) else None
                    if content is not None:
                        obj = content
                        continue
            if "message" in obj and isinstance(obj["message"], dict) and "content" in obj["message"]:
                obj = obj["message"]["content"]
                continue
            if "content" in obj and isinstance(obj["content"], (dict, list, str)):
                obj = obj["content"]
                continue
            # If it's a dict with a single key mapping to an embedded JSON string, unbox it
            if len(obj) == 1:
                val = list(obj.values())[0]
                if isinstance(val, str) and (val.strip().startswith('{') or val.strip().startswith('[')):
                    try:
                        obj = json.loads(val.strip())
                        continue
                    except Exception:
                        pass
            break
        return obj

    # Helper to strip markdown fences
    def clean_fences(s: str) -> str:
        s = s.strip()
        if "```json" in s:
            s = re.sub(r'```json\s*(.*?)\s*```', r'\1', s, flags=re.DOTALL | re.IGNORECASE)
        elif "```" in s:
            s = re.sub(r'```\s*(.*?)\s*```', r'\1', s, flags=re.DOTALL | re.IGNORECASE)
        return s.strip()

    # 2. Task-specific SQL Scraping (MANDATORY for DDL)
    if task_type == "ddl_generation":
        sql_blocks = re.findall(r'```(?:sql)?\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
        if sql_blocks:
            return {
                "ddl_sql": sql_blocks[0].strip(),
                "grant_sql": sql_blocks[1].strip() if len(sql_blocks) > 1 else "",
                "transform_sql": sql_blocks[2].strip() if len(sql_blocks) > 2 else "-- No transforms required"
            }
        if '"ddl_sql"' in text or '"grant_sql"' in text:
            try:
                ddl_match = re.search(r'"ddl_sql":\s*"(.*?)"', text, re.DOTALL)
                if ddl_match:
                    return {
                        "ddl_sql": ddl_match.group(1).replace('\\n', '\n').replace('\\"', '"'),
                        "grant_sql": "-- Extracted via Regex",
                        "transform_sql": "-- Extracted via Regex"
                    }
            except Exception: pass
        clean_start = text.strip().upper()
        if any(clean_start.startswith(k) for k in ["CREATE", "INSERT", "--", "WITH"]):
            return {"ddl_sql": text.strip()}

    # 1a. Surgical unboxing of double-encoded stringified JSON payloads from Snowflake AI_COMPLETE
    clean_start = text.strip()
    is_envelope = clean_start.startswith('{') and (('"choices"' in clean_start[:150]) or ('"messages"' in clean_start[:150]))
    
    if is_envelope:
        payload_str = None
        for key in ['"messages": "', '"content": "', '"messages":  "', '"content":  "']:
            idx = text.find(key)
            if idx != -1 and idx < 400:
                payload_str = text[idx + len(key):]
                break
        
        if payload_str:
            import re
            # Repair stray backslashes escaping closing quotes followed by structural keys
            keys_to_repair = [
                "tables", "mermaid_diagram", "design_rationale", "rel", "tasks", "roles", "mask", 
                "compliance_checklist", "lin", "tags", "architecture_type", "modeling_paradigm", 
                "layers", "architecture_justification", "data_model_blueprint", "data_flow", 
                "ddl_sql", "grant_sql", "transform_sql", "assumptions", "version", "generated_at", 
                "summary", "documentation", "pipeline_rationale", "governance_rationale"
            ]
            for key in keys_to_repair:
                pattern = r'\\{2,}"\s*,\s*(?:\\n|\\r|\s)*\\+"' + key + r'\\+"'
                def repl(match):
                    matched_str = match.group(0)
                    quote_idx = matched_str.find('"')
                    return '\\' + matched_str[quote_idx:]
                payload_str = re.sub(pattern, repl, payload_str)
                
            unescaped = unescape_json_string(payload_str)
            from dwh_assistant.backend.validator import clean_json_string, fix_truncated_json
            try:
                cleaned = clean_json_string(unescaped)
                repaired = fix_truncated_json(cleaned)
                parsed = json.loads(repaired)
                if isinstance(parsed, (dict, list)):
                    return parsed
            except Exception:
                pass

    if isinstance(text, str) and '\\"' in text and not is_envelope:
        try:
            stripped = text.strip()
            if stripped.startswith('"') and stripped.endswith('"'):
                unquoted = json.loads(stripped)
                if isinstance(unquoted, (dict, list)): return unquoted
                if isinstance(unquoted, str): text = unquoted
        except Exception: pass
        
        if '\\"' in text or '\\n' in text:
            import re
            repair_text = text
            keys_to_repair = [
                "tables", "mermaid_diagram", "design_rationale", "rel", "tasks", "roles", "mask", 
                "compliance_checklist", "lin", "tags", "architecture_type", "modeling_paradigm", 
                "layers", "architecture_justification", "data_model_blueprint", "data_flow", 
                "ddl_sql", "grant_sql", "transform_sql", "assumptions", "version", "generated_at", 
                "summary", "documentation", "pipeline_rationale", "governance_rationale"
            ]
            for key in keys_to_repair:
                pattern = r'\\{2,}"\s*,\s*(?:\\n|\\r|\s)*\\+"' + key + r'\\+"'
                def repl(match):
                    matched_str = match.group(0)
                    quote_idx = matched_str.find('"')
                    return '\\' + matched_str[quote_idx:]
                repair_text = re.sub(pattern, repl, repair_text)
                
            unescaped = unescape_json_string(repair_text)
            from dwh_assistant.backend.validator import clean_json_string, fix_truncated_json
            try:
                cleaned = clean_json_string(unescaped)
                parsed = json.loads(cleaned)
                unwrapped = unwrap_envelope(parsed)
                if isinstance(unwrapped, (dict, list)): return unwrapped
            except Exception: pass
            
            try:
                repaired = fix_truncated_json(clean_json_string(unescaped))
                parsed = json.loads(repaired)
                unwrapped = unwrap_envelope(parsed)
                if isinstance(unwrapped, (dict, list)): return unwrapped
            except Exception: pass

    # Let's try standard multi-pass unboxing loop
    current = clean_fences(text)
    
    while isinstance(current, str):
        c_str = clean_fences(current)
        try:
            parsed = json.loads(c_str)
            unwrapped = unwrap_envelope(parsed)
            if isinstance(unwrapped, (dict, list)):
                return unwrapped
            current = unwrapped
            continue
        except Exception:
            pass
            
        # Try finding substring from first { or [
        start_b = c_str.find('{')
        start_k = c_str.find('[')
        idx = -1
        if start_b != -1 and (start_k == -1 or start_b < start_k): idx = start_b
        elif start_k != -1: idx = start_k
        
        if idx != -1:
            end_b = c_str.rfind('}')
            end_k = c_str.rfind(']')
            end_idx = max(end_b, end_k)
            cand = c_str[idx:end_idx+1] if (end_idx != -1 and end_idx > idx) else c_str[idx:]
            try:
                parsed = json.loads(cand)
                unwrapped = unwrap_envelope(parsed)
                if isinstance(unwrapped, (dict, list)): return unwrapped
            except Exception:
                pass
                
            # Try unicode_escape decoding if double backslashes exist
            if '\\' in cand:
                try:
                    decoded = cand.encode('utf-8').decode('unicode_escape')
                    parsed = json.loads(decoded)
                    unwrapped = unwrap_envelope(parsed)
                    if isinstance(unwrapped, (dict, list)): return unwrapped
                except Exception:
                    pass

            # Strip problem internal quotes inside Mermaid diagram nodes to prevent fatal decode crashes
            cleaned_nodes = re.sub(r'\[\\*["\'](.*?)\\*["\']\]', r'[\1]', cand)
            cleaned_nodes = re.sub(r'\(\\*["\'](.*?)\\*["\']\)', r'(\1)', cleaned_nodes)

            # Highly robust workflow: unescape double encoded stringified JSON, then use clean_json_string
            # This guarantees that multiline Mermaid strings with embedded newlines are perfectly escaped
            from dwh_assistant.backend.validator import clean_json_string, fix_truncated_json
            
            cur_cand = cleaned_nodes
            for _ in range(4):
                try:
                    parsed = json.loads(cur_cand)
                    unwrapped = unwrap_envelope(parsed)
                    if isinstance(unwrapped, (dict, list)): return unwrapped
                except Exception:
                    pass
                    
                # Apply clean_json_string directly to the cur_cand variant
                try:
                    cleaned_str = clean_json_string(cur_cand)
                    parsed = json.loads(cleaned_str)
                    unwrapped = unwrap_envelope(parsed)
                    if isinstance(unwrapped, (dict, list)): return unwrapped
                except Exception:
                    pass
                    
                # Apply fix_truncated_json
                try:
                    repaired_str = fix_truncated_json(clean_json_string(cur_cand))
                    parsed = json.loads(repaired_str)
                    unwrapped = unwrap_envelope(parsed)
                    if isinstance(unwrapped, (dict, list)): return unwrapped
                except Exception:
                    pass
                    
                # Safe eval fallback
                try:
                    res_dict = ast.literal_eval(cur_cand)
                    unwrapped = unwrap_envelope(res_dict)
                    if isinstance(unwrapped, (dict, list)): return unwrapped
                except Exception:
                    pass
                    
                if '\\' in cur_cand:
                    # Replace sequences like \\" -> " and \\n -> \n to unwrap one layer of escaping
                    cur_cand = cur_cand.replace('\\\\"', '\\"').replace('\\"', '"').replace('\\n', '\n')
                else:
                    break

        break

    # Final absolute fallback: let's try clean_json_string on the full clean_fences text
    from dwh_assistant.backend.validator import clean_json_string, fix_truncated_json
    clean_full = clean_json_string(clean_fences(text))
    try:
        parsed = json.loads(clean_full)
        unwrapped = unwrap_envelope(parsed)
        if isinstance(unwrapped, (dict, list)): return unwrapped
    except Exception as e1:
        try:
            repaired = fix_truncated_json(clean_full)
            parsed = json.loads(repaired)
            unwrapped = unwrap_envelope(parsed)
            if isinstance(unwrapped, (dict, list)): return unwrapped
        except Exception as e2:
            if '\\"' in clean_full or '\\n' in clean_full:
                ufull = clean_full.replace('\\\\"', '\\"').replace('\\"', '"').replace('\\n', '\n')
                try:
                    rfull = fix_truncated_json(clean_json_string(ufull))
                    pfull = json.loads(rfull)
                    unwrapped = unwrap_envelope(pfull)
                    if isinstance(unwrapped, (dict, list)): return unwrapped
                except Exception: pass
            print(f"      [JSON DECODE ERROR] Pass 1: {e1} | Pass 2: {e2}\n      [CLEAN_RAW SNIPPET]: {repr(clean_full[:150])}")
            
    return {"raw_unparsed": raw_text}


def synthesize_mermaid_from_ast(diagram_ast: dict, task_type: str = "flowchart") -> str:
    """Synthesizes valid Mermaid syntax from structured AST nodes and edges natively."""
    if not isinstance(diagram_ast, dict): return str(diagram_ast)
    
    dtype = diagram_ast.get("type", task_type).lower()
    nodes = diagram_ast.get("nodes", [])
    edges = diagram_ast.get("edges", [])
    
    if "er" in dtype or task_type in ["relationship_design", "schema_modeling"]:
        lines = ["erDiagram"]
        for node in nodes:
            name = str(node.get("name", node.get("id", "Entity"))).replace(" ", "_")
            lines.append(f"  {name} {{}}")
        for edge in edges:
            src = str(edge.get("from", edge.get("source", "A"))).replace(" ", "_")
            tgt = str(edge.get("to", edge.get("target", "B"))).replace(" ", "_")
            rel = edge.get("relationship", edge.get("label", "||--o{"))
            lines.append(f"  {src} {rel} {tgt} : joins")
        if len(lines) == 1: lines.append("  Entity ||--o{ Child : joins")
        return "\n".join(lines)
    else:
        lines = ["flowchart LR"]
        for node in nodes:
            nid = str(node.get("id", node.get("name", "N"))).replace(" ", "_")
            lbl = str(node.get("label", node.get("name", nid))).replace('"', "'")
            lines.append(f"  {nid}[\"{lbl}\"]")
        for edge in edges:
            src = str(edge.get("from", edge.get("source", "A"))).replace(" ", "_")
            tgt = str(edge.get("to", edge.get("target", "B"))).replace(" ", "_")
            lbl = str(edge.get("label", "")).replace('"', "'")
            if lbl:
                lines.append(f"  {src} -->|\"{lbl}\"| {tgt}")
            else:
                lines.append(f"  {src} --> {tgt}")
        if len(lines) == 1: lines.append("  Sources --> Consumption")
        return "\n".join(lines)


def structured_merge(base: dict, update: dict) -> dict:
    """AST-aware structural recomposition merging two dictionary fragments natively."""
    if not isinstance(base, dict): return update
    if not isinstance(update, dict): return base
    
    merged = dict(base)
    for k, v in update.items():
        if k not in merged:
            merged[k] = v
        else:
            base_val = merged[k]
            if isinstance(base_val, dict) and isinstance(v, dict):
                merged[k] = structured_merge(base_val, v)
            elif isinstance(base_val, list) and isinstance(v, list):
                # Smart deduplication by 'name' or identity to backfill incomplete elements
                seen_names = {}
                combined_list = []
                for item in base_val + v:
                    if isinstance(item, dict) and "name" in item:
                        name_key = str(item["name"]).lower()
                        if name_key in seen_names:
                            combined_list[seen_names[name_key]] = structured_merge(combined_list[seen_names[name_key]], item)
                        else:
                            seen_names[name_key] = len(combined_list)
                            combined_list.append(item)
                    elif item not in combined_list:
                        combined_list.append(item)
                merged[k] = combined_list
            elif isinstance(base_val, str) and isinstance(v, str):
                s1 = base_val.rstrip()
                s2 = v.lstrip()
                if s1.endswith(s2[:min(20, len(s2))]):
                    merged[k] = s1
                else:
                    if "flowchart" in s1.lower() and s2.lower().startswith("flowchart"):
                        s2 = re.sub(r'^flowchart\s+[a-zA-Z]+\s*', '', s2, flags=re.IGNORECASE)
                    elif "graph" in s1.lower() and s2.lower().startswith("graph"):
                        s2 = re.sub(r'^graph\s+[a-zA-Z]+\s*', '', s2, flags=re.IGNORECASE)
                    merged[k] = s1 + "\n" + s2
            else:
                merged[k] = v if v else base_val
    return merged


# --- 1. AI CORE EXECUTION ---

TOKEN_BUDGETS = {
    "architecture_strategy": 16384,
    "schema_modeling":       16384,
    "schema_design":         16384,
    "pipeline_design":       16384,
    "governance_security":   16384,
    "ddl_generation":        16384,
    "documentation_summary": 8192,
    "data_dictionary":       8192,
    "diagram":               16384,
}


def _safe_parse(raw_output: str, task_type: str) -> dict:
    """Multi-pass parsing strategy to decode double-encoded Snowflake Cortex JSON outputs."""
    return extract_json(raw_output, task_type)


def normalize_extracted_payload(parsed: dict, task_type: str) -> dict:
    """Enforces standard alias mapping, default traps, and Mermaid multiline string synthesis."""
    if not isinstance(parsed, dict): return parsed
    
    req_keys = {
        "architecture_strategy": ["architecture_type", "modeling_paradigm", "layers", "mermaid_diagram"],
        "schema_modeling":       ["tables"],
        "pipeline_design":       ["tasks"],
        "governance_security":   ["roles", "mask"],
        "ddl_generation":        ["ddl_sql", "grant_sql"],
        "history":               ["assumptions"],
        "metadata_analysis":     ["lin", "tags"],
        "relationship_design":   ["rel", "mermaid_diagram"],
        "final_blueprint":       ["summary"],
    }.get(task_type, [])

    while isinstance(parsed, dict) and len(parsed) == 1:
        root_key = list(parsed.keys())[0]
        if root_key not in req_keys and isinstance(parsed[root_key], dict):
            parsed = parsed[root_key]
        else:
            break

    aliases = {
        "lineage": "lin", "governance_tags": "tags", "object_tags": "tags",
        "masking_policies": "mask", "masking": "mask", "rbac": "roles", "roles_defined": "roles",
        "mermaid": "mermaid_diagram", "diagram": "mermaid_diagram", 
        "architecture_diagram": "mermaid_diagram", "schema_diagram": "mermaid_diagram",
        "type": "architecture_type", "strategy": "architecture_strategy",
        "paradigm": "modeling_paradigm", "relationships": "rel", "joins": "rel",
        "summary_text": "summary"
    }

    def _map_aliases(target):
        if not isinstance(target, dict): return
        to_add = {}
        for k, v in target.items():
            if k in aliases and aliases[k] not in target:
                to_add[aliases[k]] = v
            if isinstance(v, dict): _map_aliases(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict): _map_aliases(item)
        target.update(to_add)
        
        # Intercept structured diagram dictionary and synthesize pure string representation
        if "diagram" in target and isinstance(target["diagram"], dict):
            target["mermaid_diagram"] = synthesize_mermaid_from_ast(target["diagram"], task_type)
        elif "mermaid" in target and isinstance(target["mermaid"], dict):
            target["mermaid_diagram"] = synthesize_mermaid_from_ast(target["mermaid"], task_type)

    _map_aliases(parsed)

    for k in req_keys:
        if k not in parsed:
            if k in ["tables", "tasks", "roles", "mask", "lin", "tags", "rel", "layers", "assumptions"]:
                parsed[k] = []
            elif k == "mermaid_diagram":
                parsed[k] = "graph LR\n  A --> B"
            else:
                parsed[k] = "Default/Inferred"

    if task_type == "ddl_generation" and isinstance(parsed, dict):
        import re
        for key in ["ddl_sql", "grant_sql", "transform_sql"]:
            if key in parsed and isinstance(parsed[key], str):
                parsed[key] = re.sub(r'\bCREATE\s+HYBRID\s+TABLE\b', 'CREATE TABLE', parsed[key], flags=re.IGNORECASE)

    return parsed


def call_cortex(session, prompt: str, task_type: str, model: str = "mistral-large2", max_retries: int = 3) -> dict:
    import importlib
    import dwh_assistant.backend.prompts as prompts_mod
    try:
        importlib.reload(prompts_mod)
    except Exception: pass

    from dwh_assistant.backend.snowflake import MODEL_TOKEN_CAPS

    THREE_PARAM_MODELS = {
        "claude-3-5-sonnet", "claude-3-7-sonnet",
        "claude-4-sonnet",   "claude-4-opus",
        "claude-sonnet-4-6", "claude-opus-4-6",
        "claude-haiku-4-5",  "claude-sonnet-4-5",
    }

    sys_prompt   = prompts_mod.get_system_prompt(model, task_type)
    token_cap    = MODEL_TOKEN_CAPS.get(model, 4096)
    base_limit   = TOKEN_BUDGETS.get(task_type, 4096)
    use_2_param  = model.lower() in TWO_PARAM_ONLY_MODELS
    raw_output   = None


    for attempt in range(max_retries):
        try:
            # Scale token budgets dynamically per attempt to allow incremental growth and prevent truncation
            current_limit = base_limit + (attempt * 4096)
            print(f"      [AI_COMPLETE] {model} | attempt {attempt+1}/{max_retries} | tokens={current_limit}", end="", flush=True)

            options_obj = {
                "temperature": 0,
                "max_tokens": current_limit
            }

            combined = f"{sys_prompt}\n\n{prompt}"
            if use_2_param:
                sql = """
                    SELECT SNOWFLAKE.CORTEX.COMPLETE(
                        ?::VARCHAR,
                        ?::VARCHAR
                    )
                """
                params = [model, combined]
            else:
                sql = """
                    SELECT SNOWFLAKE.CORTEX.COMPLETE(
                        ?::VARCHAR,
                        ARRAY_CONSTRUCT(OBJECT_CONSTRUCT('role', 'user', 'content', ?::VARCHAR)),
                        PARSE_JSON(?)::OBJECT
                    )
                """
                params = [model, combined, json.dumps(options_obj)]

            res        = session.sql(sql, params=params).collect()
            raw_output = res[0][0] if res else None

            if not raw_output:
                raise Exception("Empty response from Cortex")

            # Invoke robust multi-pass safe parse to resolve double-encoded strings and envelope wrappers flawlessly
            parsed = _safe_parse(raw_output, task_type)

            if isinstance(parsed, dict) and "raw_unparsed" in parsed:
                raise Exception("JSON decode failure: payload malformed or truncated")

            # --- DETERMINISTIC INTERCEPTION TIER ---
            if isinstance(parsed, dict):
                parsed = normalize_extracted_payload(parsed, task_type)

            print(f" Success")
            return {"success": True, "output": parsed, "raw": raw_output, "model": model}

        except Exception as e:
            err = str(e)
            print(f" Failed: {err[:80]}")
            if "Warehouse" in err or "suspended" in err.lower() or "57014" in err:
                try:
                    wh_name = session.get_current_warehouse() or "COMPUTE_WH"
                    session.sql(f"ALTER WAREHOUSE {wh_name} RESUME IF SUSPENDED").collect()
                except Exception: pass
                time.sleep(3 + attempt * 2) # Allow hardware compute nodes time to initialize warm execution pools
            if attempt == max_retries - 1:
                return {"success": False, "error": err, "raw": raw_output or "", "model": model}
            time.sleep(1 + attempt)

    return {"success": False, "error": "Max retries exceeded", "model": model}

def _is_truncated(raw: str) -> bool:
    """Detects if JSON output was cut off mid-structure."""
    if not raw or not raw.strip():
        return True
    stripped = raw.strip()
    
    # Strip trailing codeblock fences for accurate termination inspection
    if stripped.endswith("```"):
        stripped = re.sub(r'\s*```$', '', stripped).strip()
        
    # 1. Structural Closure Check (If it ends cleanly with a standard closing boundary, trust its integrity)
    if stripped.endswith("}") or stripped.endswith("]"):
        return False
        
    # 2. Simple termination check
    if stripped[-1] not in ('}', ']', '"', ' '):
        return True
        
    # 3. Naive balance check fallback
    open_braces = stripped.count('{')
    close_braces = stripped.count('}')
    if open_braces > close_braces:
        return True
        
    open_brackets = stripped.count('[')
    close_brackets = stripped.count(']')
    if open_brackets > close_brackets:
        return True

    return False

def call_cortex_with_continuation(session: Session, prompt: str, task_type: str, model: str = "claude-3-7-sonnet", max_retries: int = 3) -> Dict[str, Any]:
    """Wraps call_cortex with automatic continuation for truncated outputs."""
    result = call_cortex(session, prompt, task_type, model, max_retries)
    
    if result["success"]:
        # Double check: if it succeeded but result is empty or not what we want, we might still check for truncation
        return result
    
    # If it failed but we have raw output, check if it's because of truncation
    raw = result.get("raw", "")
    if raw and _is_truncated(raw):
        print(f"      [CONTINUATION] Detected truncated output, requesting continuation...", end="", flush=True)
        import importlib, re, json
        import dwh_assistant.backend.prompts as prompts_mod
        try: importlib.reload(prompts_mod)
        except Exception: pass
        
        sys_prompt = prompts_mod.get_system_prompt(model, task_type)
        continuation_prompt = (
            "You previously generated a response that was truncated mid-sentence or mid-code.\n"
            "Here is the very END of what you generated so far:\n"
            f"...{raw[-600:]}\n\n"
            "Continue from EXACTLY where it stopped. Output ONLY the exact plain text remainder. "
            "Do NOT output any introductory text, do NOT output markdown formatting fences, and do NOT restart the JSON object or properties. "
            "Just output the immediate literal continuation text directly."
        )
        
        combined_prompt = f"{sys_prompt}\n\n{continuation_prompt}"
        options_obj = {
            "temperature": 0,
            "max_tokens": 8192
        }
        
        use_2_param = model.lower() in TWO_PARAM_ONLY_MODELS
        if use_2_param:
            sql = """
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    ?::VARCHAR,
                    ?::VARCHAR
                )
            """
            params = [model, combined_prompt]
        else:
            sql = """
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    ?::VARCHAR,
                    ARRAY_CONSTRUCT(OBJECT_CONSTRUCT('role', 'user', 'content', ?::VARCHAR)),
                    PARSE_JSON(?)::OBJECT
                )
            """
            params = [model, combined_prompt, json.dumps(options_obj)]
        
        c2_raw = None
        try:
            res = session.sql(sql, params=params).collect()
            c2_raw = res[0][0] if res else None
        except Exception:
            try:
                sql2 = "SELECT SNOWFLAKE.CORTEX.COMPLETE(?::VARCHAR, ?::VARCHAR)"
                res = session.sql(sql2, params=[model, combined_prompt]).collect()
                c2_raw = res[0][0] if res else None
            except Exception: pass
            
        if c2_raw:
            c1 = raw.rstrip()
            c2 = c2_raw.strip()
            
            # 1. Clean markdown fences from c2 if present
            c2 = re.sub(r'^```(?:json|mermaid|sql)?\s*', '', c2, flags=re.IGNORECASE)
            c2 = re.sub(r'\s*```$', '', c2).strip()
            
            # 2. Derive base AST from truncated chunk natively
            dict1 = extract_json(raw, task_type)
            if not isinstance(dict1, dict) or "raw_unparsed" in dict1:
                try: dict1 = json.loads(fix_truncated_json(clean_json_string(raw)))
                except Exception: dict1 = {}
                
            dict2 = {}
            if c2.startswith('{'):
                dict2 = extract_json(c2, task_type)
                if not isinstance(dict2, dict) or "raw_unparsed" in dict2: dict2 = {}
            else:
                # Wrap fragment contents to extract populated sub-arrays cleanly
                wrapped_c2 = "{" + re.sub(r'^(?:"mermaid_diagram"|mermaid_diagram)?\s*:\s*', '', c2, flags=re.IGNORECASE)
                if not wrapped_c2.endswith("}"): wrapped_c2 += "}"
                try: dict2 = json.loads(fix_truncated_json(clean_json_string(wrapped_c2)))
                except Exception: dict2 = {}
                
            # Try raw text stitch extraction as fallback primary if merge is lean
            stitched = c1 + c2
            stitched_parsed = extract_json(stitched, task_type)
            if isinstance(stitched_parsed, dict) and "raw_unparsed" not in stitched_parsed:
                base_ast = stitched_parsed
            else:
                base_ast = dict1
                
            # Perform canonical structural merge over both object graphs natively
            parsed = structured_merge(base_ast, dict2)
            
            if isinstance(parsed, dict) and "raw_unparsed" not in parsed:
                parsed = normalize_extracted_payload(parsed, task_type)
                print(f" [CONTINUATION SUCCESS]")
                return {"success": True, "output": parsed, "raw": json.dumps(parsed), "model": model}
            else:
                print(f" [CONTINUATION FAILED]")
    
    return result

# --- 2. DATA PROFILING ---

def profile_sources(_session: Session, db: str, schema: str, tables: List[str], limit: int = 10) -> Optional[Dict[str, Any]]:
    """Profiles a list of Snowflake tables for architectural context."""
    if "profile_cache" not in st.session_state:
        st.session_state["profile_cache"] = {}
        
    cache_key = hash(f"{db}_{schema}_{str(tables)}")
    if cache_key in st.session_state["profile_cache"]:
        return st.session_state["profile_cache"][cache_key]
        
    profile = {"tables": [], "relationships": []}
    
    def profile_single_table(table_name):
        try:
            full_name = f'"{db}"."{schema}"."{table_name}"'
            columns_df = _session.sql(f"DESCRIBE TABLE {full_name}").collect()
            col_names = [row['name'] for row in columns_df]
            
            if not col_names:
                return {"name": table_name, "error": "No columns found"}

            card_exprs = ", ".join([f'APPROX_COUNT_DISTINCT("{c}") AS "{c}"' for c in col_names])
            stats_rows = _session.sql(f'SELECT COUNT(*) AS "_total_count", {card_exprs} FROM {full_name}').collect()
            stats_row = stats_rows[0].as_dict() if stats_rows else {}
            total_count = stats_row.pop("_total_count", 0)
            
            sample_df = _session.sql(f"SELECT * FROM {full_name} LIMIT {limit}").to_pandas()
            
            columns = []
            for row in columns_df:
                col_name, col_type = row['name'], row['type']
                unique_count = stats_row.get(col_name, 0)
                flags = []
                if any(id_key in col_name.lower() for id_key in ["id", "key"]): flags.append("KEY")
                if any(pii in col_name.lower() for pii in ["email", "phone", "ssn", "dob", "name"]): flags.append("PII")
                
                columns.append({
                    "name": col_name, "type": col_type, "nullable": row['null?'] == 'Y',
                    "cardinality": unique_count, "flags": flags, "is_pii": "PII" in flags, "is_key": "KEY" in flags
                })
            return {"name": table_name, "row_count": total_count, "columns": columns, "sample": sample_df.head(5).to_dict(orient="records")}
        except Exception as e:
            return {"name": table_name, "error": str(e), "row_count": 0, "columns": [], "sample": []}

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(profile_single_table, t): t for t in tables}
        for future in as_completed(futures): 
            res = future.result()
            if res: profile["tables"].append(res)
    
    final_profile = profile if profile["tables"] else None
    if final_profile:
        st.session_state["profile_cache"][cache_key] = final_profile
        
    return final_profile

# --- 3. PHYSICAL DEPLOYMENT ---

# ═══════════════════════════════════════════════
# METADATA-DRIVEN DDL UTILITIES
# ═══════════════════════════════════════════════

def layer_to_schema_name(layer_name: str) -> str:
    """
    Deterministically converts an AI-generated architecture layer name
    into a valid Snowflake schema identifier. No hardcoded names.

    Examples:
        "Bronze"            → "BRONZE"
        "Silver / Conformed" → "SILVER_CONFORMED"
        "Raw Vault"         → "RAW_VAULT"
        "Info Mart"         → "INFO_MART"
        "Gold (Semantic)"   → "GOLD_SEMANTIC"
    """
    slug = re.sub(r'[^a-zA-Z0-9]', '_', layer_name.strip())
    slug = re.sub(r'_+', '_', slug).strip('_').upper()
    return slug if slug else 'WAREHOUSE_LAYER'


def assemble_full_ddl(
    schema_context: Dict[str, Any],
    ai_ddl_parts: List[str],
    ai_grant_parts: Optional[List[str]] = None,
    ai_transform_parts: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Deterministically assembles the complete DDL deployment script from:
    - schema_context: the metadata-driven layer → schema mapping (from build_schema_context)
    - ai_ddl_parts:   raw CREATE TABLE SQL blocks returned by the AI (per batch)
    - ai_grant_parts: raw GRANT SQL blocks from the AI
    - ai_transform_parts: raw INSERT/MERGE SQL blocks from the AI

    Assembly steps:
    1. Generate CREATE SCHEMA IF NOT EXISTS for every layer in schema_context.
    2. Merge AI DDL parts, enforce IF NOT EXISTS, strip HYBRID TABLE.
    3. Deduplicate statements, preserving layer order (schemas first, DIM before FACT).
    4. Combine grants and transforms.

    Returns: {ddl_sql, grant_sql, transform_sql, schema_creation_sql}
    """
    if ai_grant_parts is None:
        ai_grant_parts = []
    if ai_transform_parts is None:
        ai_transform_parts = []

    layers = schema_context.get("layers", []) if isinstance(schema_context, dict) else []

    # ── 1. Deterministic schema creation block ──────────────────────────────
    schema_header_lines = ["-- ========================================================================="]
    schema_header_lines.append("-- SCHEMA CREATION (Derived from AI Architecture Strategy)")
    schema_header_lines.append("-- =========================================================================")
    schema_names_ordered = []
    for lm in layers:
        schema_name = lm.get("schema_name") or layer_to_schema_name(lm.get("layer_name", "WAREHOUSE"))
        schema_header_lines.append(f"CREATE SCHEMA IF NOT EXISTS {schema_name};")
        schema_names_ordered.append(schema_name)

    schema_creation_sql = "\n".join(schema_header_lines)

    # ── 2. Merge & clean AI DDL blocks ──────────────────────────────────────
    # Ensure each DDL part ends with a semicolon before joining them, to prevent merging DDL statements
    ai_ddl_cleaned = []
    for part in ai_ddl_parts:
        if not part: continue
        stripped = part.strip()
        if not stripped.endswith(';'):
            stripped += ';'
        ai_ddl_cleaned.append(stripped)

    raw_ddl_text = "\n\n".join(ai_ddl_cleaned)

    # Enforce CREATE TABLE IF NOT EXISTS (never skip IF NOT EXISTS)
    raw_ddl_text = re.sub(
        r'\bCREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS)',
        'CREATE TABLE IF NOT EXISTS ',
        raw_ddl_text, flags=re.IGNORECASE
    )
    # Strip any HYBRID TABLE references (Snowflake rule: standard tables only)
    raw_ddl_text = re.sub(r'\bCREATE\s+HYBRID\s+TABLE\b', 'CREATE TABLE', raw_ddl_text, flags=re.IGNORECASE)
    # Strip any lingering SCHEMA creation statements in AI output (we emit ours deterministically)
    raw_ddl_text = re.sub(r'CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+\S+\s*;?', '', raw_ddl_text, flags=re.IGNORECASE)

    # Strip FOREIGN KEY constraints to prevent deployment failures on missing/hallucinated AI dimensions
    fk_pattern = r'(?i),\s*(?:CONSTRAINT\s+[a-zA-Z0-9_]+\s+)?FOREIGN\s+KEY\s*\([^)]+\)\s*REFERENCES\s+[a-zA-Z0-9_.\"\'\[\]]+(?:\s*\([^)]+\))?(?:\s*ON\s+(?:DELETE|UPDATE)\s+(?:CASCADE|SET\s+NULL|SET\s+DEFAULT|RESTRICT|NO\s+ACTION))?'
    raw_ddl_text = re.sub(fk_pattern, '', raw_ddl_text)
    # Catch any remaining trailing commas before a closing parenthesis (caused by stripping the last column)
    raw_ddl_text = re.sub(r',\s*\)', '\n)', raw_ddl_text)

    # ── 3. Split, deduplicate, and order statements ──────────────────────────
    stmts_raw = [s.strip() for s in raw_ddl_text.split(";") if s.strip()]

    # Remove pure-comment-only statements
    def _has_sql(stmt: str) -> bool:
        no_comments = re.sub(r'--.*?(\n|$)', '', stmt, flags=re.MULTILINE)
        no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL)
        return bool(no_comments.strip())

    stmts_raw = [s for s in stmts_raw if _has_sql(s)]

    # Deduplicate by normalised statement body
    seen: Dict[str, str] = {}
    for stmt in stmts_raw:
        key = re.sub(r'\s+', ' ', stmt.upper()).strip()
        if key not in seen:
            seen[key] = stmt

    unique_stmts = list(seen.values())

    # Sort: DIM tables first (so FKs from FACT resolve), then FACT, then everything else
    def _sort_key(s: str) -> tuple:
        su = s.upper()
        # Match both SCHEMA.DIM_TABLE and bare DIM_TABLE
        if re.search(r'(?:^|[\s.(])DIM_', su):   return (0, s)
        if re.search(r'(?:^|[\s.(])(HUB_|LNK_|SAT_)', su): return (1, s)
        if re.search(r'(?:^|[\s.(])(RAW_|STG_|STAGE_|BRONZE)', su): return (2, s)
        if re.search(r'(?:^|[\s.(])(SILVER|CONFORMED|CLEANED)', su): return (3, s)
        if re.search(r'(?:^|[\s.(])(FACT_|FCT_)', su): return (4, s)
        return (5, s)

    unique_stmts.sort(key=_sort_key)

    # ── 4. Final DDL: schema creation header + ordered table DDL ────────────
    table_ddl_block = ";\n\n".join(unique_stmts)
    if table_ddl_block:
        table_ddl_block += ";"

    full_ddl_sql = (
        schema_creation_sql
        + "\n\n-- =========================================================================\n"
        + "-- TABLE DDL (Fully Qualified: schema_name.table_name)\n"
        + "-- =========================================================================\n"
        + (table_ddl_block or "-- No DDL statements generated by AI.")
    )

    # ── 5. Grants ───────────────────────────────────────────────────────────
    raw_grant_sql = "\n\n".join(filter(None, ai_grant_parts)) or ""
    
    # Extract all CREATE ROLE statements to move them to the top
    grant_stmts = [s.strip() for s in raw_grant_sql.split(";") if s.strip()]
    create_roles = [
        "CREATE ROLE IF NOT EXISTS DATA_VIEWER",
        "CREATE ROLE IF NOT EXISTS DATA_PIPELINE_ROLE"
    ]
    other_grants = []
    
    for stmt in grant_stmts:
        if re.search(r'^\s*CREATE\s+(?:OR\s+REPLACE\s+)?ROLE', stmt, re.IGNORECASE):
            # Enforce IF NOT EXISTS so it doesn't fail if the role exists
            clean_stmt = re.sub(r'CREATE\s+(?:OR\s+REPLACE\s+)?ROLE\s+(IF\s+NOT\s+EXISTS\s+)?', 'CREATE ROLE IF NOT EXISTS ', stmt, flags=re.IGNORECASE)
            create_roles.append(clean_stmt)
        else:
            other_grants.append(stmt)
            
    # Deduplicate create_roles just in case
    unique_create_roles = []
    seen_roles = set()
    for cr in create_roles:
        # Extract role name roughly
        match = re.search(r'CREATE\s+ROLE\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z0-9_]+)', cr, re.IGNORECASE)
        rname = match.group(1).upper() if match else cr.upper()
        if rname not in seen_roles:
            unique_create_roles.append(cr)
            seen_roles.add(rname)
            
    final_grant_parts = [cr + ";" for cr in unique_create_roles] + [og + ";" for og in other_grants]
    grant_sql = "\n".join(final_grant_parts) or "-- No GRANT statements generated."

    # ── 6. Transforms ───────────────────────────────────────────────────────
    transform_sql = "\n\n".join(filter(None, ai_transform_parts)) or "-- No transformation samples generated."

    return {
        "ddl_sql":            full_ddl_sql,
        "grant_sql":          grant_sql,
        "transform_sql":      transform_sql,
        "schema_creation_sql": schema_creation_sql,
    }


def _sanitize_bind_vars(sql: str) -> str:
    """Replace Snowflake bind variables like :batch_id with a dummy literal to avoid execution errors."""
    return re.sub(r':\w+', '0', sql)


def format_ddl(ddl_output: Dict[str, Any], include_transforms: bool = False) -> str:
    """Combines various SQL artifacts into a single executable script, ensuring no stray quotes."""
    # Retrieve blocks, default to empty strings
    schema_block = ddl_output.get("schema_creation_sql", "") or ""
    ddl_block    = ddl_output.get("ddl_sql", "") or ""
    grant_block  = ddl_output.get("grant_sql", "") or ""
    xform_block  = ddl_output.get("transform_sql", "") or ""
    # Clean potential surrounding quotes
    def clean_block(block: str) -> str:
        blk = block.strip()
        if blk.startswith('"') and blk.endswith('"'):
            blk = blk[1:-1]
        return blk
    schema_block = clean_block(schema_block)
    ddl_block = clean_block(ddl_block)
    grant_block = clean_block(grant_block)
    xform_block = clean_block(xform_block)
    parts = []
    if schema_block and schema_block not in ddl_block:
        parts.append(f"-- SCHEMA CREATION\n{schema_block}")
    if ddl_block:
        parts.append(f"-- DDL\n{ddl_block}")
    if grant_block:
        parts.append(f"-- GRANTS\n{grant_block}")
    if include_transforms and xform_block:
        parts.append(f"-- TRANSFORMS\n{xform_block}")
    return "\n\n".join(parts)


def execute_deployment(
    session: Session,
    ddl_sql: str,
    target_db: str,
    target_schema: str = "PUBLIC",
    project_id: str = "N/A",
    schema_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes SQL statements natively using Snowflake transactions for safety.

    If `schema_context` is provided, all AI-derived schemas are pre-created
    under `target_db` before executing the main DDL statements.
    """
    # Clean possible surrounding quotes from the entire DDL string
    ddl_sql = ddl_sql.strip()
    if ddl_sql.startswith('"') and ddl_sql.endswith('"'):
        ddl_sql = ddl_sql[1:-1]

    import re
    # Convert hybrid tables to standard tables to prevent invalid FK constraints
    ddl_sql = re.sub(r'\bCREATE\s+HYBRID\s+TABLE\b', 'CREATE TABLE', ddl_sql, flags=re.IGNORECASE)

    raw_statements = [s.strip() for s in ddl_sql.split(";") if s.strip()]
    statements = []
    for s in raw_statements:
        no_comments = re.sub(r'--.*?(\n|$)', '', s, flags=re.MULTILINE)
        no_comments = re.sub(r'/\*.*?\*/', '', no_comments, flags=re.DOTALL)
        if no_comments.strip():
            # Sanitize bind variables before execution
            sanitized = _sanitize_bind_vars(s)
            statements.append(sanitized)
    executed = []

    try:
        if not re.match(r'^[a-zA-Z0-9_]+$', target_db) or not re.match(r'^[a-zA-Z0-9_]+$', target_schema):
            raise ValueError("Database and Schema names must contain only alphanumeric characters and underscores.")

        session.sql(f"CREATE DATABASE IF NOT EXISTS {target_db}").collect()
        session.use_database(target_db)

        # ── Pre-create all AI-derived schemas (metadata-driven) ──────────────
        if schema_context and isinstance(schema_context, dict):
            for lm in schema_context.get("layers", []):
                sname = lm.get("schema_name") or layer_to_schema_name(lm.get("layer_name", "WAREHOUSE"))
                try:
                    session.sql(f"CREATE SCHEMA IF NOT EXISTS {sname}").collect()
                    print(f"[DEPLOY] Schema created: {target_db}.{sname}")
                except Exception as se:
                    print(f"[WARNING] Could not create schema {sname}: {se}")

        # Always create the user-specified target schema as well
        session.sql(f"CREATE SCHEMA IF NOT EXISTS {target_schema}").collect()
        session.use_schema(target_schema)

        # Extract and pre-create any custom roles referenced in the DDL
        roles_to_create = set()
        for stmt in statements:
            matches = re.findall(r'\bROLE\s+([a-zA-Z0-9_]+)', stmt, re.IGNORECASE)
            for m in matches:
                if m.upper() not in ["ACCOUNTADMIN", "SECURITYADMIN", "USERADMIN", "SYSADMIN", "PUBLIC"]:
                    roles_to_create.add(m.upper())

        for role in sorted(roles_to_create):
            try:
                session.sql(f"CREATE ROLE IF NOT EXISTS {role}").collect()
            except Exception as role_e:
                print(f"[WARNING] Failed to create role {role}: {role_e}")

        statements = [_sanitize_bind_vars(s) for s in statements]
        # Strip surrounding quotes and escaped characters that may be introduced by JSON extraction
        cleaned_statements = []
        for stmt in statements:
            cleaned = stmt.strip()
            # Remove surrounding single or double quotes
            cleaned = cleaned.strip('"\'')
            # Unescape escaped double quotes
            cleaned = cleaned.replace('\\"', '"')
            # Unescape escaped single quotes
            cleaned = cleaned.replace("\\'", "'")
            # Remove any leading/trailing backticks or markdown fences
            cleaned = re.sub(r'^```(?:sql|json)?\s*', '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'\s*```$', '', cleaned)
            cleaned = cleaned.strip()
            cleaned_statements.append(cleaned)
        
        
        session.sql("BEGIN").collect()
        for stmt in cleaned_statements:
            try:
                session.sql(stmt).collect()
                executed.append(stmt)
            except Exception as stmt_e:
                err_msg = str(stmt_e).lower()
                if "does not exist" in err_msg or "doesn't exist" in err_msg or "not found" in err_msg:
                    print(f"[WARNING] Skipping statement due to missing object: {stmt_e}")
                    executed.append(f"-- SKIPPED (Object does not exist): {stmt}")
                    skipped_count += 1
                else:
                    raise stmt_e
        session.sql("COMMIT").collect()

        log_deployment(session, project_id, target_db, target_schema, len(statements), "success")
        return {"success": True, "statements_run": len(statements), "skipped_count": skipped_count}

    except Exception as e:
        try:
            session.sql("ROLLBACK").collect()
            rollback_msg = "Transaction rolled back automatically."
        except Exception as rb_e:
            rollback_msg = f"Rollback failed: {rb_e}"

        log_deployment(session, project_id, target_db, target_schema, len(executed), "failed", {"error": str(e)})
        return {"success": False, "error": str(e), "rollback": [rollback_msg]}
