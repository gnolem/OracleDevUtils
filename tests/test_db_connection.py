import pytest
import os
import oracledb
from unittest.mock import patch, MagicMock
from oracle_dev_utils import db_connection

# Import functions and *MODULE* to access globals for patching state
import oracle_dev_utils.db_connection as db_connection_module
from oracle_dev_utils.db_connection import (
    # init_oracle_client_if_needed, # We'll call via module
    get_connection_details,
    connect,
    # _oracle_client_initialized, # Access via module
    # _initialization_error     # Access via module
)

# --- Fixtures ---
@pytest.fixture(autouse=True)
def manage_environment_variables():
    """Fixture to save and restore environment variables around tests."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)

def test_get_connection_details_success_tns():
    os.environ["DB_USER"] = "testuser"
    os.environ["DB_PASSWORD"] = "testpass"
    os.environ["DB_TNS_ALIAS"] = "MYTNSALIAS"
    os.environ.pop("DB_DSN", None) # Ensure DSN is not set

    details = get_connection_details()
    assert details == {"user": "testuser", "password": "testpass", "dsn": "MYTNSALIAS"}

def test_get_connection_details_success_dsn():
    os.environ["DB_USER"] = "testuser2"
    os.environ["DB_PASSWORD"] = "testpass2"
    os.environ["DB_DSN"] = "localhost:1521/myservice"
    os.environ.pop("DB_TNS_ALIAS", None) # Ensure TNS is not set

    details = get_connection_details()
    assert details == {"user": "testuser2", "password": "testpass2", "dsn": "localhost:1521/myservice"}

def test_get_connection_details_prefer_tns():
    os.environ["DB_USER"] = "testuser3"
    os.environ["DB_PASSWORD"] = "testpass3"
    os.environ["DB_TNS_ALIAS"] = "PREFER_TNS"
    os.environ["DB_DSN"] = "should_be_ignored"

    details = get_connection_details()
    assert details == {"user": "testuser3", "password": "testpass3", "dsn": "PREFER_TNS"}

def test_get_connection_details_missing_user():
    os.environ["DB_PASSWORD"] = "testpass"
    os.environ["DB_TNS_ALIAS"] = "MYTNSALIAS"
    os.environ.pop("DB_USER", None)
    with pytest.raises(ValueError, match="Missing required environment variable: DB_USER"):
        get_connection_details()

def test_get_connection_details_missing_password():
    os.environ["DB_USER"] = "testuser"
    os.environ["DB_TNS_ALIAS"] = "MYTNSALIAS"
    os.environ.pop("DB_PASSWORD", None)
    with pytest.raises(ValueError, match="Missing required environment variable: DB_PASSWORD"):
        get_connection_details()

def test_get_connection_details_missing_dsn_and_tns():
    os.environ["DB_USER"] = "testuser"
    os.environ["DB_PASSWORD"] = "testpass"
    os.environ.pop("DB_TNS_ALIAS", None)
    os.environ.pop("DB_DSN", None)
    with pytest.raises(ValueError, match="Missing required environment variable: Set either DB_TNS_ALIAS or DB_DSN"):
        get_connection_details()


# --- Test init_oracle_client_if_needed ---
# These tests mock the oracledb.init_oracle_client call

@pytest.fixture
def mock_oracledb_init():
    """Mock the oracledb.init_oracle_client function *within db_connection*."""
    with patch("oracle_dev_utils.db_connection.oracledb.init_oracle_client") as mock_init:
        yield mock_init

@pytest.fixture(autouse=True)
def reset_init_flag():
    """Reset the internal initialization flag before/after each test."""
    # Reset before test
    db_connection._oracle_client_initialized = False
    db_connection._initialization_error = None
    yield # Test runs here
    # Optional: Reset after test as well (good practice)
    db_connection._oracle_client_initialized = False
    db_connection._initialization_error = None

@pytest.fixture(autouse=True)
def reset_init_flag_and_error():
    """Reset the internal initialization flag AND error before each test."""
    # Use patch.object to modify the state within the db_connection_module
    with patch.object(db_connection_module, '_oracle_client_initialized', False, create=True), \
         patch.object(db_connection_module, '_initialization_error', None, create=True):
        yield

@pytest.fixture
def mock_os_path_isdir():
     # Patch within the db_connection module
    with patch("oracle_dev_utils.db_connection.os.path.isdir") as mock_isdir:
        yield mock_isdir


def test_init_client_first_call(mock_oracledb_init, mock_os_path_isdir):
    # State is reset by reset_init_flag_and_error fixture
    mock_os_path_isdir.return_value = True
    # Call the function via the imported module
    db_connection_module.init_oracle_client_if_needed()
    mock_oracledb_init.assert_called_once()
    # Check state directly from the module
    assert db_connection_module._oracle_client_initialized is True
    assert db_connection_module._initialization_error is None


def test_init_client_subsequent_call(mock_oracledb_init, mock_os_path_isdir):
    # Set initial state to already initialized
    with patch.object(db_connection_module, '_oracle_client_initialized', True):
        # Call the function
        db_connection_module.init_oracle_client_if_needed()

        # Assert the underlying init was NOT called again
        mock_oracledb_init.assert_not_called()
        # State should *still* be initialized *within* the patch context
        assert db_connection_module._oracle_client_initialized is True


def test_init_client_uses_env_vars(mock_oracledb_init, mock_os_path_isdir):
    # State is reset by fixture
    os.environ["ORACLE_LIB_DIR"] = "/env/lib/path"
    os.environ["TNS_ADMIN"] = "/env/tns/path"
    def mock_isdir_side_effect(path): return path in ["/env/lib/path", "/env/tns/path"]
    mock_os_path_isdir.side_effect = mock_isdir_side_effect

    db_connection_module.init_oracle_client_if_needed()

    mock_oracledb_init.assert_called_once_with(lib_dir="/env/lib/path", config_dir="/env/tns/path")
    assert db_connection_module._oracle_client_initialized is True


def test_init_client_failure(mock_oracledb_init, mock_os_path_isdir):
    # State is reset by fixture
    mock_os_path_isdir.return_value = True
    # Configure mock to raise error during the *actual* init call
    mock_oracledb_init.side_effect = oracledb.DatabaseError("OCI Init Failed")

    # Assert that calling our function raises the expected RuntimeError
    with pytest.raises(RuntimeError, match="Failed to initialize Oracle Client during attempt: OCI Init Failed"):
        db_connection_module.init_oracle_client_if_needed()

    # Check the final state
    assert db_connection_module._oracle_client_initialized is False
    assert isinstance(db_connection_module._initialization_error, oracledb.DatabaseError)


def test_init_client_previously_failed(mock_oracledb_init):
    # Manually set the 'previously failed' state
    previous_error = RuntimeError("Previous failure")
    with patch.object(db_connection_module, '_oracle_client_initialized', False), \
         patch.object(db_connection_module, '_initialization_error', previous_error):

        # Expect the specific RuntimeError because _initialization_error is set
        with pytest.raises(RuntimeError, match="Oracle Client initialization previously failed.") as excinfo:
             db_connection_module.init_oracle_client_if_needed()

        # Optional: Check that the cause was the original error
        assert excinfo.value.__cause__ is previous_error

        # Ensure the underlying init was NOT called because it raised early
        mock_oracledb_init.assert_not_called()


# --- Test connect ---

@pytest.fixture
def mock_oracledb_connect():
     """Mock the oracledb.connect function *within db_connection*."""
     # ... mock_conn setup remains the same ...
     mock_conn = MagicMock(spec=oracledb.Connection)
     mock_conn.version = "19.0.0"; mock_conn.encoding = "UTF-8"
     mock_conn.username = "mockuser"; mock_conn.dsn = "mockdsn"
     with patch("oracle_dev_utils.db_connection.oracledb.connect", return_value=mock_conn) as mock_connect:
         yield mock_connect


def test_connect_success(mock_oracledb_init, mock_oracledb_connect, mock_os_path_isdir):
    # State reset by fixture
    mock_os_path_isdir.return_value = True
    os.environ["DB_USER"] = "testuser"; os.environ["DB_PASSWORD"] = "testpass"
    os.environ["DB_TNS_ALIAS"] = "MYTNSALIAS"

    conn = connect() # Uses the connect function directly

    # Verify init was called (via the module's state check within connect)
    mock_oracledb_init.assert_called_once()
    # Verify oracledb.connect was called
    mock_oracledb_connect.assert_called_once_with(user="testuser", password="testpass", dsn="MYTNSALIAS")
    assert conn is not None
    assert conn.username == "mockuser"
    assert db_connection_module._oracle_client_initialized is True # Check side effect


def test_connect_init_failure(mock_oracledb_init, mock_oracledb_connect, mock_os_path_isdir):
    # State reset by fixture
    mock_os_path_isdir.return_value = True
    # Make the init call fail
    mock_oracledb_init.side_effect = RuntimeError("Init Failed During Connect")

    # Calling connect should now raise the RuntimeError from init
    with pytest.raises(RuntimeError, match="Init Failed During Connect"):
        connect()

    # Verify oracledb.connect was NOT called
    mock_oracledb_connect.assert_not_called()
    assert db_connection_module._oracle_client_initialized is False # Check side effect


def test_connect_details_failure(mock_oracledb_init, mock_oracledb_connect, mock_os_path_isdir):
    mock_os_path_isdir.return_value = True # Assume init would succeed if called
    os.environ.pop("DB_USER", None) # Cause get_connection_details to fail
    with pytest.raises(ValueError, match="Missing required environment variable: DB_USER"):
        connect()
    mock_oracledb_connect.assert_not_called()


def test_connect_db_failure(mock_oracledb_init, mock_oracledb_connect, mock_os_path_isdir):
    mock_os_path_isdir.return_value = True # Assume init succeeds
    mock_oracledb_connect.side_effect = oracledb.DatabaseError("ORA-01017: invalid username/password")
    os.environ["DB_USER"] = "testuser"; os.environ["DB_PASSWORD"] = "wrongpass"
    os.environ["DB_TNS_ALIAS"] = "MYTNSALIAS"

    with pytest.raises(oracledb.DatabaseError, match="ORA-01017"):
        connect()

    mock_oracledb_init.assert_called_once() # Init should have been called
    mock_oracledb_connect.assert_called_once() # Connect was called but failed
    assert db_connection_module._oracle_client_initialized is True # Init succeeded

# Note: Testing the actual database connection requires a live DB and is often
# done in integration tests marked appropriately (e.g., @pytest.mark.database)
# and potentially using a dedicated test fixture for connection setup/teardown.
# The module-level __main__ block provides a basic live test if needed.