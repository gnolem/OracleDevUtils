from dotenv import load_dotenv
import os
import oracledb
import platform
from typing import Optional, Dict, List
import logging

_oracle_client_initialized: bool = False
_initialization_error: Optional[Exception] = None

try:
    from .db_config import DEFAULT_TNS_ADMIN_DIR, DEFAULT_INSTANT_CLIENT_LIB_DIR
except ImportError:
     # Fallback for direct execution (less ideal)
    try:
        from db_config import DEFAULT_TNS_ADMIN_DIR, DEFAULT_INSTANT_CLIENT_LIB_DIR
    except ImportError:
         logging.error("Failed to import from db_config.")
         # Set fallbacks if import fails completely
         DEFAULT_TNS_ADMIN_DIR = None
         DEFAULT_INSTANT_CLIENT_LIB_DIR = None


# Configure logging for this module
log = logging.getLogger(__name__)

# Load environment variables from .env file as early as possible
# search_path ensures it looks in the current dir and parent dirs
dotenv_path = load_dotenv(override=True) # override=True allows env vars to take precedence
if dotenv_path:
    log.debug(f"Loaded environment variables from: {dotenv_path}")
else:
    log.debug("No .env file found or loaded.")


# Flag to ensure initialization happens only once per process
_oracle_client_initialized = False
_initialization_error: Optional[Exception] = None

def _find_existing_path(potential_paths: List[Optional[str]]) -> Optional[str]:
    """Helper to find the first existing directory path from a list."""
    for path in potential_paths:
        if path and os.path.isdir(path):
            log.debug(f"Found existing path: {path}")
            return path
    return None


def init_oracle_client_if_needed(force_reinit: bool = False) -> None:
    """
    Initializes the Oracle Client library and configuration directory if not already done.

    Reads ORACLE_LIB_DIR and TNS_ADMIN from environment variables first,
    then falls back to defaults defined in db_config.py.

    Args:
        force_reinit: If True, attempts initialization even if already done (use with caution).

    Raises:
        RuntimeError: If Oracle Client initialization fails fatally.
    """
    global _oracle_client_initialized, _initialization_error
    if _oracle_client_initialized and not force_reinit:
        log.debug("Oracle Client already initialized.")
        # Remove the re-raising of previous error here, let connect handle it if it matters
        return
    if _initialization_error and not force_reinit:
         raise RuntimeError("Oracle Client initialization previously failed.") from _initialization_error

    # Reset status if forcing reinitialization
    if force_reinit:
         _oracle_client_initialized = False
         _initialization_error = None
         log.info("Forcing reinitialization of Oracle Client.")

    try:
        # 1. Determine Oracle Client library directory (lib_dir)
        # Prefer environment variable, then default config, finally None (search PATH)
        env_lib_dir = os.getenv("ORACLE_LIB_DIR")
        lib_dir = _find_existing_path([env_lib_dir, DEFAULT_INSTANT_CLIENT_LIB_DIR])

        if env_lib_dir and not lib_dir:
             log.warning(f"ORACLE_LIB_DIR ('{env_lib_dir}') not found.")
        if not lib_dir:
            log.warning("Oracle Client library directory not found via ORACLE_LIB_DIR or default config. Relying on system PATH or existing OCI configuration.")
            # Let oracledb handle finding it via PATH or registry by passing lib_dir=None

        # 2. Determine TNS configuration directory (config_dir)
        # Prefer environment variable, then default config
        env_tns_admin = os.getenv("TNS_ADMIN")
        config_dir = _find_existing_path([env_tns_admin, DEFAULT_TNS_ADMIN_DIR])

        if env_tns_admin and not config_dir:
             log.warning(f"TNS_ADMIN directory ('{env_tns_admin}') not found.")
        if not config_dir:
             log.warning("Oracle TNS configuration directory (TNS_ADMIN) not found or not set. TNS aliases may not work unless configured elsewhere (e.g., registry).")
             # Proceed without config_dir, DSN connections might still work

        # 3. Attempt initialization
        log.info(f"Attempting Oracle Client initialization: lib_dir='{lib_dir or 'Default (PATH/Registry)'}', config_dir='{config_dir or 'Not Set'}'")
        oracledb.init_oracle_client(lib_dir=lib_dir, config_dir=config_dir)

        # --- Success ---
        _oracle_client_initialized = True
        _initialization_error = None
        log.info("Oracle Client initialized successfully.")

    except Exception as e:
        # --- Failure ---
        _initialization_error = e
        _oracle_client_initialized = False # Explicitly set to False on error
        log.exception("Failed to initialize Oracle Client.")
        # Re-raise immediately to signal critical failure
        # <<< THIS IS WHERE THE RUNTIMEERROR SHOULD BE RAISED >>>
        raise RuntimeError(f"Failed to initialize Oracle Client during attempt: {e}") from e


def get_connection_details() -> Dict[str, str]:
    """
    Retrieves database connection details (user, password, dsn) from environment variables.

    Prioritizes DB_TNS_ALIAS over DB_DSN if both are set.

    Returns:
        A dictionary containing 'user', 'password', and 'dsn'.

    Raises:
        ValueError: If required environment variables (DB_USER, DB_PASSWORD,
                    and either DB_TNS_ALIAS or DB_DSN) are not set or empty.
    """
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    tns_alias = os.getenv("DB_TNS_ALIAS")
    dsn = os.getenv("DB_DSN")

    # Validate required credentials
    if not user:
        raise ValueError("Missing required environment variable: DB_USER")
    if password is None: # Allow empty password if explicitly set, but not missing
         raise ValueError("Missing required environment variable: DB_PASSWORD (set to empty string if intended)")

    # Determine the connection string (DSN)
    # python-oracledb uses the TNS Alias directly as the dsn string
    # when config_dir is correctly set during init_oracle_client.
    connection_string = tns_alias if tns_alias else dsn

    if not connection_string:
        raise ValueError("Missing required environment variable: Set either DB_TNS_ALIAS or DB_DSN.")

    log.debug(f"Using connection details: User='{user}', DSN='{connection_string}' (Password=****)")
    return {"user": user, "password": password, "dsn": connection_string}


def connect(connection_details: Optional[Dict[str, str]] = None) -> Optional[oracledb.Connection]:
    """
    Establishes a connection to the Oracle database.

    Ensures Oracle client is initialized. Uses provided connection_details dictionary
    or retrieves them using get_connection_details() if not provided.

    Args:
        connection_details: Optional dictionary with 'user', 'password', 'dsn'.
                            If None, environment variables will be used.

    Returns:
        An active oracledb.Connection object, or None if initialization previously failed
        and cannot be retried.

    Raises:
        RuntimeError: If Oracle Client initialization fails during the attempt.
        ValueError: If connection details are missing or invalid.
        oracledb.DatabaseError: If the database connection attempt fails.
        Exception: For other unexpected errors during connection.
    """
    try:
        # Ensure client is initialized (or initialization error is handled)
        init_oracle_client_if_needed()

        # Get connection details if not provided
        if connection_details:
            conn_vars = connection_details
            log.debug("Using provided connection details.")
        else:
            log.debug("Retrieving connection details from environment.")
            conn_vars = get_connection_details() # Can raise ValueError

        # Validate retrieved/provided details
        if not conn_vars.get("user") or conn_vars.get("password") is None or not conn_vars.get("dsn"):
             raise ValueError("Invalid connection details provided: 'user', 'password', and 'dsn' are required.")

        log.info(f"Attempting to connect: User='{conn_vars['user']}', DSN='{conn_vars['dsn']}'")
        # Establish the connection
        # Consider adding connection pooling here if needed for performance
        connection = oracledb.connect(**conn_vars)
        log.info(f"Database connection successful. Oracle DB version: {connection.version}, Encoding: {connection.encoding}")
        # Optional: Set session parameters like NLS settings if needed
        # with connection.cursor() as cursor:
        #     cursor.execute("ALTER SESSION SET NLS_DATE_FORMAT = 'YYYY-MM-DD HH24:MI:SS'")
        #     cursor.execute("ALTER SESSION SET NLS_NUMERIC_CHARACTERS = '.,'")
        return connection

    except (ValueError, RuntimeError, oracledb.DatabaseError) as e:
        # Log specific known errors and re-raise them
        log.error(f"Failed to connect to database: {e}")
        raise e
    except Exception as e:
        # Catch any other unexpected exceptions during connection setup
        log.exception("An unexpected error occurred during database connection.")
        raise RuntimeError(f"Unexpected connection error: {e}") from e


# --- Example usage for testing within this module ---
def _main_test_connection():
    """Internal function for testing connection from main block."""
    print("\n--- Testing Database Connection (Module Level) ---")
    print("Attempting connection using environment variables / .env file...")

    conn: Optional[oracledb.Connection] = None
    try:
        # Attempt connection using the primary function
        conn = connect()

        if conn:
            print(f"Successfully connected!")
            print(f"  DB Version: {conn.version}")
            print(f"  Encoding:   {conn.encoding}")
            print(f"  Username:   {conn.username}")
            print(f"  DSN:        {conn.dsn}")

            # Perform a simple query
            with conn.cursor() as cursor:
                cursor.execute("SELECT sysdate, user, sys_context('USERENV', 'CURRENT_SCHEMA') FROM dual")
                db_time, db_user, current_schema = cursor.fetchone() # type: ignore
                print(f"  DB Time:       {db_time}")
                print(f"  DB User:       {db_user}")
                print(f"  Current Schema:{current_schema}")
        else:
            # This case should ideally not happen if connect() raises errors properly
             print("Connection attempt returned None unexpectedly.")

    except ValueError as ve:
        print(f"Connection Test FAILED: Configuration Error - {ve}")
    except RuntimeError as rte:
         print(f"Connection Test FAILED: Initialization Error - {rte}")
    except oracledb.DatabaseError as dbe:
        print(f"Connection Test FAILED: Database Error - {dbe}")
        # You can check specific ORA codes here, e.g., ORA-12154 (TNS), ORA-01017 (credentials)
    except Exception as ex:
        print(f"Connection Test FAILED: Unexpected Error - {ex}")
        import traceback
        traceback.print_exc() # Print full traceback for unexpected errors
    finally:
        if conn:
            try:
                conn.close()
                print("Database connection closed.")
            except Exception as close_ex:
                print(f"Error closing connection: {close_ex}")

if __name__ == "__main__":
    # Setup logging specifically for the __main__ block execution if desired
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')
    log.info("Running db_connection.py directly for testing.")
    _main_test_connection()