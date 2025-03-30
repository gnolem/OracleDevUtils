__version__ = "0.1.0"
from .compiler import compile_object, extract_object_name_from_code
from .analyzer import find_object_references_in_file, find_referencing_objects_in_db
from .db_connection import connect, get_connection_details, init_oracle_client_if_needed
from . import db_config # Make config constants accessible if needed

# Define what '*' imports (optional, but good practice)
__all__ = [
    'compile_object',
    'extract_object_name_from_code',
    'find_object_references_in_file',
    'find_referencing_objects_in_db',
    'connect',
    'get_connection_details',
    'init_oracle_client_if_needed',
    'db_config',
]

# You might want to set up package-level logging here if desired
import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())