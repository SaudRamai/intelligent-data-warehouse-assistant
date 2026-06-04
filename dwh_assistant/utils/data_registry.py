# Centralized Data Registry for Templates and Samples
INDUSTRY_TEMPLATES = {
    "Retail": {
        "tables": [
            {
                "name": "CUSTOMERS", 
                "row_count": 15000,
                "columns": [
                    {"name": "CUSTOMER_ID", "type": "NUMBER", "nullable": False, "is_key": True},
                    {"name": "NAME", "type": "TEXT", "nullable": False},
                    {"name": "EMAIL", "type": "TEXT", "nullable": True, "is_pii": True},
                    {"name": "COUNTRY", "type": "TEXT", "nullable": True}
                ],
                "sample": []
            },
            {
                "name": "PRODUCTS", 
                "row_count": 1200,
                "columns": [
                    {"name": "PRODUCT_ID", "type": "NUMBER", "nullable": False, "is_key": True},
                    {"name": "NAME", "type": "TEXT", "nullable": False},
                    {"name": "CATEGORY", "type": "TEXT", "nullable": True},
                    {"name": "PRICE", "type": "NUMBER(10,2)", "nullable": False}
                ],
                "sample": []
            },
            {
                "name": "ORDERS", 
                "row_count": 85000,
                "columns": [
                    {"name": "ORDER_ID", "type": "NUMBER", "nullable": False, "is_key": True},
                    {"name": "CUSTOMER_ID", "type": "NUMBER", "nullable": False, "is_key": True},
                    {"name": "ORDER_DATE", "type": "DATE", "nullable": False},
                    {"name": "TOTAL_AMOUNT", "type": "NUMBER(12,2)", "nullable": False}
                ],
                "sample": []
            }
        ]
    },
    "Healthcare": {
        "tables": [
            {
                "name": "PATIENTS", 
                "row_count": 5000,
                "columns": [
                    {"name": "PATIENT_ID", "type": "NUMBER", "nullable": False, "is_key": True},
                    {"name": "NAME", "type": "TEXT", "nullable": False, "is_pii": True},
                    {"name": "DOB", "type": "DATE", "nullable": False, "is_pii": True},
                    {"name": "GENDER", "type": "TEXT", "nullable": True}
                ],
                "sample": []
            },
            {
                "name": "VISITS", 
                "row_count": 25000,
                "columns": [
                    {"name": "VISIT_ID", "type": "NUMBER", "nullable": False, "is_key": True},
                    {"name": "PATIENT_ID", "type": "NUMBER", "nullable": False, "is_key": True},
                    {"name": "VISIT_DATE", "type": "DATE", "nullable": False},
                    {"name": "DIAGNOSIS", "type": "TEXT", "nullable": True}
                ],
                "sample": []
            }
        ]
    },
    "Finance": {
        "tables": [
            {
                "name": "ACCOUNTS", 
                "row_count": 12000,
                "columns": [
                    {"name": "ACCOUNT_ID", "type": "NUMBER", "nullable": False, "is_key": True},
                    {"name": "HOLDER_NAME", "type": "TEXT", "nullable": False, "is_pii": True},
                    {"name": "TYPE", "type": "TEXT", "nullable": False},
                    {"name": "BALANCE", "type": "NUMBER(15,2)", "nullable": False}
                ],
                "sample": []
            },
            {
                "name": "TRANSACTIONS", 
                "row_count": 450000,
                "columns": [
                    {"name": "TX_ID", "type": "NUMBER", "nullable": False, "is_key": True},
                    {"name": "ACCOUNT_ID", "type": "NUMBER", "nullable": False, "is_key": True},
                    {"name": "TX_DATE", "type": "TIMESTAMP", "nullable": False},
                    {"name": "AMOUNT", "type": "NUMBER(12,2)", "nullable": False},
                    {"name": "TYPE", "type": "TEXT", "nullable": False}
                ],
                "sample": []
            }
        ]
    }
}

def get_template(industry: str):
    return INDUSTRY_TEMPLATES.get(industry, INDUSTRY_TEMPLATES["Retail"])

def get_tpch_sample_config(industry: str = None):
    return {
        "source_type": "Snowflake Sample Data",
        "database": "SNOWFLAKE_SAMPLE_DATA",
        "schema": "TPCH_SF1",
        "tables": ["CUSTOMER", "ORDERS", "LINEITEM", "PART", "SUPPLIER"]
    }
