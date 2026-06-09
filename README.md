# Intelligent Data Warehouse Assistant

An enterprise-grade, multi-page Streamlit application that acts as an AI Orchestrator to bridge business requirements with technical Snowflake infrastructure. The application uses Snowflake Cortex native LLMs to automatically architect, design, and generate deployment code for data warehouse environments.

## Directory Structure

*   **`streamlit_app.py`**: The main entry point for the application. Sets up the environment and routing.
*   **`pages/`**: Contains the multi-page Streamlit workflows:
    *   `1_Intake_Form.py`: Captures business requirements and KPIs.
    *   `2_Data_Profile.py`: Connects to source databases to profile existing data.
    *   `3_AI_Generation.py`: Interfaces with Snowflake Cortex to generate the architecture blueprint.
    *   `4_Design_Center.py`: Interactive review and editing of generated schemas, pipelines, and DDLs using Mermaid.js and code editors.
    *   `5_Deliverables_Documents.py`: Enterprise document generator for crafting client-ready Proposals and Technical Design Documents.
*   **`dwh_assistant/`**: The core application logic.
    *   `backend/`: Snowflake connection logic, executor for LLM payload extraction, and prompt definitions.
    *   `components/`: Reusable Streamlit components like the interactive Mermaid renderer and CSS stylesheets.
    *   `utils/`: Helper utilities, including robust `doc_generator.py` for chunked LLM execution and `doc_export.py` for PDF/DOCX rendering.
*   **`.streamlit/`**: Contains the `secrets.toml` file for secure Snowflake connection settings.

## Getting Started

1. Set up your `.streamlit/secrets.toml` with your Snowflake connection details:
```toml
[connections.snowflake]
account = "your_account_locator"
user = "your_username"
password = "your_password"
role = "ACCOUNTADMIN"
warehouse = "COMPUTE_WH"
```

2. Run the application locally:
```bash
python -m streamlit run streamlit_app.py
```

Please see `DEPLOYMENT.md` for a comprehensive overview of the system architecture and Snowflake dependencies.
