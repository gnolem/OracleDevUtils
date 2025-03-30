# FILE: C:\Users\tke\OracleDevUtils\src\oracle_dev_utils\compiler.py
import os
import oracledb
import re
import logging
from typing import Dict, List, Any, Optional

# Use relative import within the package
try:
    from .db_connection import connect
except ImportError:
    # Fallback for direct execution (less ideal)
    try:
        from db_connection import connect
    except ImportError:
         logging.error("Failed to import 'connect' from db_connection. Ensure db_connection.py is accessible.")
         connect = None # type: ignore

# Configure logging for this module
log = logging.getLogger(__name__)

# Regex to capture object type and name (handles schema, quotes, various types)
# Group 1: Object Type (PACKAGE, FUNCTION, VIEW, etc.)
# Group 2: Schema (Optional)
# Group 3: Object Name
OBJECT_NAME_REGEX = re.compile(
    r"""
    ^\s*CREATE(?:\s+OR\s+REPLACE)?\s+
    (?:NONEDITIONABLE\s+)?
    ( # Group 1: Object Type Keyword(s)
      (?:PACKAGE|TYPE)\s+BODY
      |
      PUBLIC\s+SYNONYM # PUBLIC SYNONYM handled explicitly first
      |
      PACKAGE|FUNCTION|PROCEDURE|TYPE|VIEW|TRIGGER|SEQUENCE|MATERIALIZED\s+VIEW|SYNONYM # Regular types
    )
    \s+
    # Optional Schema (Group 2) - Not typically used with PUBLIC SYNONYM, but pattern allows it
    (?:
        (?:\"?([a-zA-Z0-9_$#]+)\"?) # Schema name
        \.
    )?
    # Object Name (Group 3)
    \"?([a-zA-Z0-9_$#]+)\"? # Object name
    # Optional rest of synonym: FOR schema.object
    (?:\s+FOR\s+.*)? # Non-capturing group for the rest, allows match
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE
)


def extract_object_name_from_code(plsql_code: str, file_path: str) -> Optional[str]:
    """
    Extracts the database object name from PL/SQL/SQL code using regex.
    Falls back to filename if regex fails.

    Args:
        plsql_code: The source code as a string.
        file_path: The path to the source file (used for fallback).

    Returns:
        The extracted object name (uppercase) or None if extraction fails completely.
    """
    match = OBJECT_NAME_REGEX.search(plsql_code)
    if match:
        # Group 3 contains the object name
        object_name = match.group(3)
        if object_name:
            log.debug(f"Extracted object name '{object_name.upper()}' using regex from {file_path}")
            return object_name.upper() # Return uppercase for consistency
        else:
            log.warning(f"Regex matched but failed to capture object name group in {file_path}. Match groups: {match.groups()}")
    else:
         log.warning(f"Could not find CREATE statement via regex in {file_path}. Falling back to filename.")

    # Fallback to filename
    try:
        base_name = os.path.basename(file_path)
        object_name = os.path.splitext(base_name)[0].upper()
        # Remove common prefixes/suffixes like R__, V__, T__ if desired (adjust pattern as needed)
        object_name = re.sub(r'^(R__|V__|T__|PKS__|PKB__|FNC__|PRC__|TRG__)', '', object_name, flags=re.IGNORECASE)
        log.debug(f"Extracted object name '{object_name}' using fallback filename from {file_path}")
        return object_name
    except Exception as e:
        log.error(f"Error extracting object name from filename '{file_path}': {e}")
        return None


def compile_object(file_path: str) -> Dict[str, Any]:
    """
    Compiles a PL/SQL or SQL object from a file against the Oracle database.

    Args:
        file_path: The path to the .sql, .pks, .pkb, .vw, etc. file.

    Returns:
        A dictionary containing:
            - status (str): 'success', 'success_with_warnings', 'failed', 'error_reading_file', 'error_connecting', 'error_compiling', 'no_connection_module'
            - object_name (Optional[str]): The determined object name (or None).
            - messages (Optional[List[str]]): Compilation errors/warnings or error details.
            - file_path (str): The original file path provided.
    """
    result: Dict[str, Any] = {
        "status": None,
        "object_name": None,
        "messages": [],
        "file_path": file_path,
    }

    log.info(f"Starting compilation for: {file_path}")

    if connect is None: # Check if the import/fallback failed
        result["status"] = "no_connection_module"
        result["messages"] = ["Database connection module not loaded."]
        log.critical("Cannot compile object: connect function not available.")
        return result

    # 1. Read the PL/SQL file contents.
    plsql_code = ""
    try:
        # Try common encodings
        encodings_to_try = ['utf-8', 'cp1252', 'latin1']
        for enc in encodings_to_try:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    plsql_code = f.read()
                log.debug(f"Successfully read '{file_path}' with encoding '{enc}'")
                break # Stop trying encodings once successful
            except UnicodeDecodeError:
                log.debug(f"Failed to read '{file_path}' with encoding '{enc}'")
                continue # Try next encoding
            except Exception as read_exc:
                 # Handle other file reading errors (e.g., permissions)
                 raise read_exc # Re-raise other exceptions

        # If plsql_code is still empty after trying all encodings
        if not plsql_code and os.path.exists(file_path):
             # This case handles files that exist but failed all decoding attempts
             # Or files that might be truly empty
             if os.path.getsize(file_path) == 0:
                 result["status"] = "error_reading_file"
                 result["messages"] = [f"File '{file_path}' is empty."]
                 log.warning(f"File '{file_path}' is empty.")
                 return result
             else:
                  raise ValueError(f"Could not decode file '{file_path}' with tried encodings: {encodings_to_try}")


        # Remove any line that contains only a slash (e.g., a line with "/" only)
        # and trim whitespace from the result. Handles Windows/Unix line endings.
        plsql_code = "\n".join(line for line in plsql_code.splitlines() if line.strip() != "/").strip()

        # Ensure there's code left after stripping slashes
        if not plsql_code:
             # This covers files containing *only* slashes or whitespace after removing slash lines
             result["status"] = "error_reading_file"
             result["messages"] = [f"File '{file_path}' contains no executable code (or only '/' lines)."]
             log.warning(f"File '{file_path}' contains no executable code (or only '/' lines).")
             return result

    except FileNotFoundError:
         result["status"] = "error_reading_file"
         result["messages"] = [f"File not found: '{file_path}'"]
         log.error(f"File not found: '{file_path}'")
         return result
    except Exception as exc:
        result["status"] = "error_reading_file"
        result["messages"] = [f"Error reading or decoding file '{file_path}': {exc}"]
        log.error(f"Error reading or decoding file '{file_path}': {exc}", exc_info=True)
        return result

    # 2. Extract object name
    object_name = extract_object_name_from_code(plsql_code, file_path)
    result["object_name"] = object_name
    if not object_name:
         # Log error but proceed; USER_ERRORS check will be skipped later if name is None.
         log.error(f"Could not determine object name for {file_path}. USER_ERRORS check will be skipped.")


    # 3. Connect and Compile
    conn = None
    try:
        conn = connect() # Get connection using the imported function
        if conn is None:
             # Should be handled by connect() raising an error, but double-check
             raise ConnectionError("Failed to establish database connection (connect returned None).")

        with conn.cursor() as cursor:
            log.debug(f"Executing compilation for {object_name or file_path}")
            # Execute the potentially multi-statement block
            # For PL/SQL, just executing the block is usually sufficient
            # For SQL scripts with multiple statements, might need `cursor.execute("BEGIN\n{script}\nEND;")`
            # or split statements, but usually create commands are single logical units.
            cursor.execute(plsql_code)
            log.debug(f"Execution finished for {object_name or file_path}. Checking for errors/warnings.")

            plsql_warning = None
            # DPY-7000 is specific to python-oracledb when PL/SQL compilation succeeds with warnings
            # Check cursor.warning for this specific code.
            # Other warnings might be raised as exceptions or appear in USER_ERRORS.
            try:
                 # cursor.warning is only populated in specific scenarios by the driver
                 w = cursor.warning
                 if w and hasattr(w, 'code') and w.code == 'DPY-7000':
                     plsql_warning = w # Capture the DPY-7000 warning object
                     log.debug(f"Detected DPY-7000 warning: {w.message}")

            except AttributeError:
                 plsql_warning = None # No warning attribute


            # Check USER_ERRORS for explicit compilation errors or detailed warnings (PL/SQL or SQL errors)
            error_messages = []
            if object_name: # Only query user_errors if we have a likely name
                # Query USER_ERRORS for the specific object
                # Note: Object names are stored in uppercase in the dictionary
                query = """
                    SELECT line, position, text, attribute, message_number
                    FROM user_errors
                    WHERE name = :obj_name
                    ORDER BY sequence
                """
                try:
                    # Using object_name directly as it's already uppercase from extraction
                    cursor.execute(query, obj_name=object_name)
                    for line, pos, text, attr, msg_num in cursor:
                        # Distinguish between ERRORS and WARNINGS if possible
                        err_type = "Error" if attr == "ERROR" else f"Warning ({attr})"
                        # Use strip() on text to remove potential trailing newlines
                        error_messages.append(f"{err_type} at Line {line}, Pos {pos}: {text.strip()} (ORA-{msg_num:05d})")
                except oracledb.DatabaseError as ue_err:
                     log.warning(f"Could not query USER_ERRORS for {object_name}: {ue_err}")
                     # Proceed without USER_ERRORS info if query fails

            else:
                log.warning(f"Skipping USER_ERRORS check for {file_path} as object name could not be determined.")


            # Determine final status based on errors and warnings
            if any("Error at Line" in msg for msg in error_messages):
                result["status"] = "failed"
                result["messages"] = error_messages
                log.error(f"Compilation failed for {object_name} ({file_path}) with errors.")
                # Consider conn.rollback() here if DDL failures shouldn't be implicitly committed?
                # Oracle often auto-commits DDL success/failure, but explicit rollback might be safer.
            elif plsql_warning or any("Warning at Line" in msg for msg in error_messages):
                result["status"] = "success_with_warnings"
                # Combine DPY-7000 message (if any) with USER_ERRORS messages
                combined_messages = []
                if plsql_warning:
                    combined_messages.append(f"Driver Warning: {getattr(plsql_warning, 'message', 'DPY-7000 Details Unavailable')}")
                combined_messages.extend(error_messages) # Add warnings from USER_ERRORS
                result["messages"] = combined_messages
                log.warning(f"Compilation succeeded with warnings for {object_name} ({file_path}).")
                conn.commit() # Commit successful compilation even with warnings
            else:
                # No DPY-7000 warning and no errors/warnings found in USER_ERRORS
                result["status"] = "success"
                result["messages"] = [f"Compilation successful for {object_name}."]
                log.info(f"Compilation successful for {object_name} ({file_path}).")
                conn.commit() # Commit successful compilation

        return result

    except oracledb.DatabaseError as db_exc:
        result["status"] = "error_compiling"
        error_msg = f"Database error during compilation: {db_exc}"
        # Try to extract more detail if available (e.g., ORA code, offset)
        if hasattr(db_exc, 'args') and db_exc.args and hasattr(db_exc.args[0], 'code'):
            ora_code = db_exc.args[0].code
            ora_msg = db_exc.args[0].message.strip()
            offset = getattr(db_exc.args[0], 'offset', None)
            line_num_str = ""
            if offset is not None and plsql_code: # Ensure plsql_code was read
                try:
                     # Count newlines before the offset to estimate line number
                    line_num = plsql_code.count('\n', 0, offset) + 1
                    line_num_str = f" at line ~{line_num}"
                except Exception:
                    pass # Ignore errors in line number calculation
            error_msg = f"Database error during compilation{line_num_str}: ORA-{ora_code:05d} - {ora_msg}"

        result["messages"] = [error_msg]
        log.error(f"Database error compiling {object_name} ({file_path}): {error_msg}", exc_info=False) # exc_info=False if msg is detailed
        # Consider rollback if connection is still alive
        # if conn: conn.rollback()
        return result
    except ConnectionError as conn_err:
         result["status"] = "error_connecting"
         result["messages"] = [f"Connection error: {conn_err}"]
         log.error(f"Connection error for {file_path}: {conn_err}")
         return result
    except Exception as exc:
        result["status"] = "error_compiling" # Generic compilation error
        result["messages"] = [f"Unexpected error during compilation of '{file_path}': {exc}"]
        log.exception(f"Unexpected error compiling {object_name} ({file_path})")
        # Consider rollback if connection is still alive
        # if conn: conn.rollback()
        return result
    finally:
        if conn is not None:
            try:
                conn.close()
                log.debug(f"Database connection closed for {file_path}")
            except Exception as close_exc:
                # Log error but don't overwrite primary result
                log.error(f"Error closing connection for {file_path}: {close_exc}")


def main():
    # This main function is for module-level testing. Use the CLI or script for general use.
    # Setup basic logging for direct script execution testing
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(module)s - %(message)s')

    # Create dummy files for testing if they don't exist
    test_files_dir = Path("temp_compile_test_files")
    test_files_dir.mkdir(exist_ok=True)

    test_files_content = {
        "test_ok.pks": """
CREATE OR REPLACE PACKAGE test_ok_pkg AS -- Changed name slightly for uniqueness
  PROCEDURE my_proc;
END test_ok_pkg;
/
        """,
         "test_ok_body.pkb": """
CREATE OR REPLACE PACKAGE BODY test_ok_pkg AS
    PROCEDURE my_proc IS BEGIN NULL; END;
END test_ok_pkg;
/
        """,
        "test_err.pks": """
CREATE OR REPLACE PACKAGE test_err_pkg AS
  PROCEDURE my_proc_error; -- Missing semicolon
END test_err_pkg;
/
        """,
         "test_warn.fnc": """
CREATE OR REPLACE FUNCTION test_warn_fnc RETURN NUMBER AS
  l_unused_var PLS_INTEGER; -- This might generate a warning depending on DB settings
BEGIN
  RETURN 1;
END test_warn_fnc;
/
         """,
         "R__my_view.vw": """
CREATE OR REPLACE VIEW r__my_view AS
SELECT dummy FROM dual;
/
         """,
         "non_existent_file.sql": None, # Represents a file that won't be created
         "empty_file.sql": "",
         "slash_only.sql": "/",
         "decode_err.sql": b'\x80abc', # Invalid start byte for UTF-8

    }

    test_files_compile = []
    for fname, content in test_files_content.items():
         fpath = test_files_dir / fname
         if content is None and fname == "non_existent_file.sql":
              test_files_compile.append(str(fpath)) # Add path even if it won't exist
              continue
         if isinstance(content, bytes):
              # Write bytes for decode error test
               try:
                    with open(fpath, "wb") as f:
                        f.write(content)
                    print(f"Created dummy file (binary): {fpath}")
                    test_files_compile.append(str(fpath))
               except Exception as e:
                    print(f"Failed to create binary test file {fpath}: {e}")
         elif content is not None:
            # Write text files
            try:
                with open(fpath, "w", encoding='utf-8') as f:
                    f.write(content)
                print(f"Created dummy file: {fpath}")
                test_files_compile.append(str(fpath))
            except Exception as e:
                print(f"Failed to create test file {fpath}: {e}")

    # --- Compilation Tests ---
    print("\n--- Testing Compilation (Module Level) ---")
    print("\nEnsure DB connection details are set in environment or .env file.")

    all_results = []
    for test_file in test_files_compile:
        print(f"\nTesting compile_object with file: {test_file}")
        result = compile_object(test_file)
        all_results.append(result)
        print(f"Result Status: {result.get('status')}")
        print(f"Object Name:   {result.get('object_name')}")
        print("Messages:")
        if result.get("messages"):
            for msg in result["messages"]:
                print(f"  - {msg}")
        else:
            print("  (No messages)")
        print("-" * 20)

    # --- Cleanup Dummy Files ---
    print("\nCleaning up test files...")
    try:
        shutil.rmtree(test_files_dir)
        print(f"Removed directory: {test_files_dir}")
    except Exception as e:
         print(f"Error removing test directory {test_files_dir}: {e}")


if __name__ == "__main__":
    # Add imports needed only for main() testing block
    from pathlib import Path
    import shutil
    main()