import pytest
import os
import tempfile
import shutil
from pathlib import Path

# Example fixture to create temporary files for testing compilation/analysis
@pytest.fixture(scope="function") # 'function' scope runs setup/teardown for each test
def temp_sql_file():
    """Creates a temporary directory and provides a way to add files to it."""
    temp_dir = tempfile.mkdtemp(prefix="oracle_dev_utils_test_")
    print(f"\nCreated temp dir: {temp_dir}") # For debugging test runs

    def _create_file(filename: str, content: str, encoding='utf-8'):
        file_path = Path(temp_dir) / filename
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
        return str(file_path) # Return path as string, often easier for functions

    yield _create_file # The test function receives the _create_file helper

    # Teardown: Remove the temporary directory after the test function completes
    try:
        shutil.rmtree(temp_dir)
        print(f"\nRemoved temp dir: {temp_dir}") # For debugging test runs
    except Exception as e:
        print(f"Error removing temp dir {temp_dir}: {e}")


# Example fixture for managing database connections (more advanced)
# This would require careful handling of connection pooling or setup/teardown
# @pytest.fixture(scope="session") # 'session' scope runs once for all tests
# def db_connection():
#     """ Provides a database connection for tests that need it. """
#     from oracle_dev_utils.db_connection import connect, init_oracle_client_if_needed
#     conn = None
#     try:
#         print("\nSetting up database connection for test session...")
#         # Ensure .env is loaded and client initialized
#         init_oracle_client_if_needed()
#         conn = connect() # Assumes .env is configured correctly
#         print("Database connection established for tests.")
#         yield conn # Provide the connection to tests
#     except Exception as e:
#         pytest.fail(f"Failed to establish database connection for tests: {e}")
#     finally:
#         if conn:
#             try:
#                 conn.close()
#                 print("\nDatabase connection closed after test session.")
#             except Exception as e:
#                 print(f"Error closing test DB connection: {e}")