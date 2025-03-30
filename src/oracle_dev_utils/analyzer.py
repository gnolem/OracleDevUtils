import re
import os
import logging
import oracledb # Needed for DB interaction
from typing import List, Dict, Set, Any, Optional

# Use relative import within the package
try:
    from .db_connection import connect, oracledb
except ImportError:
    try:
        from db_connection import connect, oracledb
    except ImportError:
        logging.error("Failed to import 'connect' from db_connection.")
        connect = None
        oracledb = None # Ensure oracledb is None if import fails

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Basic PL/SQL Keywords and common built-ins to ignore as object references
PLSQL_KEYWORDS = {
    'ACCESS', 'ACCOUNT', 'ACTIVATE', 'ADD', 'ADMIN', 'ADVISE', 'AFTER', 'ALIAS', 'ALL', 'ALLOCATE', 'ALLOW',
    'ALTER', 'ANALYZE', 'AND', 'ANY', 'ARCHIVE', 'ARCHIVELOG', 'ARRAY', 'AS', 'ASC', 'AT', 'AUDIT', 'AUTHENTICATED',
    'AUTHORIZATION', 'AUTO', 'AUTOEXTEND', 'AUTOMATIC', 'BACKUP', 'BECOME', 'BEFORE', 'BEGIN', 'BETWEEN', 'BFILE',
    'BITMAP', 'BLOB', 'BLOCK', 'BODY', 'BY', 'CACHE', 'CACHE_INSTANCES', 'CANCEL', 'CASCADE', 'CASE', 'CAST',
    'CFILE', 'CHAINED', 'CHANGE', 'CHAR', 'CHARACTER', 'CHAR_CS', 'CHECK', 'CHECKPOINT', 'CHOOSE', 'CHUNK',
    'CLEAR', 'CLOB', 'CLONE', 'CLOSE', 'CLOSE_CACHED_OPEN_CURSORS', 'CLUSTER', 'COALESCE', 'COLLECT', 'COLUMN',
    'COLUMNS', 'COMMENT', 'COMMIT', 'COMMITTED', 'COMPATIBILITY', 'COMPILE', 'COMPLETE', 'COMPOSITE_LIMIT',
    'COMPRESS', 'COMPUTE', 'CONNECT', 'CONNECT_TIME', 'CONSTRAINT', 'CONSTRAINTS', 'CONTENTS', 'CONTINUE',
    'CONTROLFILE', 'CONVERT', 'COST', 'CPU_PER_CALL', 'CPU_PER_SESSION', 'CREATE', 'CROSS', 'CUBE', 'CURRENT',
    'CURRENT_SCHEMA', 'CURREN_USER', 'CURSOR', 'CYCLE', 'DANGLING', 'DATABASE', 'DATAFILE', 'DATAFILES',
    'DATAOBJNO', 'DATE', 'DATE_CACHE', 'DAY', 'DBA', 'DBTIMEZONE', 'DDL', 'READ', 'DEBUG', 'DEC', 'DECIMAL',
    'DECLARE', 'DEFAULT', 'DEFERRABLE', 'DEFERRED', 'DEGREE', 'DELETE', 'DEMAND', 'DENSE_RANK', 'DEPTH', 'DESC',
    'DIRECTORY', 'DISABLE', 'DISASSOCIATE', 'DISCONNECT', 'DISK', 'DISKGROUP', 'DISMOUNT', 'DISTINCT',
    'DISTRIBUTED', 'DML', 'DOUBLE', 'DROP', 'DUMP', 'DYNAMIC', 'EACH', 'ELSE', 'ENABLE', 'END', 'ENFORCE',
    'ENTRY', 'ERROR', 'ESCAPE', 'EXCEPT', 'EXCEPTIONS', 'EXCHANGE', 'EXCLUDING', 'EXCLUSIVE', 'EXECUTE', 'EXISTS',
    'EXPIRE', 'EXPLAIN', 'EXTEND', 'EXTENDS', 'EXTENT', 'EXTERNALLY', 'FAILGROUP', 'FAILED_LOGIN_ATTEMPTS',
    'FALSE', 'FAST', 'FILE', 'FILTER', 'FINISH', 'FIRST', 'FIRST_ROWS', 'FLAGGER', 'FLASHBACK', 'FLOAT', 'FLOB',
    'FLUSH', 'FOR', 'FORCE', 'FOREIGN', 'FREELIST', 'FREELISTS', 'FROM', 'FULL', 'FUNCTION', 'GLOBAL',
    'GLOBALLY', 'GLOBAL_NAME', 'GRANT', 'GROUP', 'GROUPS', 'HASH', 'HAVING', 'HEADER', 'HEAP', 'HOUR',
    'IDENTIFIED', 'IDGENERATORS', 'IDLE_TIME', 'IF', 'IMMEDIATE', 'IN', 'INCLUDING', 'INCREMENT', 'INDEX',
    'INDEXED', 'INDEXES', 'INDICATOR', 'IND_PARTITION', 'INITIAL', 'INITIALLY', 'INITRANS', 'INSERT', 'INSTANCE',
    'INSTANCES', 'INSTEAD', 'INT', 'INTEGER', 'INTEGRITY', 'INTERMEDIATE', 'INTERNAL_USE', 'INTERSECT',
    'INTERVAL', 'INTO', 'INVALIDATE', 'IS', 'ISOLATION', 'JAVA', 'JOIN', 'KEEP', 'KEY', 'KILL', 'LABEL', 'LAST',
    'LAYER', 'LESS', 'LEVEL', 'LIBRARY', 'LIKE', 'LIMIT', 'LINK', 'LIST', 'LOB', 'LOCAL', 'LOCK', 'LOCKED',
    'LOG', 'LOGFILE', 'LOGGING', 'LOGICAL', 'LOGICAL_READS_PER_CALL', 'LOGICAL_READS_PER_SESSION', 'LONG',
    'LOOP', 'MANAGE', 'MASTER', 'MAX', 'MAXARCHLOGS', 'MAXDATAFILES', 'MAXEXTENTS', 'MAXIMIZE', 'MAXINSTANCES',
    'MAXLOGFILES', 'MAXLOGHISTORY', 'MAXLOGMEMBERS', 'MAXSIZE', 'MAXTRANS', 'MAXVALUE', 'MEASURES', 'MEMBER',
    'MERGE', 'MIN', 'MINEXTENTS', 'MINIMIZE', 'MINUS', 'MINUTE', 'MINVALUE', 'MLSLABEL', 'MODE', 'MODIFY',
    'MONITORING', 'MONTH', 'MOUNT', 'MOVE', 'MTS_DISPATCHERS', 'MULTISET', 'NAME', 'NATIONAL', 'NATURAL',
    'NCHAR', 'NCHAR_CS', 'NCLOB', 'NEEDED', 'NESTED', 'NETWORK', 'NEVER', 'NEW', 'NEXT', 'NOARCHIVELOG',
    'NOAUDIT', 'NOCACHE', 'NOCOMPRESS', 'NOCYCLE', 'NOFORCE', 'NOLOGGING', 'NOMAXVALUE', 'NOMINVALUE',
    'NONE', 'NOORDER', 'NOOVERRIDE', 'NOPARALLEL', 'NOREVERSE', 'NORMAL', 'NOSORT', 'NOT', 'NOTHING', 'NOWAIT',
    'NULL', 'NUMBER', 'NUMERIC', 'NVARCHAR2', 'OBJECT', 'OBJNO', 'OBJNO_REUSE', 'OF', 'OFF', 'OFFLINE', 'OID',
    'OIDINDEX', 'OLD', 'ON', 'ONLINE', 'ONLY', 'OPAQUE', 'OPEN', 'OPERATOR', 'OPTIMAL', 'OPTIMIZER_GOAL',
    'OPTION', 'OR', 'ORDER', 'ORGANIZATION', 'OSERROR', 'OVER', 'OVERFLOW', 'OVERRIDE', 'OWN', 'PACKAGE',
    'PARALLEL', 'PARAMETERS', 'PARENT', 'PARTITION', 'PASSWORD', 'PASSWORD_GRACE_TIME', 'PASSWORD_LIFE_TIME',
    'PASSWORD_LOCK_TIME', 'PASSWORD_REUSE_MAX', 'PASSWORD_REUSE_TIME', 'PASSWORD_VERIFY_FUNCTION', 'PCTFREE',
    'PCTINCREASE', 'PCTTHRESHOLD', 'PCTUSED', 'PCTVERSION', 'PERCENT', 'PERMANENT', 'PFILE', 'PHYSICAL', 'PLAN',
    'PLSQL_DEBUG', 'POLICY', 'POST_TRANSACTION', 'PRECISION', 'PREPARE', 'PRESERVE', 'PRIMARY', 'PRIOR',
    'PRIVATE', 'PRIVATE_SGA', 'PRIVILEGE', 'PRIVILEGES', 'PROCEDURE', 'PROFILE', 'PROTECTED', 'PUBLIC',
    'PURGE', 'QUEUE', 'QUOTA', 'RAISE', 'RANGE', 'RAW', 'RBA', 'READUP', 'REAL', 'REBUILD', 'RECOVER',
    'RECOVERABLE', 'RECOVERY', 'REF', 'REFERENCES', 'REFERENCING', 'REFRESH', 'RENAME', 'REPLACE', 'RESET',
    'RESETLOGS', 'RESIZE', 'RESOLVE', 'RESOURCE', 'RESTRICTED', 'RETURN', 'RETURNING', 'REUSE', 'REVERSE',
    'REVOKE', 'ROLE', 'ROLES', 'ROLLBACK', 'ROLLUP', 'ROW', 'ROWID', 'ROWNUM', 'ROWS', 'RULE', 'SAMPLE', 'SAVEPOINT',
    'SB4', 'SCAN_INSTANCES', 'SCHEMA', 'SCN', 'SCOPE', 'SD_ALL', 'SD_INHIBIT', 'SD_SHOW', 'SECOND', 'SEGMENT',
    'SEG_BLOCK', 'SEG_FILE', 'SELECT', 'SEQUENCE', 'SERIALIZABLE', 'SESSION', 'SESSIONS_PER_USER',
    'SESSION_CACHED_CURSORS', 'SESSIONTIMEZONE', 'SET', 'SETS', 'SHARE', 'SHARED', 'SHARED_POOL', 'SHRINK',
    'SIZE', 'SKIP', 'SKIP_UNUSABLE_INDEXES', 'SMALLINT', 'SNAPSHOT', 'SOME', 'SORT', 'SPECIFICATION', 'SPLIT',
    'SPFILE', 'SQL', 'SQL_TRACE', 'SQLERROR', 'STANDBY', 'START', 'STARTING', 'STATEMENT_ID', 'STATISTICS',
    'STOP', 'STORAGE', 'STORE', 'SUBPARTITION', 'SUBSTITUTABLE', 'SUCCESSFUL', 'SWITCH', 'SYNONYM', 'SYSDATE',
    'SYSDBA', 'SYSOPER', 'SYSTEM', 'TABLE', 'TABLES', 'TABLESPACE', 'TABLESPACE_NO', 'TABNO', 'TEMPFILE',
    'TEMPLATE', 'TEMPORARY', 'TERMINATE', 'THAN', 'THE', 'THEN', 'THREAD', 'THROUGH', 'TIME', 'TIMESTAMP',
    'TIMEZONE_ABBR', 'TIMEZONE_HOUR', 'TIMEZONE_MINUTE', 'TIMEZONE_REGION', 'TO', 'TOPLEVEL', 'TRACE',
    'TRACING', 'TRANSACTION', 'TRANSITIONAL', 'TRIGGER', 'TRIGGERS', 'TRUE', 'TRUNCATE', 'TX', 'TYPE', 'UB2',
    'UBA', 'UID', 'UNARCHIVED', 'UNDO', 'UNIFORM', 'UNION', 'UNIQUE', 'UNLIMITED', 'UNLOCK', 'UNPACKED',
    'UNPROTECTED', 'UNRECOVERABLE', 'UNTIL', 'UNUSABLE', 'UNUSED', 'UPDATABLE', 'UPDATE', 'UPGRADE', 'USAGE',
    'USE', 'USER', 'USING', 'VALIDATE', 'VALIDATION', 'VALUE', 'VALUES', 'VARCHAR', 'VARCHAR2', 'VARYING',
    'VIEW', 'WHEN', 'WHENEVER', 'WHERE', 'WHILE', 'WITH', 'WITHIN', 'WITHOUT', 'WORK', 'WRITE', 'WRITEDOWN',
    'WRITEUP', 'XMLATTRIBUTES', 'XMLEXISTS', 'XMLNAMESPACES', 'YEAR', 'ZONE',
    # Common Oracle built-in packages/types (add more as needed)
    'DBMS_OUTPUT', 'DBMS_SQL', 'DBMS_LOCK', 'DBMS_ALERT', 'DBMS_PIPE', 'DBMS_JOB', 'DBMS_SCHEDULER',
    'DBMS_AQ', 'DBMS_AQADM', 'DBMS_CRYPTO', 'DBMS_LOB', 'DBMS_RANDOM', 'DBMS_UTILITY', 'UTL_FILE',
    'UTL_HTTP', 'UTL_SMTP', 'UTL_TCP', 'UTL_URL', 'UTL_RAW', 'SYS_REFCURSOR', 'ANYDATA', 'XMLTYPE', 'DUAL' # Added DUAL here too
}


def remove_comments(code: str) -> str:
    """Removes single-line and multi-line comments from PL/SQL code."""
    # Remove multi-line comments /* ... */ using non-greedy match
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
    # Remove single-line comments -- ... (including potential preceding whitespace)
    code = re.sub(r'\s*--.*?$', '', code, flags=re.MULTILINE)
    return code # Return without extra strip here, compare_code_lines handles it

def find_object_references_in_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Finds potential database object references in a PL/SQL file via static analysis.

    Args:
        file_path: Path to the PL/SQL file (.sql, .pks, .pkb, etc.).

    Returns:
        A list of dictionaries, each containing:
        - 'reference' (str): The potential object reference found.
        - 'line_number' (int): The line number where it was found.
        - 'file_path' (str): The original file path.
    """
    references = []
    if not os.path.exists(file_path):
        logging.error(f"File not found for reference analysis: {file_path}")
        return references

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_lines = f.readlines()

        code_no_comments = remove_comments("".join(original_lines))
        lines_no_comments = code_no_comments.splitlines()

        identifier_regex = re.compile(
            r"""
            (?<![:=<>!]) # Negative lookbehind
            \b # Word boundary
            ( # Start capture group 1: full reference
              (?: # Optional schema part (non-capturing within group 1)
                  (?:\"?([a-zA-Z0-9_$#]+)\"?) # Schema name (group 2)
                  \.
              )?
              \"?([a-zA-Z0-9_$#]{2,})\"? # Object name (group 3)
              (?: # Optional member part(s) (non-capturing within group 1)
                  \. \"? [a-zA-Z0-9_$#]+ \"?
              )* # Zero or more members allowed
            ) # End capture group 1
            # Lookahead
            (?=[\s.(%@;]|\s*\b(?:AS|IS|NOT|NULL|DEFAULT|THEN|LOOP|=>)\b|$)
            """,
            re.IGNORECASE | re.VERBOSE
        )
        found_references: Set[str] = set()

        for line_num, line in enumerate(lines_no_comments, 1):
            line_upper = line.upper()
            if not line.strip(): continue
            # Heuristics to skip declarations (can be refined)
            if re.match(r'^\s*(?:[lgcprt]_|v_)[a-zA-Z0-9_$#]+\s+(?:CONSTANT\s+)?(?:[A-Z0-9._"%]+|TABLE\s+OF|RECORD|CURSOR|REF\s+CURSOR)\b', line_upper): continue

            for match in identifier_regex.finditer(line):
                full_ref = match.group(1) # Full reference (e.g., schema.object.member)
                schema = match.group(2)   # Schema part (e.g., SYS)
                obj_name = match.group(3) # Base object name (e.g., DUAL)

                # Prepare for case-insensitive comparison
                full_ref_upper = full_ref.upper()
                schema_upper = schema.upper() if schema else None
                base_obj_upper = obj_name.upper() if obj_name else None # Use a distinct name

                # --- REVISED FILTERING LOGIC ---

                # 1. Skip if the *entire* matched string is a keyword
                if full_ref_upper in PLSQL_KEYWORDS:
                    logging.debug(f"Filtering '{full_ref}' (keyword match: full string)")
                    continue

                # 2. Skip if the *schema part* itself is a keyword (unlikely but possible)
                if schema_upper and schema_upper in PLSQL_KEYWORDS:
                    logging.debug(f"Filtering '{full_ref}' (keyword match: schema part '{schema_upper}')")
                    continue

                # 3. Skip if *not* schema-qualified AND the *base object* is a keyword
                #    (This allows schema-qualified keywords like SYS.DUAL)
                if not schema_upper and base_obj_upper and base_obj_upper in PLSQL_KEYWORDS:
                    logging.debug(f"Filtering '{full_ref}' (keyword match: base object '{base_obj_upper}' without schema)")
                    continue

                # 4. Context Checks (Parameters, Assignments - Keep these)
                match_start_index = match.start(1)
                # Simple check for common assignment/parameter patterns
                preceding_text = line[:match_start_index].rstrip()
                if preceding_text.endswith((':=', '=>')):
                     logging.debug(f"Filtering '{full_ref}' (context match: preceding {preceding_text[-2:]})")
                     continue

                following_text = line[match.end(1):].lstrip()
                # Example: Filter labels like "my_label:"
                if following_text.startswith(':'):
                    logging.debug(f"Filtering '{full_ref}' (context match: following ':')")
                    continue

                # --- END REVISED FILTERING ---

                # If it passes all filters, add it
                # Check for duplicates based on full_ref and line_number before adding
                ref_key = (full_ref_upper, line_num)
                if ref_key not in found_references: # Use the set defined earlier
                    references.append({
                        "reference": full_ref,
                        "line_number": line_num,
                        "file_path": file_path
                    })
                    found_references.add(ref_key) # Add tuple (ref, line) to the set
                    logging.debug(f"Potential reference added: '{full_ref}' at line {line_num}")

    except Exception as e:
        logging.exception(f"Error analyzing static references in file '{file_path}': {e}")

    # Remove the old unique_references loop at the end, duplication is handled above
    # unique_references = []
    # seen = set()
    # for ref_dict in references:
    #     key = (ref_dict['reference'].upper(), ref_dict['line_number'])
    #     if key not in seen:
    #         unique_references.append(ref_dict)
    #         seen.add(key)

    # Return the list built using the found_references set check
    return references


# --- NEW FUNCTION ---
def find_referencing_objects_in_db(referenced_object_name: str,
                                   referenced_schema: Optional[str] = None,
                                   referenced_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Queries ALL_DEPENDENCIES to find objects that depend on the specified object.

    Args:
        referenced_object_name: The name of the object being referenced (e.g., 'MY_TABLE', 'MY_PACKAGE'). Case-insensitive match.
        referenced_schema: The schema/owner of the referenced object. If None, attempts to use current schema,
                           but may find references from other schemas if the object name is unique or synonyms exist.
                           Case-insensitive match.
        referenced_type: The type of the object being referenced (e.g., 'TABLE', 'PACKAGE', 'VIEW').
                         Filtering by type increases accuracy. Case-insensitive match.

    Returns:
        A dictionary containing:
            - 'status' (str): 'success', 'error_connecting', 'error_querying', 'no_connection_module'
            - 'referenced_object': Details of the object queried.
            - 'referencing_objects' (List[Dict]): A list of objects that reference the target object.
            - 'error_message' (Optional[str]): Error details if status is not 'success'.
    """
    result: Dict[str, Any] = {
        "status": None,
        "referenced_object": {
            "name": referenced_object_name,
            "schema": referenced_schema,
            "type": referenced_type
        },
        "referencing_objects": [],
        "error_message": None
    }

    if connect is None: # Check if the import failed or the fallback connect is None
        result["status"] = "no_connection_module"
        result["error_message"] = "Database connection module not loaded or failed to import."
        logging.critical("Cannot query DB dependencies: connect function not available.")
        return result

    conn = None
    try:
        conn = connect() # Call the imported connect function
        if conn is None:
             # If connect itself returns None (e.g., due to config error handled within connect)
             raise ConnectionError("Failed to establish database connection (connect returned None).")

        with conn.cursor() as cursor:
            # Determine current schema if not provided
            effective_schema = referenced_schema
            if not effective_schema:
                try:
                    cursor.execute("SELECT sys_context('USERENV', 'CURRENT_SCHEMA') FROM dual")
                    current_schema_res = cursor.fetchone()
                    if current_schema_res:
                        effective_schema = current_schema_res[0]
                    else:
                        logging.warning("Could not determine current schema (query returned no result). Query might be less specific.")
                except Exception as ctx_err:
                     logging.warning(f"Could not determine current schema due to error: {ctx_err}. Query might be less specific.")

            logging.info(f"Querying dependencies for: Schema='{effective_schema or 'ANY'}', Name='{referenced_object_name}', Type='{referenced_type or 'ANY'}'")

            # Base query
            sql = """
            SELECT owner, name, type, dependency_type
            FROM all_dependencies
            WHERE referenced_name = UPPER(:ref_name)
            """
            params: Dict[str, Any] = {"ref_name": referenced_object_name}

            # Add optional filters
            # Filter by owner only if we are reasonably sure we have one
            if effective_schema:
                sql += " AND referenced_owner = UPPER(:ref_owner)"
                params["ref_owner"] = effective_schema
            elif referenced_schema is not None: # User explicitly passed None, maybe don't assume current user?
                 logging.warning("Querying without a referenced_schema filter. Results may include objects from other schemas.")


            if referenced_type:
                sql += " AND referenced_type = UPPER(:ref_type)"
                params["ref_type"] = referenced_type

            sql += " ORDER BY owner, name, type" # Consistent ordering

            cursor.execute(sql, params)

            for owner, name, obj_type, dep_type in cursor:
                result["referencing_objects"].append({
                    "owner": owner,
                    "name": name,
                    "type": obj_type,
                    "dependency_type": dep_type # e.g., 'HARD', 'REF'
                })

            result["status"] = "success"
            logging.info(f"Found {len(result['referencing_objects'])} referencing objects for {referenced_object_name}")

    except oracledb.DatabaseError as db_exc:
        result["status"] = "error_querying"
        result["error_message"] = f"Database query error: {db_exc}"
        logging.error(f"Database error querying dependencies for {referenced_object_name}: {db_exc}", exc_info=True)
    except ConnectionError as conn_err:
         result["status"] = "error_connecting"
         result["error_message"] = f"Connection error: {conn_err}"
         logging.error(f"Connection error querying dependencies: {conn_err}")
    except Exception as exc:
        result["status"] = "error_querying" # Generic query error
        result["error_message"] = f"Unexpected error querying dependencies: {exc}"
        logging.exception(f"Unexpected error querying dependencies for {referenced_object_name}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass # Ignore errors during close after another error

    return result
# --- END NEW FUNCTION ---


def main():
    # This main block is primarily for testing this specific module directly.
    # Actual usage would typically be via the CLI or importing functions elsewhere.

    # Example: Create a dummy file for static analysis test
    test_ref_file = "test_refs_analyzer.pkb" # Use unique name to avoid conflict
    test_ref_content = """
    CREATE OR REPLACE PACKAGE BODY test_refs_analyzer AS
      PROCEDURE proc1 IS BEGIN UPDATE my_table SET col1 = 1; END;
      FUNCTION func1 RETURN NUMBER IS BEGIN RETURN sysdate; END; -- Not keyword 'SYSDATE'
    END;
    """
    try:
        with open(test_ref_file, "w") as f:
            f.write(test_ref_content)
        print(f"Created dummy file: {test_ref_file}")

        print(f"\n--- Testing Static Reference Analysis (File Based) ---")
        refs = find_object_references_in_file(test_ref_file)
        if refs:
            print(f"\nFound {len(refs)} potential static references in {test_ref_file}:")
            refs.sort(key=lambda x: (x['line_number'], x['reference']))
            for ref_info in refs:
                print(f"  - Line {ref_info['line_number']:<4}: {ref_info['reference']}")
        else:
            print(f"\nNo static references found or error occurred for {test_ref_file}.")

    finally:
        if os.path.exists(test_ref_file):
            os.remove(test_ref_file)
            print(f"Removed dummy file: {test_ref_file}")


    # --- Database Dependency Test ---
    print(f"\n--- Testing Database Dependency Analysis (Requires DB Connection) ---")
    # IMPORTANT: Replace 'DUAL' and 'SYS' with an object YOU KNOW exists
    test_db_object_name = 'DUAL'
    test_db_object_schema = 'SYS'
    test_db_object_type = 'TABLE'

    print(f"Querying DB for objects referencing: Schema='{test_db_object_schema or 'CURRENT'}', Name='{test_db_object_name}', Type='{test_db_object_type or 'ANY'}'")
    # Ensure .env is configured for this test to run
    print("Ensure DB connection details are set in '.env' file for this test.")
    db_deps_result = find_referencing_objects_in_db(
        referenced_object_name=test_db_object_name,
        referenced_schema=test_db_object_schema,
        referenced_type=test_db_object_type
    )

    print(f"Result Status: {db_deps_result['status']}")
    if db_deps_result['status'] == 'success':
        if db_deps_result['referencing_objects']:
            print("\nReferencing Objects Found:")
            for dep in db_deps_result['referencing_objects']:
                print(f"  - Owner: {dep['owner']:<20} Name: {dep['name']:<30} Type: {dep['type']:<15} DepType: {dep['dependency_type']}")
        else:
            print("\nNo referencing objects found in ALL_DEPENDENCIES.")
    elif db_deps_result['error_message']:
        print(f"Error: {db_deps_result['error_message']}")
    else:
        print("Analysis failed or could not connect.")


if __name__ == "__main__":
    # Note: Running this directly requires .env file in the CWD or env vars set
    # and might have issues with relative imports depending on execution context.
    # Recommend running via `python -m oracle_dev_utils.analyzer` if needed,
    # or preferably, run tests or the CLI entry point.
    main()