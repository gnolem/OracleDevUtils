# FILE: C:\Users\tke\OracleDevUtils\tests\test_compiler.py
import pytest
import os
from oracle_dev_utils.compiler import compile_object, extract_object_name_from_code

# --- Tests for extract_object_name_from_code ---

@pytest.mark.parametrize("code, expected_name", [
    ("CREATE OR REPLACE PACKAGE my_pkg AS END;", "MY_PKG"),
    ("create function my_func RETURN NUMBER IS BEGIN RETURN 1; END;", "MY_FUNC"),
    (" CREATE\tVIEW my_view AS SELECT * FROM dual;", "MY_VIEW"),
    ("CREATE OR REPLACE PACKAGE BODY app_schema.my_body AS END;", "MY_BODY"),
    ('create or replace type "My_Type" as object (id number);', 'MY_TYPE'),
    ('CREATE PUBLIC SYNONYM public_syn FOR other_schema.table;', 'PUBLIC_SYN'), # Basic synonym
    ('CREATE SEQUENCE my_seq START WITH 1;', 'MY_SEQ'),
    ("CREATE TRIGGER my_trg BEFORE INSERT ON employees FOR EACH ROW BEGIN NULL; END;", "MY_TRG"),
    # Fallback cases (no CREATE statement) handled by test_extract_name_fallback
])
def test_extract_name_regex(code, expected_name):
    assert extract_object_name_from_code(code, "dummy_path.sql") == expected_name

@pytest.mark.parametrize("file_path, expected_name", [
    ("my_object.pks", "MY_OBJECT"),
    ("/path/to/V__MY_VIEW.vw", "MY_VIEW"), # Test prefix removal
    ("R__proc_name.prc", "PROC_NAME"), # Test prefix removal
    ("no_extension", "NO_EXTENSION"),
    ("complex.name.with.dots.sql", "COMPLEX.NAME.WITH.DOTS"),
])
def test_extract_name_fallback(file_path, expected_name):
    code = "SELECT * FROM some_table;" # Code without a CREATE statement
    assert extract_object_name_from_code(code, file_path) == expected_name

def test_extract_name_regex_no_match():
     code = "ALTER TABLE my_table ADD constraint pk_id PRIMARY KEY (id);"
     # Expect fallback to filename
     assert extract_object_name_from_code(code, "alter_script.sql") == "ALTER_SCRIPT"


# --- Tests for compile_object ---
# These tests generally require a database connection.

@pytest.mark.database
def test_compile_success(temp_sql_file, db_connection):
    if not db_connection: pytest.skip("Database connection not available")
    content = """
    CREATE OR REPLACE FUNCTION test_compile_success_fnc RETURN NUMBER AS
    BEGIN
      RETURN 123;
    END test_compile_success_fnc;
    """
    file_path = temp_sql_file("test_success.fnc", content)
    result = compile_object(file_path)

    assert result['status'] == 'success'
    assert result['object_name'] == 'TEST_COMPILE_SUCCESS_FNC'
    assert result['file_path'] == file_path
    assert isinstance(result['messages'], list)
    assert "Compilation successful" in result['messages'][0]

    # Optional: Verify object status in DB (requires db_connection fixture)
    with db_connection.cursor() as cursor:
         cursor.execute("SELECT status FROM user_objects WHERE object_name = 'TEST_COMPILE_SUCCESS_FNC' AND object_type = 'FUNCTION'")
         status = cursor.fetchone()
         assert status[0] == 'VALID'


@pytest.mark.database
def test_compile_failure_syntax_error(temp_sql_file, db_connection):
    if not db_connection: pytest.skip("Database connection not available")
    content = """
    CREATE OR REPLACE PROCEDURE test_compile_fail_prc IS
    BEGIN
      DBMS_OUTPUT.PUT_LINE('Hello') -- Missing semicolon
    END test_compile_fail_prc;
    """
    file_path = temp_sql_file("test_fail.prc", content)
    result = compile_object(file_path)

    assert result['status'] == 'failed'
    assert result['object_name'] == 'TEST_COMPILE_FAIL_PRC'
    assert result['file_path'] == file_path
    assert isinstance(result['messages'], list)
    assert len(result['messages']) > 0
    # Check for specific Oracle error indicators in the message
    assert any("PLS-00103" in msg for msg in result['messages']) # Example: Encountered symbol error
    assert any("Error at Line" in msg for msg in result['messages'])

    # Optional: Verify object status in DB is INVALID
    with db_connection.cursor() as cursor:
         cursor.execute("SELECT status FROM user_objects WHERE object_name = 'TEST_COMPILE_FAIL_PRC' AND object_type = 'PROCEDURE'")
         status = cursor.fetchone()
         assert status[0] == 'INVALID'


@pytest.mark.database
def test_compile_warning(temp_sql_file, db_connection):
    if not db_connection: pytest.skip("Database connection not available")
    # This code might generate PLW-06002 depending on DB settings
    content = """
    CREATE OR REPLACE FUNCTION test_compile_warn_fnc RETURN NUMBER AS
      l_unused_variable NUMBER;
    BEGIN
      RETURN 42;
    END test_compile_warn_fnc;
    """
    file_path = temp_sql_file("test_warn.fnc", content)
    result = compile_object(file_path)

    # Warnings can be tricky, status might be 'success' or 'success_with_warnings'
    # depending on how USER_ERRORS is populated vs driver warnings (DPY-7000)
    assert result['status'] in ('success', 'success_with_warnings')
    assert result['object_name'] == 'TEST_COMPILE_WARN_FNC'
    # If warnings are reported, check messages
    if result['status'] == 'success_with_warnings':
        assert isinstance(result['messages'], list)
        assert len(result['messages']) > 0
        # Check for specific warning indicators (adjust codes as needed)
        assert any("Warning at Line" in msg or "PLW-" in msg or "DPY-7000" in msg for msg in result['messages'])

    # Object should still be VALID even with warnings
    with db_connection.cursor() as cursor:
         cursor.execute("SELECT status FROM user_objects WHERE object_name = 'TEST_COMPILE_WARN_FNC' AND object_type = 'FUNCTION'")
         status = cursor.fetchone()
         assert status[0] == 'VALID'


def test_compile_file_not_found():
    file_path = "non_existent_compile_test_file.sql"
    result = compile_object(file_path)
    assert result['status'] == 'error_reading_file'
    assert result['object_name'] is None # Name extraction won't happen
    assert result['file_path'] == file_path
    assert "File not found" in result['messages'][0]

def test_compile_empty_file(temp_sql_file):
     file_path = temp_sql_file("empty.sql", "")
     result = compile_object(file_path)
     assert result['status'] == 'error_reading_file'
     assert "File" in result['messages'][0] and "empty" in result['messages'][0]

def test_compile_slash_only_file(temp_sql_file):
     file_path = temp_sql_file("slash_only.sql", "/\n/\n")
     result = compile_object(file_path)
     assert result['status'] == 'error_reading_file'
     assert "contains no executable code" in result['messages'][0]


# Placeholder for db_connection fixture - copy from test_analyzer.py if needed
@pytest.fixture(scope="session")
def db_connection():
     pytest.skip("Database connection fixture not fully implemented or enabled.")
     yield None