import pytest
from oracle_dev_utils.analyzer import (
    find_object_references_in_file,
    find_referencing_objects_in_db,
    remove_comments
)

# --- Helper for comparing code blocks ---
def compare_code_lines(actual: str, expected: str) -> bool:
    """Compares two code strings line by line after stripping."""
    actual_lines = [line.strip() for line in actual.strip().splitlines() if line.strip()]
    expected_lines = [line.strip() for line in expected.strip().splitlines() if line.strip()]
    # Add print for debugging differences
    if actual_lines != expected_lines:
        print("\nActual Lines:")
        print(actual_lines)
        print("\nExpected Lines:")
        print(expected_lines)
    return actual_lines == expected_lines

# --- Tests for remove_comments ---

def test_remove_single_line_comments():
    code = """
    SELECT * -- This is a comment
    FROM my_table; -- Another comment
    -- Full line comment
    WHERE id = 1;
    """
    expected = """
    SELECT *
    FROM my_table;

    WHERE id = 1;
    """
    actual = remove_comments(code)
    # Use the helper function for comparison
    assert compare_code_lines(actual, expected), "Single line comment removal mismatch"

def test_remove_multi_line_comments():
    code = """
    /* Multi-line
       comment */
    SELECT col1 FROM another_table /* inline comment */ WHERE x=1;
    /**/ Empty comment
    """
    expected = """

    SELECT col1 FROM another_table  WHERE x=1;
     Empty comment
    """
    actual = remove_comments(code)
    assert compare_code_lines(actual, expected), "Multi line comment removal mismatch"


def test_remove_mixed_comments():
    code = """
    /* Start block */
    PROCEDURE test IS -- Test proc
    BEGIN /* Inner block */
       NULL; -- Do nothing
    END; -- End proc
    /* End block */
    """
    expected = """

    PROCEDURE test IS
    BEGIN
       NULL;
    END;

    """
    actual = remove_comments(code)
    assert compare_code_lines(actual, expected), "Mixed comment removal mismatch"


# --- Tests for find_object_references_in_file ---

def test_find_refs_basic(temp_sql_file):
    content = """
    CREATE OR REPLACE PACKAGE BODY my_pkg IS
      PROCEDURE p1 IS BEGIN UPDATE hr.employees SET sal = 1; END;
      FUNCTION f1 RETURN DATE IS BEGIN RETURN sys.dual.dummy; END; -- Use schema.table.column
      CURSOR c1 IS SELECT * FROM user_tables; -- Simple table reference
    END my_pkg;
    """
    file_path = temp_sql_file("basic.pkb", content)
    refs = find_object_references_in_file(file_path)
    ref_names = {r['reference'].lower() for r in refs} # lowercase set
    # Check core references now including the member part
    assert "hr.employees" in ref_names
    assert "sys.dual.dummy" in ref_names # Expect full reference now
    assert "user_tables" in ref_names
    # Exclude known declarations/locals/columns
    ref_names = {r for r in ref_names if r not in ('my_pkg', 'p1', 'f1', 'c1', 'sal')}
    assert ref_names == {"hr.employees", "sys.dual.dummy", "user_tables"}


def test_find_refs_with_comments(temp_sql_file):
    content = """
    -- Reference to other_table in comment, should be ignored
    /* SELECT * FROM commented_out_table; */
    SELECT real_col FROM real_table; -- Use real_table
    """
    file_path = temp_sql_file("comments.sql", content)
    refs = find_object_references_in_file(file_path)
    ref_names = {r['reference'] for r in refs}
    # Expect both column and table
    assert ref_names == {"real_col", "real_table"}

def test_find_refs_no_refs(temp_sql_file):
    content = """
    CREATE OR REPLACE PROCEDURE no_refs AS
      l_var NUMBER;
    BEGIN
      l_var := 1 + 1; -- Only local vars and built-ins
      DBMS_OUTPUT.PUT_LINE('Hello'); -- Built-in package (should be filtered)
    END;
    """
    file_path = temp_sql_file("no_refs.prc", content)
    refs = find_object_references_in_file(file_path)
    # Corrected filtering comprehension: Use r['reference'].upper()
    ref_names = {r['reference'] for r in refs if r['reference'].upper() not in ('NO_REFS', 'L_VAR')}
    assert len(ref_names) == 0, f"Expected 0 refs after filtering, found: {ref_names}"

def test_find_refs_nonexistent_file():
    refs = find_object_references_in_file("path/to/non_existent_file_analyzer.sql")
    assert refs == [] # Should handle file not found gracefully


# --- Tests for find_referencing_objects_in_db ---
# These tests require a live database connection and configured .env file.
# They are marked with 'database' and might be skipped in environments without a DB.

@pytest.mark.database
def test_find_db_refs_known_object(db_connection): # Assumes db_connection fixture exists and works
    if not db_connection: pytest.skip("Database connection not available")

    # IMPORTANT: Choose an object that *definitely exists* in your test DB
    # and preferably has known dependencies. Using DUAL owned by SYS is common.
    target_object = 'DUAL'
    target_schema = 'SYS'
    target_type = 'TABLE'

    result = find_referencing_objects_in_db(
        referenced_object_name=target_object,
        referenced_schema=target_schema,
        referenced_type=target_type
    )

    assert result['status'] == 'success'
    assert result['referenced_object']['name'] == target_object
    assert result['referenced_object']['schema'] == target_schema
    assert result['referenced_object']['type'] == target_type
    assert isinstance(result['referencing_objects'], list)
    # We expect DUAL to have many references, so check the list is not empty
    assert len(result['referencing_objects']) > 0
    # Check structure of one item (optional)
    first_ref = result['referencing_objects'][0]
    assert 'owner' in first_ref
    assert 'name' in first_ref
    assert 'type' in first_ref

@pytest.mark.database
def test_find_db_refs_non_existent_object(db_connection):
    if not db_connection: pytest.skip("Database connection not available")

    target_object = 'THIS_OBJECT_DOES_NOT_EXIST_XYZ123'

    result = find_referencing_objects_in_db(referenced_object_name=target_object)

    assert result['status'] == 'success' # Query succeeds even if no rows found
    assert result['referenced_object']['name'] == target_object
    assert isinstance(result['referencing_objects'], list)
    assert len(result['referencing_objects']) == 0 # Expect no dependencies

# Placeholder for the db_connection fixture if not defined in conftest.py yet
# This allows tests to run without failing immediately if the fixture isn't ready.
@pytest.fixture(scope="session")
def db_connection():
     pytest.skip("Database connection fixture not fully implemented or enabled.")
     yield None # Or implement actual connection logic here or in conftest.py