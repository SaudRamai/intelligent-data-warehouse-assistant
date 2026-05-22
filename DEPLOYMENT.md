# Enterprise Deployment Guide: Intelligent Data Warehouse Assistant

This document provides a deep-dive, technical blueprint for deploying, configuring, and maintaining the Intelligent Data Warehouse Assistant.

---

## 1. High-Level System Architecture

The application is a state-of-the-art **AI Orchestrator** that bridges business requirements with technical Snowflake infrastructure.

### Technology Stack
*   **Application Framework**: Streamlit 1.32.0 (Multi-page Architecture)
*   **Data Processing**: Snowflake Snowpark for Python 1.18.0
*   **AI Engine**: Snowflake Cortex (Native Large Language Models)
*   **Visualization**: Mermaid.js & Streamlit Flow
*   **Styling**: Custom CSS (Outfit & JetBrains Mono typography)

---

## 2. Core Module Deep-Dive

### 2.1 Backend: Connection & Security (`snowflake_conn.py`)
The connection layer is designed for enterprise resilience, featuring an automated "Circuit Breaker."

*   **Session Management**: Uses `st.cache_resource` to persist the Snowpark session. It includes a heartbeat check (`SELECT 1`) to ensure the connection hasn't timed out.
*   **Circuit Breaker (Lockout Logic)**:
    *   **Trigger**: If an authentication error (Invalid Credentials, Account Locked) is detected, `_set_lockout()` writes a timestamped entry to `.streamlit/snowflake_lockout.json`.
    *   **Protection**: `_check_lockout()` blocks all subsequent login attempts for a 60-second cooldown period, preventing local brute-force or accidental account suspension by Snowflake.
*   **Auto-Provisioning**:
    *   `ensure_session()` automatically detects if the `ARCHITECTURE_STORE` database exists.
    *   If missing, it executes `setup.sql` to build the required persistence layer.
    *   It also attempts to grant the `SNOWFLAKE.CORTEX_USER` database role to the current active role.

### 2.2 AI Logic: Cortex Engine (`cortex_engine.py`)
This module handles the non-deterministic nature of LLMs with surgical precision.

*   **SQL Literal Construction**: Uses raw SQL `SELECT SNOWFLAKE.CORTEX.COMPLETE(...)` with dollar-sign quoting (`$$...$$`) to handle complex prompt characters safely.
*   **JSON Self-Healing**:
    *   `clean_json_string()`: Removes LLM-generated comments, fixes single-quote delimiters, and cleans trailing commas.
    *   `fix_truncated_json()`: A stack-based parser that automatically closes unclosed braces `{}` or brackets `[]` if the LLM output is cut off due to token limits.
*   **Model Fallback Strategy**: If the primary model (e.g., Claude 3.5 Sonnet) fails due to regional throughput limits, the engine automatically falls back to secondary models (Mixtral 8x7b, Llama 3.1 8b) to ensure service continuity.

### 2.3 Deployment Logic: Executor (`deploy_executor.py`)
Handles the transition from "Design" to "Live" with transactional-like safety.

*   **Atomic Execution**: Splinters the generated DDL SQL into individual statements and executes them sequentially.
*   **Rollback Engine**: If any statement fails, the `rollback()` function parses the previously executed statements. It identifies `CREATE TABLE` commands and issues `DROP TABLE IF EXISTS` commands to leave the Snowflake environment clean.
*   **Audit Logging**: Every deployment attempt (success or failure) is logged to the `DEPLOY_LOG` table with metadata on the failed statement and execution time.

---

## 3. Database Schema (`setup.sql`)

The persistence layer consists of two mission-critical tables:

### `PROJECTS` Table
Stores the entire state of the AI's architectural design.
*   **ID**: UUID string for unique project identification.
*   **REQUIREMENTS (VARIANT)**: Stores JSON from the Intake Form (Industry, Goals, KPIs).
*   **ARCHITECTURE / SCHEMA_DESIGN (VARIANT)**: Stores the AI-generated JSON blueprints.
*   **DDL_SQL (TEXT)**: The ready-to-execute SQL code.
*   **MERMAID_DIAGRAM (TEXT)**: The code used to render the visual architecture.

### `DEPLOY_LOG` Table
Audit trail for infrastructure changes.
*   **PROJECT_ID**: FK to the Projects table.
*   **STATEMENTS_RUN**: Count of successful SQL commands executed.
*   **STATUS**: 'success' or 'failed'.
*   **ERRORS (VARIANT)**: Detailed error messages if the deployment crashed.

---

## 4. UI/UX Design System (`styles.py`)

The application uses a **Premium Midnight Navy** design language.

*   **Typography**:
    *   `Outfit`: Used for all UI text, buttons, and headers for a modern, clean look.
    *   `JetBrains Mono`: Used for code blocks and technical output.
*   **Design Tokens**:
    *   `.glass-card`: Semi-transparent navy background (`rgba(0, 34, 68, 0.9)`) with backdrop blur.
    *   `.accent-text`: Sky blue (`#38BDF8`) for highlights.
    *   Custom Hover Effects: Buttons feature smooth transitions and subtle drop shadows.

---

## 5. Deployment Instructions

### Prerequisites
*   **Snowflake Account**: Region must support Cortex AI models.
*   **Network**: The host machine must have outbound access to Snowflake.
*   **Python**: Version 3.9 is mandated by the `environment.yml` specification.

### Installation
1.  **Environment Setup**:
    ```bash
    conda env create -f dwh_assistant/environment.yml
    conda activate dwh_assistant
    ```
2.  **Secrets Configuration**:
    Create `dwh_assistant/.streamlit/secrets.toml`:
    ```toml
    SNOWFLAKE_ACCOUNT = "..."
    SNOWFLAKE_USER = "..."
    SNOWFLAKE_PASSWORD = "..."
    SNOWFLAKE_ROLE = "ACCOUNTADMIN"
    SNOWFLAKE_WAREHOUSE = "COMPUTE_WH"
    ```
3.  **Launch**:
    ```bash
    python -m streamlit run dwh_assistant/app.py
    ```

---

## 6. Security Governance

*   **RBAC**: The user role must possess `CREATE DATABASE` and `CREATE SCHEMA` privileges on the account to allow the assistant to provision new environments.
*   **Data Privacy**: Profiling uses a configurable sampling depth (default 10 rows) to ensure minimal data exposure during the AI design phase.

---

*Document Revision: 2024.1 (Deep-Dive Edition)*
*Generated by Antigravity*
