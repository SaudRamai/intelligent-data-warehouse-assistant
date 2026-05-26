import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

# Avoid encoding issues on Windows when printing unicode characters
sys.stdout.reconfigure(encoding='utf-8')

from dwh_assistant.backend.validator import (
    _eid,
    normalize_attribute_type,
    clean_mermaid_erd,
    synthesize_erd_from_tables
)

def run_tests():
    print("==================================================")
    print("RUNNING ERD & MERMAID VALIDATION TESTS")
    print("==================================================")

    # 1. Test _eid (Identifier Normalizer & Collapse Underscores)
    print("\n--- 1. Testing Identifier Sanitization (_eid) ---")
    test_cases_eid = [
        ("C___G_S", "C_G_S"),
        ("___G_S", "G_S"),
        ("customer___gold_serving_", "CUSTOMER_GOLD_SERVING"),
        ("dim_customers", "DIM_CUSTOMERS"),
        ("S", "S"),
        ("", "ENTITY")
    ]
    for raw, expected in test_cases_eid:
        res = _eid(raw)
        print(f"  _eid('{raw}') -> '{res}' | Expected: '{expected}' | {'PASS' if res == expected else 'FAIL'}")
        assert res == expected

    # 2. Test Data Type Normalizer
    print("\n--- 2. Testing Data Type Normalization ---")
    test_cases_types = [
        ("VARCHAR(50)", "customer_id", "string"),
        ("NUMBER(38,0)", "customer_sk", "int"),
        ("NUMBER(10,2)", "unit_price", "float"),
        ("VARIANT", "raw_payload", "string"),
        ("double precision", "amount", "float"),
        ("TIMESTAMP_NTZ", "created_at", "timestamp"),
        ("boolean", "is_active", "boolean")
    ]
    for t, col, expected in test_cases_types:
        res = normalize_attribute_type(t, col)
        print(f"  normalize('{t}', '{col}') -> '{res}' | Expected: '{expected}' | {'PASS' if res == expected else 'FAIL'}")
        assert res == expected

    # 3. Test clean_mermaid_erd (Messy Input Parsing & Layer Grouping)
    print("\n--- 3. Testing clean_mermaid_erd ---")
    messy_erd = """
    erDiagram
      BRONZE_RAW_CUSTOMERS {
        VARCHAR(50) customer_id
        NUMBER(38,0) customer_sk PK
        VARIANT payload
      }
      
      SILVER_DIM_CUSTOMERS {
        VARCHAR(50) customer_id
        INT customer_sk PK
      }

      GOLD_FACT_SALES {
        NUMBER(38,0) sales_sk PK
        NUMBER(38,0) customer_sk FK
        NUMBER(10,2) amount
      }

      GOLD_FACT_SALES }|..|| SILVER_DIM_CUSTOMERS : customer_sk
      SILVER_DIM_CUSTOMERS --> BRONZE_RAW_CUSTOMERS
    """
    
    cleaned = clean_mermaid_erd(messy_erd)
    print("Cleaned ERD:\n")
    print(cleaned)
    
    # Assertions
    assert "%% ─── BRONZE LAYER ───" not in cleaned
    assert "BRONZE_RAW_CUSTOMERS" not in cleaned
    assert "%% ─── SILVER LAYER ───" in cleaned
    assert "%% ─── GOLD LAYER ───" in cleaned
    assert "%% ─── CROSS-LAYER RELATIONSHIPS ───" not in cleaned  # no cross-layer rels left since bronze is excluded
    assert "VARCHAR(50)" not in cleaned
    assert "NUMBER" not in cleaned
    assert "VARIANT" not in cleaned
    assert "-->" not in cleaned
    print("  -> ERD parsing, sectioning, cleaning: PASS")

    # 4. Test synthesize_erd_from_tables
    print("\n--- 4. Testing synthesize_erd_from_tables ---")
    tables = [
        {
            "name": "BRONZE_RAW_CUSTOMERS",
            "layer": "Bronze",
            "columns": [
                {"name": "customer_id", "type": "VARCHAR(50)", "pk": False},
                {"name": "customer_sk", "type": "NUMBER(38,0)", "pk": True}
            ]
        },
        {
            "name": "SILVER_DIM_CUSTOMERS",
            "layer": "Silver",
            "columns": [
                {"name": "customer_id", "type": "VARCHAR(50)", "pk": False},
                {"name": "customer_sk", "type": "int", "pk": True}
            ]
        },
        {
            "name": "GOLD_FACT_SALES",
            "layer": "Gold",
            "columns": [
                {"name": "sales_sk", "type": "int", "pk": True},
                {"name": "customer_sk", "type": "int", "fk": True, "ref": "SILVER_DIM_CUSTOMERS.customer_sk"},
                {"name": "amount", "type": "float"}
            ]
        }
    ]
    
    synthesized = synthesize_erd_from_tables(tables)
    print("Synthesized ERD:\n")
    print(synthesized)
    
    assert "%% ─── BRONZE LAYER ───" not in synthesized
    assert "BRONZE_RAW_CUSTOMERS" not in synthesized
    assert "%% ─── SILVER LAYER ───" in synthesized
    assert "%% ─── GOLD LAYER ───" in synthesized
    assert "%% ─── CROSS-LAYER RELATIONSHIPS ───" in synthesized  # SILVER_DIM_CUSTOMERS to GOLD_FACT_SALES is cross-layer!
    assert "SILVER_DIM_CUSTOMERS ||--o{ GOLD_FACT_SALES" in synthesized or "GOLD_FACT_SALES }o--|| SILVER_DIM_CUSTOMERS" in synthesized or "SILVER_DIM_CUSTOMERS ||--o{ GOLD_FACT_SALES : references" in synthesized or "GOLD_FACT_SALES }o--|| SILVER_DIM_CUSTOMERS : references" in synthesized
    print("  -> ERD synthesis and layering: PASS")

    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
