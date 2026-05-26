import sys
import re
import json

raw_text = '{\n  "choices": [\n    {\n      "messages": "{\\n  \\"mermaid_diagram\\": \\"erDiagram\\\\n\\\\n  %% ─── BRONZE LAYER ───\\\\n  BRONZE_RAW_CUSTOMERS {\\\\n    VARCHAR customer_sk PK\\\\n    VARCHAR customer_id\\\\n    VARCHAR company_name\\\\n    VARCHAR contact_name\\\\n    VARCHAR contact_title\\\\n    VARCHAR address\\\\n    VARCHAR city\\\\n    VARCHAR region\\\\n    VARCHAR postal_code\\\\n    VARCHAR country\\\\n    VARCHAR phone\\\\n    VARCHAR fax\\\\n  }\\\\n  BRONZE_RAW_EMPLOYEES {\\\\n    VARCHAR employee_sk PK\\\\n    VARCHAR employee_id\\\\n    VARCHAR last_name\\\\n    VARCHAR first_name\\\\n    VARCHAR title\\\\n    VARCHAR title_of_courtesy\\\\n    VARCHAR birth_date\\\\n    VARCHAR hire_date\\\\n    VARCHAR address\\\\n    VARCHAR city\\\\n    VARCHAR region\\\\n    VARCHAR postal_code\\\\n    VARCHAR country\\\\n    VARCHAR home_phone\\\\n    VARCHAR extension\\\\n    VARCHAR photo\\\\n    VARCHAR notes\\\\n    VARCHAR reports_to\\\\n    VARCHAR photo_path\\\\n  }\\\\n  BRONZE_RAW_ORDERS {\\\\n    VARCHAR order_sk PK\\\\n    VARCHAR order_id\\\\n    VARCHAR customer_id\\\\n    VARCHAR employee_id\\\\n    VARCHAR order_date\\\\n    VARCHAR required_date\\\\n    VARCHAR shipped_date\\\\n    VARCHAR ship_via\\\\n    VARCHAR freight\\\\n    VARCHAR ship_name\\\\n    VARCHAR ship_address\\\\n    VARCHAR ship_city\\\\n    VARCHAR ship_region\\\\n    VARCHAR ship_postal_code\\\\n    VARCHAR ship_country\\\\n  }\\\\n  BRONZE_RAW_ORDER_DETAILS {\\\\n    VARCHAR order_detail_sk PK\\\\n    VARCHAR order_id\\\\n    VARCHAR product_id\\\\n    VARCHAR unit_price\\\\n    VARCHAR quantity\\\\n    VARCHAR discount\\\\n  }\\\\n  BRONZE_RAW_PRODUCTS {\\\\n    VARCHAR product_sk PK\\\\n    VARCHAR product_id\\\\n    VARCHAR product_name\\\\n    VARCHAR supplier_id\\\\n    VARCHAR category_id\\\\n    VARCHAR quantity_per_unit\\\\n    VARCHAR unit_price\\\\n    VARCHAR units_in_stock\\\\n    VARCHAR units_on_order\\\\n    VARCHAR reorder_level\\\\n    VARCHAR discontinued\\\\n  }\\\\n  BRONZE_RAW_SUPPLIERS {\\\\n    VARCHAR supplier_sk PK\\\\n    VARCHAR supplier_id\\\\n    VARCHAR company_name\\\\n    VARCHAR contact_name\\\\n    VARCHAR contact_title\\\\n    VARCHAR address\\\\n    VARCHAR city\\\\n    VARCHAR region\\\\n    VARCHAR postal_code\\\\n    VARCHAR country\\\\n    VARCHAR phone\\\\n    VARCHAR fax\\\\n    VARCHAR home_page\\\\n  }\\\\n  BRONZE_RAW_CATEGORIES {\\\\n    VARCHAR category_sk PK\\\\n    VARCHAR category_id\\\\n    VARCHAR category_name\\\\n    VARCHAR description\\\\n    VARCHAR picture\\\\n  }\\\\n  BRONZE_RAW_SHIPPERS {\\\\n    VARCHAR shipper_sk PK\\\\n    VARCHAR shipper_id\\\\n    VARCHAR company_name\\\\n    VARCHAR phone\\\\n  }\\\\n\\\\n  %% ─── SILVER LAYER ───\\\\n  SILVER_DIM_CUSTOMERS {\\\\n    INT customer_sk PK\\\\n    VARCHAR customer_id\\\\n    VARCHAR company_name\\\\n    VARCHAR contact_name\\\\n    VARCHAR contact_title\\\\n    VARCHAR address\\\\n    VARCHAR city\\\\n    VARCHAR region\\\\n    VARCHAR postal_code\\\\n    VARCHAR country\\\\n    VARCHAR phone\\\\n    VARCHAR fax\\\\n  }\\\\n  SILVER_DIM_EMPLOYEES {\\\\n    INT employee_sk PK\\\\n    VARCHAR employee_id\\\\n    VARCHAR last_name\\\\n    VARCHAR first_name\\\\n    VARCHAR title\\\\n    VARCHAR title_of_courtesy\\\\n    DATE birth_date\\\\n    DATE hire_date\\\\n    VARCHAR address\\\\n    VARCHAR city\\\\n    VARCHAR region\\\\n    VARCHAR postal_code\\\\n    VARCHAR country\\\\n    VARCHAR home_phone\\\\n    VARCHAR extension\\\\n    VARCHAR photo\\\\n    VARCHAR notes\\\\n    INT reports_to_sk\\\\n    VARCHAR photo_path\\\\n  }\\\\n  SILVER_DIM_PRODUCTS {\\\\n    INT product_sk PK\\\\n    VARCHAR product_id\\\\n    VARCHAR product_name\\\\n    INT supplier_sk\\\\n    INT category_sk\\\\n    VARCHAR quantity_per_unit\\\\n    FLOAT unit_price\\\\n    INT units_in_stock\\\\n    INT units_on_order\\\\n    INT reorder_level\\\\n    BOOLEAN discontinued\\\\n  }\\\\n  SILVER_DIM_SUPPLIERS {\\\\n    INT supplier_sk PK\\\\n    VARCHAR supplier_id\\\\n    VARCHAR company_name\\\\n    VARCHAR contact_name\\\\n    VARCHAR contact_title\\\\n    VARCHAR address\\\\n    VARCHAR city\\\\n    VARCHAR region\\\\n    VARCHAR postal_code\\\\n    VARCHAR country\\\\n    VARCHAR phone\\\\n    VARCHAR fax\\\\n    VARCHAR home_page\\\\n  }\\\\n  SILVER_DIM_CATEGORIES {\\\\n    INT category_sk PK\\\\n    VARCHAR category_id\\\\n    VARCHAR category_name\\\\n    VARCHAR description\\\\n    VARCHAR picture\\\\n  }\\\\n  SILVER_DIM_SHIPPERS {\\\\n    INT shipper_sk PK\\\\n    VARCHAR shipper_id\\\\n    VARCHAR company_name\\\\n    VARCHAR phone\\\\n  }\\\\n  SILVER_DIM_DATE {\\\\n    INT date_sk PK\\\\n    DATE full_date\\\\n    INT year\\\\n    INT month\\\\n    VARCHAR month_name\\\\n    INT day\\\\n    INT day_of_week\\\\n    VARCHAR day_name\\\\n    BOOLEAN is_weekend\\\\n  }\\\\n  SILVER_FACT_ORDERS {\\\\n    INT order_sk PK\\\\n    VARCHAR order_id\\\\n    INT customer_sk\\\\n    INT employee_sk\\\\n    INT order_date_sk\\\\n    INT required_date_sk\\\\n    INT shipped_date_sk\\\\n    INT ship_via_sk\\\\n    FLOAT freight\\\\n    VARCHAR ship_name\\\\n    VARCHAR ship_address\\\\n    VARCHAR ship_city\\\\n    VARCHAR ship_region\\\\n    VARCHAR ship_postal_code\\\\n    VARCHAR ship_country\\\\n  }\\\\n  SILVER_FACT_ORDER_DETAILS {\\\\n    INT order_detail_sk PK\\\\n    INT order_sk\\\\n    INT product_sk\\\\n    FLOAT unit_price\\\\n    INT quantity\\\\n    FLOAT discount\\\\n  }\\\\n\\\\n  %% ─── GOLD LAYER ───\\\\n  GOLD_DIM_CUSTOMERS {\\\\n    INT customer_sk PK\\\\n    VARCHAR customer_id\\\\n    VARCHAR company_name\\\\n    VARCHAR contact_name\\\\n    VARCHAR contact_title\\\\n    VARCHAR address\\\\n    VARCHAR city\\\\n    VARCHAR region\\\\n    VARCHAR postal_code\\\\n    VARCHAR country\\\\n    VARCHAR phone\\\\n    VARCHAR fax\\\\n  }\\\\n  GOLD_DIM_EMPLOYEES {\\\\n    INT employee_sk PK\\\\n    VARCHAR employee_id\\\\n    VARCHAR last_name\\\\n    VARCHAR first_name\\\\n    VARCHAR title\\\\n    VARCHAR title_of_courtesy\\\\n    DATE birth_date\\\\n    DATE hire_date\\\\n    VARCHAR address\\\\n    VARCHAR city\\\\n    VARCHAR region\\\\n    VARCHAR postal_code\\\\n    VARCHAR country\\\\n    VARCHAR home_phone\\\\n    VARCHAR extension\\\\n    VARCHAR photo\\\\n    VARCHAR notes\\\\n    INT reports_to_sk\\\\n    VARCHAR photo_path\\\\n  }\\\\n  GOLD_DIM_PRODUCTS {\\\\n    INT product_sk PK\\\\n    VARCHAR product_id\\\\n    VARCHAR product_name\\\\n    INT supplier_sk\\\\n    INT category_sk\\\\n    VARCHAR quantity_per_unit\\\\n    FLOAT unit_price\\\\n    INT units_in_stock\\\\n    INT units_on_order\\\\n    INT reorder_level\\\\n    BOOLEAN discontinued\\\\n  }\\\\n  GOLD_DIM_DATE {\\\\n    INT date_sk PK\\\\n    DATE full_date\\\\n    INT year\\\\n    INT month\\\\n    VARCHAR month_name\\\\n    INT day\\\\n    INT day_of_week\\\\n    VARCHAR day_name\\\\n    BOOLEAN is_weekend\\\\n  }\\\\n  GOLD_FACT_SALES {\\\\n    INT sales_sk PK\\\\n    INT order_sk\\\\n    INT customer_sk\\\\n    INT employee_sk\\\\n    INT order_date_sk\\\\n    INT product_sk\\\\n    INT shipper_sk\\\\n    FLOAT unit_price\\\\n    INT quantity\\\\n    FLOAT discount\\\\n    FLOAT gross_amount\\\\n    FLOAT net_amount\\\\n  }\\\\n\\\\n  %% ─── RELATIONSHIPS ───\\\\n  SILVER_FACT_ORDERS }|..|| SILVER_DIM_CUSTOMERS : customer_sk\\\\n  SILVER_FACT_ORDERS }|..|| SILVER_DIM_EMPLOYEES : employee_sk\\\\n  SILVER_FACT_ORDERS }|..|| SILVER_DIM_DATE : order_date_sk\\\\n  SILVER_FACT_ORDERS }|..|| SILVER_DIM_DATE : required_date_sk\\\\n  SILVER_FACT_ORDERS }|..|| SILVER_DIM_DATE : shipped_date_sk\\\\n  SILVER_FACT_ORDERS }|..|| SILVER_DIM_SHIPPERS : ship_via_sk\\\\n  SILVER_FACT_ORDER_DETAILS }|..|| SILVER_FACT_ORDERS : order_sk\\\\n  SILVER_FACT_ORDER_DETAILS }|..|| SILVER_DIM_PRODUCTS : product_sk\\\\n  SILVER_DIM_PRODUCTS }|..|| SILVER_DIM_SUPPLIERS : supplier_sk\\\\n  SILVER_DIM_PRODUCTS }|..|| SILVER_DIM_CATEGORIES : category_sk\\\\n  GOLD_FACT_SALES }|..|| GOLD_DIM_CUSTOMERS : customer_sk\\\\n  GOLD_FACT_SALES }|..|| GOLD_DIM_EMPLOYEES : employee_sk\\\\n  GOLD_FACT_SALES }|..|| GOLD_DIM_DATE : order_date_sk\\\\n  GOLD_FACT_SALES }|..|| GOLD_DIM_PRODUCTS : product_sk\\\\n  GOLD_FACT_SALES }|..|| GOLD_DIM_EMPLOYEES : shipper_sk\\\\n  BRONZE_RAW_ORDERS }|..|| BRONZE_RAW_CUSTOMERS : customer_id\\\\n  BRONZE_RAW_ORDERS }|..|| BRONZE_RAW_EMPLOYEES : employee_id\\\\n  BRONZE_RAW_ORDER_DETAILS }|..|| BRONZE_RAW_ORDERS : order_id\\\\n  BRONZE_RAW_ORDER_DETAILS }|..|| BRONZE_RAW_PRODUCTS : product_id\\\\n  BRONZE_RAW_PRODUCTS }|..|| BRONZE_RAW_SUPPLIERS : supplier_id\\\\n  BRONZE_RAW_PRODUCTS }|..|| BRONZE_RAW_CATEGORIES : category_id\\\\n  BRONZE_RAW_ORDERS }|..|| BRONZE_RAW_SHIPPERS : ship_via\\\\n  \\\\",\n  \\"tables\\": [\\n    {\\n      \\"name\\": \\"BRONZE_RAW_CUSTOMERS\\",\\n      \\"layer\\": \\"Bronze\\",\\n      \\"description\\": \\"Raw customers data\\",\\n      \\"columns\\": [\\n        {\\"name\\": \\"customer_sk\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": true, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"customer_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"company_name\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"contact_name\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"contact_title\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"address\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"city\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"region\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"postal_code\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"country\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"phone\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"fax\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null}\\n      ]\\n    },\\n    {\\n      \\"name\\": \\"BRONZE_RAW_EMPLOYEES\\",\\n      \\"layer\\": \\"Bronze\\",\\n      \\"description\\": \\"Raw employees data\\",\\n      \\"columns\\": [\\n        {\\"name\\": \\"employee_sk\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": true, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"employee_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"last_name\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"first_name\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"title\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"title_of_courtesy\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"birth_date\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"hire_date\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"address\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"city\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"region\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"postal_code\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"country\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"home_phone\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"extension\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"photo\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"notes\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"reports_to\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"photo_path\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null}\\n      ]\\n    },\\n    {\\n      \\"name\\": \\"BRONZE_RAW_ORDERS\\",\\n      \\"layer\\": \\"Bronze\\",\\n      \\"description\\": \\"Raw orders data\\",\\n      \\"columns\\": [\\n        {\\"name\\": \\"order_sk\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": true, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"order_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"customer_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": true, \\"ref\\": \\"BRONZE_RAW_CUSTOMERS.customer_id\\"},\\n        {\\"name\\": \\"employee_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": true, \\"ref\\": \\"BRONZE_RAW_EMPLOYEES.employee_id\\"},\\n        {\\"name\\": \\"order_date\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"required_date\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"shipped_date\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"ship_via\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": true, \\"ref\\": \\"BRONZE_RAW_SHIPPERS.shipper_id\\"},\\n        {\\"name\\": \\"freight\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"ship_name\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"ship_address\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"ship_city\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"ship_region\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"ship_postal_code\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"ship_country\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null}\\n      ]\\n    },\\n    {\\n      \\"name\\": \\"BRONZE_RAW_ORDER_DETAILS\\",\\n      \\"layer\\": \\"Bronze\\",\\n      \\"description\\": \\"Raw order details data\\",\\n      \\"columns\\": [\\n        {\\"name\\": \\"order_detail_sk\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": true, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"order_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": true, \\"ref\\": \\"BRONZE_RAW_ORDERS.order_id\\"},\\n        {\\"name\\": \\"product_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": true, \\"ref\\": \\"BRONZE_RAW_PRODUCTS.product_id\\"},\\n        {\\"name\\": \\"unit_price\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"quantity\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"discount\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null}\\n      ]\\n    },\\n    {\\n      \\"name\\": \\"BRONZE_RAW_PRODUCTS\\",\\n      \\"layer\\": \\"Bronze\\",\\n      \\"description\\": \\"Raw products data\\",\\n      \\"columns\\": [\\n        {\\"name\\": \\"product_sk\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": true, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"product_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"product_name\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"supplier_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": true, \\"ref\\": \\"BRONZE_RAW_SUPPLIERS.supplier_id\\"},\\n        {\\"name\\": \\"category_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": true, \\"ref\\": \\"BRONZE_RAW_CATEGORIES.category_id\\"},\\n        {\\"name\\": \\"quantity_per_unit\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"unit_price\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"units_in_stock\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"units_on_order\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"reorder_level\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"discontinued\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null}\\n      ]\\n    },\\n    {\\n      \\"name\\": \\"BRONZE_RAW_SUPPLIERS\\",\\n      \\"layer\\": \\"Bronze\\",\\n      \\"description\\": \\"Raw suppliers data\\",\\n      \\"columns\\": [\\n        {\\"name\\": \\"supplier_sk\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": true, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"supplier_id\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"company_name\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"contact_name\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"contact_title\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"address\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"city\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"region\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"postal_code\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"country\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"phone\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"fax\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null},\\n        {\\"name\\": \\"home_page\\", \\"type\\": \\"VARCHAR\\", \\"pk\\": false, \\"fk\\": false, \\"ref\\": null}\\n      ]\\n    }'

# --- Ripped functions from validator.py to match exact runtime behavior ---
def clean_json_string(s: str) -> str:
    if not s: return s
    s = re.sub(r'^```(?:json)?\s*', '', s.strip(), flags=re.IGNORECASE)
    s = re.sub(r'\s*```$', '', s)
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

def unescape_json_string(s: str) -> str:
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

# Let's run the logic
print("--- TEST RUN WITH EXECUTOR.EXTRACT_JSON ---")
import sys
sys.path.insert(0, 'c:/Users/ramai.saud/intelligent-data-warehouse-assistant')
from dwh_assistant.backend.executor import extract_json

try:
    parsed = extract_json(raw_text)
    print("Parsed successfully via executor.extract_json! Keys:", list(parsed.keys()))
except Exception as e:
    print("PARSE FAILED WITH ERROR:", e)
