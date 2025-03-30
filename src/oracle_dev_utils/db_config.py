# FILE: C:\Users\tke\OracleDevUtils\src\oracle_dev_utils\db_config.py
import os
import logging

log = logging.getLogger(__name__)

# --- Configuration Constants ---

# Default Instant Client Path (used if ORACLE_LIB_DIR env var is not set)
# Adjust this path based on your typical installation location.
DEFAULT_INSTANT_CLIENT_LIB_DIR = r"C:\Oracle\instantclient_21_7" # Example path

# Default TNS_ADMIN Directory Path (used if TNS_ADMIN env var is not set)
# This should point to the *directory* containing tnsnames.ora and sqlnet.ora
# Option 1: Specify a fixed path (modify as needed)
# DEFAULT_TNS_ADMIN_DIR = r"C:\path\to\your\network\admin"
# Option 2: Try to derive from a known tnsnames.ora location (as in original)
# Be cautious with UNC paths (\...) if environment variables aren't used.
DEFAULT_TNSNAMES_PATH_EXAMPLE = r"\\office.ads\GLOBAL\APPLICATION\Oracle\tnsnames.ora"
try:
     # Ensure the directory containing the example tnsnames.ora exists before setting
     derived_tns_admin_dir = os.path.dirname(DEFAULT_TNSNAMES_PATH_EXAMPLE)
     if os.path.isdir(derived_tns_admin_dir):
          DEFAULT_TNS_ADMIN_DIR = derived_tns_admin_dir
          log.debug(f"Derived default TNS_ADMIN directory: {DEFAULT_TNS_ADMIN_DIR}")
     else:
          log.warning(f"Directory derived from DEFAULT_TNSNAMES_PATH_EXAMPLE ('{derived_tns_admin_dir}') does not exist. Default TNS_ADMIN not set this way.")
          DEFAULT_TNS_ADMIN_DIR = None
except Exception as e:
     log.warning(f"Could not determine default TNS_ADMIN directory from example path: {e}")
     DEFAULT_TNS_ADMIN_DIR = None


# You can add other database-related configuration constants here if needed.
# Example:
# DEFAULT_NLS_LANG = "AMERICAN_AMERICA.WE8MSWIN1252"