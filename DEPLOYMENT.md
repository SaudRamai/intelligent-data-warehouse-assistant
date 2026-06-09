# Enterprise Deployment Guide: Intelligent Data Warehouse Assistant

This document provides a deep-dive, technical blueprint for deploying, configuring, and maintaining the Intelligent Data Warehouse Assistant.

---

## 1. High-Level System Architecture

The application is a state-of-the-art **AI Orchestrator** that bridges business requirements with technical Snowflake infrastructure.

### Technology Stack
*   **Application Framework**: Streamlit (Multi-page Architecture)
*   **Data Processing**: Snowflake Snowpark for Python
*   **AI Engine**: Snowflake Cortex (Native Large Language Models)
*   **Visualization**: Mermaid.js & SVG Pan Zoom
*   **Document Generation**: ReportLab (PDF) & python-docx (DOCX)
*   **Styling**: Custom CSS (Outfit typography, Glassmorphism)

---

## 2. Core Module Deep-Dive

### 2.1 Backend: Connection & Security (`dwh_assistant/backend/snowflake.py`)
The connection layer is designed for enterprise resilience, featuring an automated "Circuit Breaker."

*   **Session Management**: Uses `st.cache_resource` to persist the Snowpark session. It includes a heartbeat check (`SELECT 1`) to ensure the connection hasn't timed out.
*   **Circuit Breaker (Lockout Logic)**:
    *   **Trigger**: If an authentication error is detected, it writes a timestamped entry to `.streamlit/snowflake_lockout.json`.
    *   **Protection**: Blocks all subsequent login attempts for a 60-second cooldown period, preventing local brute-force or accidental account suspension by Snowflake.
*   **Auto-Provisioning**:
    *   `ensure_session()` automatically detects if the `ARCHITECTURE_STORE` database exists.
    *   If missing, it automatically creates the required schemas and tables to build the persistence layer.

### 2.2 AI Logic: Cortex Engine (`dwh_assistant/backend/executor.py` & `prompts.py`)
This module handles the non-deterministic nature of LLMs with surgical precision.

*   **JSON Self-Healing & Escaping**:
    *   `clean_json_string()`: Removes LLM-generated comments, fixes single-quote delimiters, and cleans trailing commas.
    *   `fix_truncated_json()`: A stack-based parser that automatically closes unclosed braces `{}` or brackets `[]`.
    *   `keys_to_repair`: A dedicated regex repair tool that automatically patches double-escaped strings (`\\n`, `\\"`) injected by Snowflake Cortex APIs into nested JSON structures (like table `headers` and `rows`).
*   **Auto-Continuation**: `call_cortex_with_continuation()` automatically detects truncated payloads (due to the 8192 token limit) and streams the remainder natively, stitching it seamlessly back into the JSON AST.

### 2.3 Document Generation & Export (`dwh_assistant/utils/doc_generator.py` & `doc_export.py`)
Engineered to bypass hard token limits and render enterprise-grade deliverables.

*   **Chunked Generation (`doc_generator.py`)**: Slices massive 16-section technical documents into batches of 2 or 4 sections. This orchestrates multiple sequential Cortex calls to keep output payloads comfortably under the 8192 token limit, merging the results into a single comprehensive JSON blueprint.
*   **Robust PDF Rendering (`doc_export.py`)**: Uses `ReportLab` (Platypus) to build boardroom-ready PDFs.
    *   **Dynamic Table Scaling**: Automatically scales down font sizes, leading, and padding for massive technical tables (e.g., 9-column Source-to-Target mapping).
    *   **Proportional Column Widths**: Analyzes string lengths to allocate table column widths dynamically, preventing layout crashes (`LayoutError`) caused by overly aggressive CJK word wrapping.
*   **DOCX Support**: Provides drop-in `.docx` generation via `python-docx` using corporate styled headers, tables, and paragraphs.

### 2.4 Orchestration & UI (`dwh_assistant/backend/orchestrator.py` & `pages/`)
Handles the transition from "Design" to "Live" with transactional-like safety.

*   **Multi-Page Application**: The application flow is broken into Intake Form, Data Profile, AI Generation, Design Center, and Deliverables Documents.
*   **Component Architecture**: UI components and CSS are organized within `dwh_assistant/components/` (e.g., `mermaid_renderer.py`, `styles.py`).

---

## 3. Database Schema

The persistence layer consists of two mission-critical tables created automatically:

### `PROJECTS` Table
Stores the entire state of the AI's architectural design.
*   **ID**: UUID string for unique project identification.
*   **REQUIREMENTS (VARIANT)**: Stores JSON from the Intake Form (Industry, Goals, KPIs).
*   **ARCHITECTURE / SCHEMA_DESIGN (VARIANT)**: Stores the AI-generated JSON blueprints.
*   **DDL_SQL (TEXT)**: The ready-to-execute SQL code.
*   **DOCUMENTATION (TEXT)**: Stores the JSON payload of the generated Proposal and Technical Design Documents.
*   **MERMAID_DIAGRAM (TEXT)**: Stores the visual entity-relationship diagram logic.

### `DEPLOY_LOG` Table
Audit trail for infrastructure changes.
*   **PROJECT_ID**: FK to the Projects table.
*   **STATEMENTS_RUN**: Count of successful SQL commands executed.
*   **STATUS**: 'success' or 'failed'.
*   **ERRORS (VARIANT)**: Detailed error messages if the deployment crashed.

---

## 4. UI/UX Design System (`dwh_assistant/components/styles.py`)

The application uses a **Premium Midnight Navy** design language.

*   **Typography**:
    *   `Outfit`: Used for all UI text, buttons, and headers for a modern, clean look.
*   **Design Tokens**:
    *   `.glass-card`: Semi-transparent navy background (`rgba(0, 34, 68, 0.9)`) with backdrop blur.
    *   `.accent-text`: Sky blue (`#38BDF8`) for highlights.

---

## 5. Deployment Instructions

### Prerequisites
*   **Snowflake Account**: Region must support Cortex AI models.
*   **Network**: The host machine must have outbound access to Snowflake.

### Installation
1.  **Secrets Configuration**:
    Create `.streamlit/secrets.toml`:
    ```toml
    [connections.snowflake]
    account = "..."
    user = "..."
    password = "..."
    role = "ACCOUNTADMIN"
    warehouse = "COMPUTE_WH"
    ```
2.  **Launch**:
    ```bash
    python -m streamlit run streamlit_app.py
    ```

---

## 6. Security Governance

*   **RBAC**: The user role must possess `CREATE DATABASE` and `CREATE SCHEMA` privileges on the account to allow the assistant to provision new environments.
*   **Data Privacy**: Profiling uses a configurable sampling depth to ensure minimal data exposure during the AI design phase.

---

*Document Revision: 2024.1 (Deep-Dive Edition)*
*Generated by Antigravity*
