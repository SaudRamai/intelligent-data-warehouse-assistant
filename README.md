# Intelligent Data Warehouse Assistant

This minimal repository is structured for developing a Streamlit application designed for deployment as a Snowflake Native App.

## Directory Structure

*   **`streamlit/app.py`**: The main Streamlit entry point. Contains the UI and interaction logic.
*   **`scripts/setup.sql`**: The setup script run by Snowflake when installing / upgrading the Native App package.
*   **`manifest.yml`**: Defines the Native App metadata, entry points, and required privileges.
*   **`environment.yml`**: Specifies the conda dependencies for the Streamlit environment within Snowflake.

## Deployment to Snowflake

To deploy this package, you will generally:

1. Upload the files (`manifest.yml`, `environment.yml`, `scripts/setup.sql`, `streamlit/app.py` and other python files) to a predefined stage in Snowflake.
2. Create an Application Package from the stage.
3. Create an Application instance from the Application Package.
