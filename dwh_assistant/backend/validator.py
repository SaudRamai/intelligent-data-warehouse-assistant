import json
import re
from typing import Dict, Any, List, Optional
from collections import defaultdict

def clean_json_string(s: str) -> str:
    """Surgically repairs common JSON malformations and extracts JSON from noise."""
    if not s: return s
    
    # 1. Strip markdown wrappers
    s = re.sub(r'^```(?:json)?\s*', '', s.strip(), flags=re.IGNORECASE)
    s = re.sub(r'\s*```$', '', s)
    
    # 2. Extract first { or [ to last } or ] to ignore conversational noise
    start_brace = s.find('{')
    start_bracket = s.find('[')
    
    start_idx = -1
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        start_idx = start_brace
    elif start_bracket != -1:
        start_idx = start_bracket
        
    if start_idx != -1:
        end_brace = s.rfind('}')
        end_bracket = s.rfind(']')
        end_idx = max(end_brace, end_bracket)
        if end_idx != -1 and end_idx > start_idx:
            s = s[start_idx:end_idx+1]

    # 3. Clean common issues
    s = re.sub(r'//.*?\n|/\*.*?\*/', '', s, flags=re.DOTALL)
    s = re.sub(r'^\s*#.*$', '', s, flags=re.MULTILINE)
    s = re.sub(r"(?<!\w)\'(\w+)\'\s*:", r'"\1":', s)
    s = re.sub(r'([\{\,]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', s)
    s = re.sub(r":\s*\'([^'\\]*(?:\\.[^'\\]*)*)\'", r': "\1"', s, flags=re.DOTALL)
    s = re.sub(r'([\"|0-9|e|\]|\}])\s*\n\s*\"', r'\1,\n"', s)
    s = re.sub(r',(\s*[}\]])$', r'\1', s.strip())
    s = re.sub(r',\s*$', '', s)
    s = s.replace("\\'", "'")
    s = re.sub(r'\\(?![\\\"\/bfnrtuwWdDsSpP\(\)\[\]\{\}\.\*\+\?\^\$\|])', r'\\\\', s)
    
    # 4. Escape literal newlines inside JSON strings (Crucial for multiline Mermaid strings)
    res = []
    in_string = False
    escape = False
    for char in s:
        if escape:
            res.append(char)
            escape = False
            continue
        if char == '\\':
            res.append(char)
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            res.append(char)
            continue
        if in_string and char == '\n':
            res.append('\\n')
        elif in_string and char == '\r':
            pass
        else:
            res.append(char)
    s = "".join(res)
    
    return s.strip()

def fix_truncated_json(s: str) -> str:
    """Attempts to close unclosed JSON structures and preserves truncated strings."""
    # Standard bracket balancing and natural string closure
    stack = []
    in_string = False
    escape = False
    fixed = ""
    for char in s:
        if escape: fixed += char; escape = False; continue
        if char == '\\': fixed += char; escape = True; continue
        if char == '"': in_string = not in_string; fixed += char; continue
        if not in_string:
            if char == '{': stack.append('}')
            elif char == '[': stack.append(']')
            elif char == '}': 
                if stack and stack[-1] == '}': stack.pop()
            elif char == ']':
                if stack and stack[-1] == ']': stack.pop()
        fixed += char
    if in_string: fixed += '"'
    while stack: fixed += stack.pop()
    return fixed

def heal_mermaid_flow(mermaid: str) -> str:
    """
    Surgically detects and reverses inverted data flows in Mermaid diagrams.
    Ensures Sources -> Bronze -> Silver -> Gold direction.
    """
    if "flowchart" not in mermaid.lower() and "graph" not in mermaid.lower():
        return mermaid
        
    lines = mermaid.split('\n')
    healed_lines = []
    
    # Layer Weighting for directional enforcement
    layer_weights = {
        "source": 0, "src": 0, "erp": 0, "crm": 0, "app": 0, "s1": 0, "s2": 0, "s3": 0, "s4": 0, "feed": 0, "landing": 0,
        "bronze": 1, "raw": 1, "raw_vault": 1, "hub": 1, "lnk": 1, "sat": 1, "b1": 1, "b2": 1, "stage": 1, "stg": 1, "ingest": 1,
        "silver": 2, "cleaned": 2, "conformed": 2, "stg_": 2, "business_vault": 2, "bv_": 2, "s1a": 2, "s2a": 2,
        "gold": 3, "curated": 3, "enriched": 3, "semantic": 3, "infomart": 3, "mart": 3, "info_mart": 3, "fct_": 3, "dim_": 3, "fact_": 3, "s1b": 3, "s2b": 3, "g1": 3, "g2": 3, "presentation": 3,
        "consumption": 4, "bi": 4, "analytics": 4, "analyst": 4, "cortex": 4, "reporting": 4, "dashboard": 4, "app_": 4
    }
    
    def get_weight(node_text: str) -> int:
        node_text = node_text.lower()
        for prefix, weight in layer_weights.items():
            if prefix in node_text:
                return weight
        return -1

    for line in lines:
        # Match common arrow pattern: A --> B or A -- label --> B
        match = re.search(r'([^\s-]+)\s*(?:--[^>]*--|--+)\s*>\s*([^\s\[({]+)', line)
        if match:
            node_a, node_b = match.group(1), match.group(2)
            weight_a = get_weight(node_a)
            weight_b = get_weight(node_b)
            
            # If both nodes have identifiable layers and flow is inverted (A > B)
            if weight_a != -1 and weight_b != -1 and weight_a > weight_b:
                arrow_part_match = re.search(r'(\s*(?:--[^>]*--|--+)\s*>)', line)
                if arrow_part_match:
                    arrow_part = arrow_part_match.group(1)
                    parts = line.split(arrow_part)
                    if len(parts) == 2:
                        flipped_line = f"    {parts[1].strip()} {arrow_part} {parts[0].strip()}"
                        healed_lines.append(flipped_line)
                        continue
        
        healed_lines.append(line)
        
    return "\n".join(healed_lines)

def validate_step_output(step_name: str, data: Any, required_keys: List[str], schema_specs: Dict[str, Any]) -> bool:
    """Centralized validation engine for AI-generated artifacts."""
    if not isinstance(data, dict): return False
    
    # 1. Mandatory Key Check
    missing = [k for k in required_keys if k not in data]
    if missing: return False
    
    # 2. Type Enforcement
    for key, expected_type in schema_specs.items():
        if key in data and not isinstance(data[key], expected_type):
            return False
            
    # 3. Quality Check
    if "tables" in data:
        if not isinstance(data["tables"], list) or len(data["tables"]) == 0:
            if step_name in ["schema_details", "schema_design", "schema_modeling"]:
                return False
    return True

def heal_mermaid_diagram(mermaid: str) -> str:
    """
    Surgically repairs Mermaid syntax errors and enforces structural integrity.
    """
    if not mermaid: return ""
    
    # 1. Basic cleaning and header ensuring
    mermaid = mermaid.strip()
    # Only unescape JSON escape sequences if they are still present as raw literals
    # (i.e. the string was NOT yet parsed through json.loads). Applying these
    # replacements to an already-decoded string corrupts valid node labels.
    if '\\n' in mermaid or '\\"' in mermaid or '\\\\' in mermaid:
        mermaid = mermaid.replace('\\\\', '\x00__SLASH__\x00')  # protect real backslashes
        mermaid = mermaid.replace('\\n', '\n')
        mermaid = mermaid.replace('\\"', '"')
        mermaid = mermaid.replace('\x00__SLASH__\x00', '\\')
    
    # ER Diagram Type Simplification (Visual Only)
    if "erDiagram" in mermaid.lower():
        mermaid = mermaid.replace("TIMESTAMP_NTZ", "TIMESTAMP")
        mermaid = mermaid.replace("TIMESTAMP_LTZ", "TIMESTAMP")
        mermaid = mermaid.replace("TIMESTAMP_TZ", "TIMESTAMP")
        mermaid = mermaid.replace("NUMBER(38,0)", "NUMBER")

    valid_headers = ['graph', 'flowchart', 'erDiagram', 'sequenceDiagram', 'classDiagram', 'gantt', 'pie']
    lines = mermaid.split('\n')
    if not lines: return ""
    first_line = lines[0].strip().lower()
    
    has_header = any(first_line.startswith(h.lower()) for h in valid_headers)
    if not has_header:
        mermaid = "flowchart LR\n" + mermaid
        lines = mermaid.split('\n')

    # 2. Route to specialized cleaners
    if "erDiagram" in mermaid:
        return clean_mermaid_erd(mermaid)
    elif "flowchart" in mermaid or "graph" in mermaid:
        mermaid = clean_mermaid_flowchart(mermaid)
        return heal_mermaid_flow(mermaid)
        
    return mermaid

def clean_mermaid_flowchart(code: str) -> str:
    """Sanitizer for flowchart/graph diagrams.
    
    Preserves node labels inline on edge lines to avoid blank-node rendering.
    Collects standalone node label definitions in a first pass, then emits
    edges with full labels, and defers classDef/class/style lines to the end.
    """
    if not code: return ""
    lines = code.split("\n")
    cleaned = []
    seen_edges = set()

    # 1. Isolate the header
    header_found = False
    start_line = 0
    for i, line in enumerate(lines):
        match = re.search(r'^\s*(flowchart|graph)\s+[^\s]+', line, re.IGNORECASE)
        if match:
            header = match.group(0).strip()
            cleaned.append(header)
            remaining = line[match.end():].strip()
            if remaining:
                lines[i] = remaining
                start_line = i
            else:
                start_line = i + 1
            header_found = True
            break

    if not header_found:
        cleaned.append("flowchart LR")
        start_line = 0

    def sanitize_id(nid: str) -> str:
        s = nid.strip()
        s = re.sub(r'[\.\s\-]+', '_', s)
        s = re.sub(r'[^a-zA-Z0-9_]', '', s)
        s = re.sub(r'_+', '_', s).strip('_')
        low = s.lower()
        if low == "silve": s = "SILVER" if s.isupper() else "Silver"
        elif low == "bronz": s = "BRONZE" if s.isupper() else "Bronze"
        elif low == "strat": s = "STRATEGY" if s.isupper() else "Strategy"
        return s or "node"

    def _close_bracket(inner: str) -> str:
        """Ensure bracket content is properly closed."""
        pairs = [("[[", "]]"), ("{{", "}}"), ("([", "])"), ("[(", ")]"), ("((", "))"),
                 ("[", "]"), ("(", ")"), ("{", "}")]
        for op, cl in pairs:
            if inner.startswith(op) and not inner.endswith(cl):
                return inner + cl
        return inner

    def _format_node(n_id: str, bracket_content: str) -> str:
        """Build a clean  id["Label"]  node string."""
        inner = _close_bracket(bracket_content.strip())
        label = re.sub(r'^[\[\(\{]+|[\]\)\}]+$', '', inner).strip().strip('"').strip("'")
        sp = inner[:2] if inner[:2] in ["[[", "{{", "([", "[(", "(("] else inner[:1]
        ss = inner[-2:] if inner[-2:] in ["]]", "}}", "])", ")]", "))"] else inner[-1:]
        return f'{n_id}{sp}"{label}"{ss}'

    # 2. First pass: collect standalone node label definitions
    node_labels: dict = {}
    for line in lines[start_line:]:
        l = line.strip()
        if not l or l.startswith("%%"):
            continue
        if any(arrow in l for arrow in ["-->", "---", "-.-", "==>"]):  # skip edge lines
            continue
        if any(l.lower().startswith(x) for x in ["subgraph", "end", "classdef", "class ", "style ", "direction", "flowchart", "graph"]):
            continue
        br = re.search(r'([\[\(\{].*)', l)
        if br:
            nid = sanitize_id(re.split(r'[\[\(\{]', l, 1)[0])
            if nid:
                node_labels[nid] = _format_node(nid, br.group(1))

    emitted_nodes: set = set()
    style_lines = []

    # 3. Main pass
    for line in lines[start_line:]:
        l = line.strip()
        if not l:
            continue
            
        if l == "end" or l.startswith("%%"):
            cleaned.append(f"    {l}")
            continue

        l = re.sub(r'\.\s*$', '', l)

        # Defer style/class lines
        if any(l.lower().startswith(x) for x in ["classdef", "class ", "style "]):
            style_lines.append(f"    {l}")
            continue

        # Subgraph
        sg = re.search(r'subgraph\s+([^"\[\(\s\n]+)?\s*(?:["\[\(]([^"\]\)]+?)["\]\)])?', l, re.IGNORECASE)
        if sg and not l.startswith(("end", "flowchart", "graph")):
            s_id, s_label = sg.groups()
            title = (s_label or s_id or "layer").strip().rstrip('.')
            cleaned.append(f"    subgraph {sanitize_id(s_id or title)} [\"{title}\"]")
            continue

        # Edge lines
        if any(arrow in l for arrow in ["-->", "---", "-.-", "==>"]):  # noqa
            am = re.search(r'(\-\-\>|\-\-\-|\-\.\-|\=\=\>)', l)
            if am:
                arrow = am.group(1)
                p0, p1 = l.split(arrow, 1)
                src_part = p0.strip()
                tgt_part = p1.strip()

                src_split = re.split(r'[\[\(\{]', src_part, 1)
                src_id = sanitize_id(src_split[0])

                tgt_split = re.split(r'[\[\(\{]', tgt_part, 1)
                tgt_id = sanitize_id(tgt_split[0])

                if src_id and tgt_id and src_id != tgt_id:
                    edge_key = (src_id, tgt_id, arrow)
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)

                        # Build node strings with labels
                        if len(src_split) > 1:
                            src_str = _format_node(src_id, "[" + src_split[1])
                            node_labels[src_id] = src_str
                            emitted_nodes.add(src_id)
                        elif src_id in node_labels:
                            src_str = node_labels[src_id]
                            emitted_nodes.add(src_id)
                        else:
                            src_str = src_id

                        if len(tgt_split) > 1:
                            tgt_str = _format_node(tgt_id, "[" + tgt_split[1])
                            node_labels[tgt_id] = tgt_str
                            emitted_nodes.add(tgt_id)
                        elif tgt_id in node_labels:
                            tgt_str = node_labels[tgt_id]
                            emitted_nodes.add(tgt_id)
                        else:
                            tgt_str = tgt_id

                        cleaned.append(f"    {src_str} {arrow} {tgt_str}")
            continue

        # Standalone node definitions (only emit if not already emitted via an edge)
        if not any(l.lower().startswith(x) for x in ["classdef", "class", "style", "direction"]):
            br = re.search(r'([\[\(\{].*)', l)
            if br:
                n_id = sanitize_id(re.split(r'[\[\(\{]', l, 1)[0])
                if n_id and n_id not in emitted_nodes:
                    cleaned.append(f"    {_format_node(n_id, br.group(1))}")
                    emitted_nodes.add(n_id)
            else:
                n_id = sanitize_id(l)
                if n_id and n_id not in ["flowchart", "graph"] and n_id not in emitted_nodes:
                    cleaned.append(f"    {n_id}")
                    emitted_nodes.add(n_id)
        else:
            style_lines.append(f"    {l}")

    if style_lines:
        cleaned.extend(style_lines)

    return "\n".join(cleaned)

# --- Mermaid ERD Syntax & Formatting Helpers ---

_SAFE_ID = re.compile(r'[^A-Z0-9_]')

def _eid(raw: str) -> str:
    """Normalises to uppercase alphanumeric+underscore identifier, collapsing multiple underscores."""
    if not raw:
        return "ENTITY"
    # Replace spaces, dots, hyphens with underscore
    s = re.sub(r'[\.\s\-]+', '_', str(raw).strip()).upper()
    # Retain only alphanumeric and underscore
    s = _SAFE_ID.sub('', s)
    # Collapse multiple underscores and strip leading/trailing
    s = re.sub(r'_+', '_', s).strip('_')
    # Reject artificial/invalid entity names that are completely empty or too short
    return s if s else "ENTITY"

_TYPE_MAP = {
    "varchar": "string", "text": "string", "nvarchar": "string", "char": "string", "string": "string",
    "charactervarying": "string",
    "number": "number",  "numeric": "number", "decimal": "number", "float": "float", "double": "float",
    "doubleprecision": "float",
    "int": "int", "integer": "int", "bigint": "int", "smallint": "int", "tinyint": "int",
    "bool": "boolean", "boolean": "boolean",
    "date": "date", "datetime": "timestamp", "timestamp": "timestamp",
    "timestamp_ntz": "timestamp", "timestamp_ltz": "timestamp", "timestamp_tz": "timestamp",
    "timestampwithouttimezone": "timestamp", "timestampwithtimezone": "timestamp",
    "variant": "string", "object": "string", "array": "string", "json": "string"
}

def normalize_attribute_type(t: str, col_name: str = "") -> str:
    """Maps database-specific type to standard clean types supported by Mermaid."""
    # Split by parenthesis to ignore lengths or precision scale, e.g. VARCHAR(50) or NUMBER(38,0)
    cleaned = str(t).lower().split("(")[0].strip()
    cleaned = re.sub(r'[^a-z0-9_]', '', cleaned)
    
    mapped = _TYPE_MAP.get(cleaned, cleaned[:20]) or "string"
    
    # Refine "number" to int or float based on semantic naming of the column
    if mapped == "number":
        c_low = str(col_name).lower()
        if any(x in c_low for x in ["price", "amount", "rate", "discount", "freight", "tax", "cost", "value", "amt"]):
            return "float"
        return "int"
        
    return mapped

def layer_sort_key(layer_name: str) -> int:
    """Logically orders layers for medallion and similar architectures."""
    l = str(layer_name).lower()
    if "bronze" in l or "raw" in l or "landing" in l:
        return 0
    if "staging" in l or "silver" in l or "clean" in l or "conform" in l:
        return 1
    if "ods" in l or "operational" in l:
        return 2
    if "gold" in l or "curated" in l or "mart" in l or "fact" in l or "dim" in l:
        return 3
    return 4

def get_layer_for_table(name: str, table_to_layer: Optional[Dict[str, str]] = None) -> str:
    """Identifies/infers the logical layer of a table name using heuristics or metadata."""
    normalized_name = _eid(name)
    if table_to_layer and normalized_name in table_to_layer:
        return table_to_layer[normalized_name]
        
    # Fallback to heuristics
    if any(x in normalized_name for x in ["BRONZE", "RAW", "LANDING", "SRC_"]):
        return "Bronze"
    if any(x in normalized_name for x in ["SILVER", "STAGING", "STG_", "CLEAN", "CONFORMED"]):
        return "Silver"
    if "ODS" in normalized_name:
        return "ODS"
    if any(x in normalized_name for x in ["GOLD", "FACT_", "DIM_", "FCT_", "MART", "PRES_"]):
        return "Gold"
    return "Warehouse"

def clean_mermaid_erd(code: str) -> str:
    """
    Industrial-grade sanitizer and reconstructor for erDiagrams.
    Performs strict deduplication by merging entity attributes across repeated blocks,
    removes duplicate table definitions, extracts or infers valid relationships,
    resolves syntax errors (like spaces/brackets/invalid types), and reconstructs
    the diagram layer-by-layer separated into distinct comment-labeled sections.
    """
    if not code: return "erDiagram\n"
    
    lines = code.split("\n")
    entities: Dict[str, List[str]] = {}
    seen_attrs: Dict[str, set] = {}
    relationships: List[Dict[str, str]] = []
    seen_rels = set()
    
    current_entity = None
    
    # Improved regex for ER relationships
    rel_regex = r'([a-zA-Z0-9_\.\s\-]+)\s+([\|\}o][\|o]?[\-\.][\-\.][\|o]?[\|\{o])\s+([a-zA-Z0-9_\.\s\-]+)(?:\s*:\s*"?([^"]*)"?)?'
    
    for line in lines:
        l = line.strip()
        if not l or l.lower().startswith("erdiagram") or l.startswith("%%"): continue
        
        # Check if line contains a relationship
        edge_match = re.search(rel_regex, l)
        simple_match = None
        if not edge_match:
            simple_match = re.search(r'^([a-zA-Z0-9_\.\s\-]+)\s+(?:-->|--+|->)\s+([a-zA-Z0-9_\.\s\-]+)', l)
            
        if edge_match or simple_match:
            if edge_match:
                src, rel_type, tgt, label = edge_match.groups()
            else:
                src, tgt = simple_match.groups()
                rel_type, label = "||--o{", "references"
                
            src_eid = _eid(src)
            tgt_eid = _eid(tgt)
            
            if src_eid and tgt_eid and src_eid != tgt_eid:
                rel_key = (src_eid, tgt_eid)
                if rel_key not in seen_rels and (tgt_eid, src_eid) not in seen_rels:
                    seen_rels.add(rel_key)
                    clean_label = str(label or "references").strip().replace(' ', '_').replace('"', '').replace("'", "")
                    relationships.append({
                        "from": src_eid,
                        "to": tgt_eid,
                        "rel_type": rel_type,
                        "label": clean_label
                    })
                    # Ensure both entities exist in registry
                    if src_eid not in entities: 
                        entities[src_eid] = []
                        seen_attrs[src_eid] = set()
                    if tgt_eid not in entities: 
                        entities[tgt_eid] = []
                        seen_attrs[tgt_eid] = set()
            continue

        # Check for start of entity block
        if "{" in l:
            match = re.search(r'^([a-zA-Z0-9_\.\s\-]+)\s*\{', l)
            if match:
                ent_raw = match.group(1).strip()
                ent = _eid(ent_raw)
                if ent:
                    current_entity = ent
                    if current_entity not in entities:
                        entities[current_entity] = []
                        seen_attrs[current_entity] = set()
                # Check if there are attributes inline after {
                inline_attr = l.split("{", 1)[1].strip().rstrip("}")
                if inline_attr:
                    parts = [p.strip() for p in inline_attr.split() if p.strip()]
                    if len(parts) >= 2:
                        col_type = normalize_attribute_type(parts[0], parts[1])
                        col_name = re.sub(r'[^a-zA-Z0-9_]', '', parts[1])
                        col_key = col_name.lower()
                        if col_key not in seen_attrs.get(current_entity, set()):
                            seen_attrs[current_entity].add(col_key)
                            marker = parts[2] if len(parts) > 2 else ""
                            marker = re.sub(r'[^A-Z0-9_]', '', marker).upper()
                            if marker not in ["PK", "FK"]: marker = ""
                            entities[current_entity].append(f"        {col_type} {col_name} {marker}".strip())
            continue
            
        # Check for end of entity block
        if "}" in l:
            current_entity = None
            continue
            
        # If we are inside an entity block, parse attributes
        if current_entity:
            raw_parts = [p.strip() for p in l.split() if p.strip()]
            if len(raw_parts) >= 2:
                col_type = normalize_attribute_type(raw_parts[0], raw_parts[1])
                col_name = re.sub(r'[^a-zA-Z0-9_]', '', raw_parts[1])
                col_key = col_name.lower()
                if col_key not in seen_attrs.get(current_entity, set()):
                    seen_attrs[current_entity].add(col_key)
                    marker = raw_parts[2] if len(raw_parts) > 2 else ""
                    marker = re.sub(r'[^A-Z0-9_]', '', marker).upper()
                    if marker not in ["PK", "FK"]: marker = ""
                    entities[current_entity].append(f"        {col_type} {col_name} {marker}".strip())
            elif len(raw_parts) == 1:
                col_name = re.sub(r'[^a-zA-Z0-9_]', '', raw_parts[0])
                col_key = col_name.lower()
                if col_key not in seen_attrs.get(current_entity, set()):
                    seen_attrs[current_entity].add(col_key)
                    col_type = "string" if not col_name.endswith(("_sk", "_id")) else "int"
                    marker = "PK" if col_name.endswith("_sk") else ""
                    entities[current_entity].append(f"        {col_type} {col_name} {marker}".strip())

    # Build diagram sections layer-by-layer
    layer_groups = defaultdict(list)
    for ent in entities.keys():
        layer_groups[get_layer_for_table(ent)].append(ent)

    # Sort layers
    sorted_layers = sorted(layer_groups.keys(), key=layer_sort_key)
    
    # Filter out Bronze / Raw / Landing layers if other warehouse layers exist
    warehouse_layers = [l for l in sorted_layers if l.lower() not in ["bronze", "raw", "landing", "ingest"]]
    target_layers = warehouse_layers if warehouse_layers else sorted_layers
    
    final_sections = []
    rendered_tables = set()
    for layer in target_layers:
        rendered_tables.update(layer_groups[layer])
    
    # 1. Output strict, deduplicated, fully populated entities layer by layer
    for layer in target_layers:
        layer_ents = layer_groups[layer]
        layer_lines = []
        layer_lines.append(f"\n  %% ─── {layer.upper()} LAYER ───")
        for ent in sorted(layer_ents):
            if ent in ["ERDIAGRAM", "SELECT", "FROM", "WHERE", "END"]: continue
            layer_lines.append(f"  {ent} {{")
            attrs = entities[ent]
            if not attrs:
                layer_lines.append(f"    int {ent.lower()}_sk PK")
            else:
                for attr in attrs:
                    layer_lines.append(f"    {attr.strip()}")
            layer_lines.append("  }")
            
        # Group intra-layer relationships inside the layer section
        layer_table_names = set(layer_ents)
        intra_rels = []
        for r in relationships:
            if r["from"] in layer_table_names and r["to"] in layer_table_names:
                intra_rels.append(f"  {r['from']} {r['rel_type']} {r['to']} : {r['label']}")
        
        if intra_rels:
            layer_lines.extend(intra_rels)
            
        final_sections.append("\n".join(layer_lines))

    # 2. Output cross-layer relationships
    cross_layer_rels = []
    for r in relationships:
        from_layer = get_layer_for_table(r["from"])
        to_layer = get_layer_for_table(r["to"])
        if from_layer != to_layer:
            if r["from"] in rendered_tables and r["to"] in rendered_tables:
                cross_layer_rels.append(f"  {r['from']} {r['rel_type']} {r['to']} : {r['label']}")

    # If no explicit relationships exist, infer them
    if not relationships and len(entities) > 1:
        ent_names = set(entities.keys())
        for ent, attrs in entities.items():
            for attr in attrs:
                parts = attr.split()
                if len(parts) >= 2:
                    col_name = parts[1].lower()
                    if col_name.endswith("_sk") and col_name != f"{ent.lower()}_sk":
                        target_cand = col_name[:-3].upper()
                        best_target = None
                        if target_cand in ent_names:
                            best_target = target_cand
                        else:
                            for candidate in ent_names:
                                if candidate.startswith(target_cand) or target_cand.startswith(candidate):
                                    best_target = candidate
                                    break
                        if best_target and best_target != ent:
                            rel_key = (best_target, ent)
                            if rel_key not in seen_rels:
                                seen_rels.add(rel_key)
                                cross_layer_rels.append(f"  {best_target} ||--o{{ {ent} : references")

    # Assembly Phase
    res = ["erDiagram"]
    for section in final_sections:
        res.append(section)
        
    if cross_layer_rels:
        res.append("\n  %% ─── CROSS-LAYER RELATIONSHIPS ───")
        res.extend(cross_layer_rels)
        
    return "\n".join(res)


def synthesize_erd_from_tables(tables: List[Dict], relationships: Optional[List[Dict]] = None) -> str:
    """
    Deterministically synthesises a complete erDiagram string from the merged schema
    tables list and (optionally) a relationships list.

    Generates the diagram layer by layer in distinct structured sections.
    """
    if not tables:
        return "erDiagram\n"

    # Map tables to their layers
    table_to_layer = {}
    for table in tables:
        if isinstance(table, dict) and table.get("name"):
            table_to_layer[_eid(table["name"])] = table.get("layer", "Warehouse")

    # Group tables by layer
    layer_groups = defaultdict(list)
    for table in tables:
        if not isinstance(table, dict):
            continue
        layer = table.get("layer", "Warehouse")
        layer_groups[layer].append(table)

    # Gather all relationships first
    all_rels = []
    seen_rels = set()

    # 1. From column refs
    for table in tables:
        if not isinstance(table, dict):
            continue
        src_name = table.get("name", "")
        src_eid = _eid(src_name)
        cols = table.get("columns", [])
        for col in (cols or []):
            if not isinstance(col, dict):
                continue
            ref = col.get("ref") or col.get("references")
            if ref and isinstance(ref, str) and "." in ref:
                target_table = ref.split(".")[0]
                tgt_eid = _eid(target_table)
                if src_eid and tgt_eid and src_eid != tgt_eid:
                    rel_key = (src_eid, tgt_eid)
                    rev_key = (tgt_eid, src_eid)
                    if rel_key not in seen_rels and rev_key not in seen_rels:
                        seen_rels.add(rel_key)
                        all_rels.append({
                            "from": tgt_eid,
                            "to": src_eid,
                            "cardinality": "||--o{",
                            "label": "references"
                        })

    # 2. From explicit relationships
    if relationships:
        for rel_item in relationships:
            if not isinstance(rel_item, dict):
                continue
            src_eid = _eid(rel_item.get("from_table") or rel_item.get("from") or "")
            tgt_eid = _eid(rel_item.get("to_table") or rel_item.get("to") or "")
            if not src_eid or not tgt_eid or src_eid == tgt_eid:
                continue
            rel_key = (src_eid, tgt_eid)
            rev_key = (tgt_eid, src_eid)
            if rel_key not in seen_rels and rev_key not in seen_rels:
                seen_rels.add(rel_key)
                cardinality = rel_item.get("cardinality", "||--o{")
                label_raw = rel_item.get("label", rel_item.get("c", "relates"))
                label = str(label_raw).replace('"', "").replace("'", "").replace(" ", "_") or "relates"
                all_rels.append({
                    "from": src_eid,
                    "to": tgt_eid,
                    "cardinality": cardinality,
                    "label": label
                })

    # Build layers incrementally
    final_sections = []
    cross_layer_rels = []

    # Sort layers
    sorted_layers = sorted(layer_groups.keys(), key=layer_sort_key)
    
    # Filter out Bronze / Raw / Landing layers if other warehouse layers exist
    warehouse_layers = [l for l in sorted_layers if l.lower() not in ["bronze", "raw", "landing", "ingest"]]
    target_layers = warehouse_layers if warehouse_layers else sorted_layers

    rendered_tables = set()
    for layer in target_layers:
        for table in layer_groups[layer]:
            rendered_tables.add(_eid(table.get("name", "")))

    for layer in target_layers:
        layer_tables = layer_groups[layer]
        layer_lines = []
        layer_lines.append(f"\n  %% ─── {layer.upper()} LAYER ───")
        
        # Add tables in this layer
        for table in layer_tables:
            ent = _eid(table.get("name", ""))
            if not ent or ent in ("ERDIAGRAM", "SELECT", "FROM", "WHERE"):
                continue
            cols = table.get("columns", [])
            layer_lines.append(f"  {ent} {{")
            if not cols:
                layer_lines.append(f"    int {ent.lower()}_sk PK")
            else:
                seen_col_names = set()
                for col in cols:
                    if not isinstance(col, dict):
                        continue
                    col_name = str(col.get("name", "")).strip()
                    if not col_name or col_name.lower() in seen_col_names:
                        continue
                    seen_col_names.add(col_name.lower())
                    col_type = normalize_attribute_type(col.get("type", "string"), col_name)
                    markers = []
                    if col.get("pk") or col.get("primary_key") or col.get("is_pk"):
                        markers.append("PK")
                    if col.get("fk") or col.get("is_fk"):
                        markers.append("FK")
                    marker_str = (" " + " ".join(markers)) if markers else ""
                    layer_lines.append(f"    {col_type} {col_name}{marker_str}")
            layer_lines.append("  }")

        # Add intra-layer relationships
        layer_table_names = { _eid(t.get("name", "")) for t in layer_tables }
        intra_rels = []
        for r in all_rels:
            if r["from"] in layer_table_names and r["to"] in layer_table_names:
                intra_rels.append(f"  {r['from']} {r['cardinality']} {r['to']} : {r['label']}")
        
        if intra_rels:
            layer_lines.extend(intra_rels)

        final_sections.append("\n".join(layer_lines))

    # Cross-layer relationships
    for r in all_rels:
        from_layer = get_layer_for_table(r["from"], table_to_layer)
        to_layer = get_layer_for_table(r["to"], table_to_layer)
        if from_layer != to_layer:
            if r["from"] in rendered_tables and r["to"] in rendered_tables:
                cross_layer_rels.append(f"  {r['from']} {r['cardinality']} {r['to']} : {r['label']}")

    # Combine everything
    output_lines = ["erDiagram"]
    for section in final_sections:
        output_lines.append(section)

    if cross_layer_rels:
        output_lines.append("\n  %% ─── CROSS-LAYER RELATIONSHIPS ───")
        output_lines.extend(cross_layer_rels)

    return "\n".join(output_lines)



def detect_truncation(mermaid: str) -> bool:
    """
    Heuristically detects whether a Mermaid diagram was truncated mid-generation.
    Returns True if the diagram appears incomplete (likely hit a token limit).
    
    Signals checked:
      1. Unbalanced curly braces { } — most reliable indicator for erDiagram blocks
      2. Diagram ends with a trailing comma, keyword, or open bracket
      3. erDiagram has entity blocks opened but never closed
    """
    if not mermaid or not mermaid.strip():
        return False
    
    text = mermaid.strip()
    
    # 1. Count unbalanced curly braces (entity blocks in erDiagram).
    # Important: erDiagram relationship cardinality markers (e.g. ||--o{ or }|) contain
    # literal { and } characters — strip relationship lines before counting so we
    # only count actual entity-block delimiters.
    lines_for_brace = [
        l for l in text.splitlines()
        if not re.search(r'[|o][|\-\.][|\-\.][|o{]', l)   # skip cardinality markers
    ]
    brace_text = '\n'.join(lines_for_brace)
    open_braces  = brace_text.count('{')
    close_braces = brace_text.count('}')
    if open_braces > close_braces:
        return True
    
    # 2. Check for dangling last line — truncation mid-token
    last_line = text.splitlines()[-1].strip() if text.splitlines() else ''
    dangling_patterns = [
        r',$',                     # trailing comma
        r':\s*$',                  # dangling colon (mid-relationship label)
        r'--\s*$',                 # partial arrow
        r'\|\s*$',                 # partial cardinality marker
        r'\b(int|string|float|date|timestamp|boolean)\s*$',  # type with no column name
    ]
    for pat in dangling_patterns:
        if re.search(pat, last_line, re.IGNORECASE):
            return True
    
    # 3. Flowchart: open subgraph with no matching 'end'
    subgraph_opens = len(re.findall(r'\bsubgraph\b', text, re.IGNORECASE))
    subgraph_ends  = len(re.findall(r'^\s*end\b', text, re.IGNORECASE | re.MULTILINE))
    if subgraph_opens > subgraph_ends:
        return True
    
    return False


def clean_mermaid_code(code: str, tab_route: Optional[str] = None) -> str:

    """
    Sanitizes Mermaid code by enforcing strict validation: only content that starts with valid 
    Mermaid keywords is sent to the engine. Any preceding plain text tab labels or UI headers 
    are stripped. Routes tabs correctly to ensure Schema only renders as erDiagram.
    """
    if not code: return ""
    
    # 1. Strip markdown wrappers
    code = re.sub(r'^```(?:mermaid)?\s*', '', code.strip(), flags=re.IGNORECASE)
    code = re.sub(r'\s*```$', '', code)
    
    lines = [l.strip() for l in code.split('\n')]
    valid_keywords = ['graph ', 'graph\n', 'flowchart ', 'flowchart\n', 'erdiagram', 'sequencediagram', 'classdiagram', 'gantt', 'pie']
    
    # Find the very first line that starts with a valid keyword
    start_idx = -1
    for i, line in enumerate(lines):
        l_low = line.lower()
        if any(l_low.startswith(kw) for kw in valid_keywords) or l_low == "graph" or l_low == "flowchart":
            start_idx = i
            break
            
    if start_idx == -1:
        # No valid graph syntax exists in this block.
        # If tab_route is schema, it MUST only render an erDiagram.
        if tab_route == "schema":
            return "erDiagram\n"
        # Otherwise, do not send raw plain text or UI labels to the renderer
        return ""
        
    # Extract only the valid diagram block
    diagram_lines = lines[start_idx:]
    diagram_str = "\n".join(diagram_lines)
    
    # If route is schema, enforce that it must be an erDiagram
    if tab_route == "schema" and "erdiagram" not in diagram_str.lower():
        return "erDiagram\n"
        
    return heal_mermaid_diagram(diagram_str)

def validate_modeling_rules(schema: Dict[str, Any], paradigm: str = "STAR_SCHEMA") -> List[str]:
    """
    Enforces industrial-grade DWH modeling rules based on the selected paradigm.
    """
    errors = []
    tables = schema.get("tables", [])
    relationships = schema.get("relationships", [])
    p = str(paradigm).upper()
    
    # Map table name to type and prefix
    table_types = {t.get("name"): t.get("type", "").lower() for t in tables}
    
    # 1. PARADIGM-SPECIFIC VALIDATION
    if p == "DATA_VAULT":
        # Data Vault Rules: Hubs, Links, Satellites
        for rel in relationships:
            src = rel.get("from_table") or rel.get("from", "").split(".")[0]
            tgt = rel.get("to_table") or rel.get("to", "").split(".")[0]
            
            # Satellites must only join to Hubs or Links
            if src.startswith("sat_") and not (tgt.startswith("hub_") or tgt.startswith("lnk_")):
                errors.append(f"DATA VAULT VIOLATION: Satellite {src} must join to a Hub or Link, not {tgt}.")
            # Hubs should not join directly to other Hubs
            if src.startswith("hub_") and tgt.startswith("hub_"):
                errors.append(f"DATA VAULT VIOLATION: Hub {src} cannot join directly to Hub {tgt}. Use a Link.")
        return errors # Data Vault has its own flow

    # 2. STANDARD DIMENSIONAL RULES (Star, Snowflake, Galaxy)
    for rel in relationships:
        source = rel.get("from_table") or rel.get("from", "").split(".")[0]
        target = rel.get("to_table") or rel.get("to", "").split(".")[0]
        src_type = table_types.get(source)
        tgt_type = table_types.get(target)

        # Relational Integrity Check (Cross-Paradigm)
        if src_type == "fact" and tgt_type == "fact" and p == "STAR_SCHEMA":
             # Optional: Allow transaction-to-transaction joins for non-Gold layers
             pass
            
    # 3. Column-level FK check
    for t in tables:
        t_name = t.get("name")
        for col in t.get("columns", []):
            if col.get("fk") is True:
                ref = col.get("ref")
                if not ref or "." not in str(ref):
                    errors.append(f"INVALID FK: Table {t_name} column {col.get('name')} lacks a valid 'ref' (table.column).")
                else:
                    ref_table = ref.split(".")[0]
                    if ref_table not in table_types and not any(t_name == ref_table for t_name in table_types):
                        # Relax check if the table might be in another layer (cross-layer ref)
                        pass
                        
    return errors
