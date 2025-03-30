# FILE: C:\Users\tke\OracleDevUtils\src\oracle_dev_utils\cli.py
import argparse
import logging
import sys
import os
import json
from typing import List, Optional
import traceback

try:
    from .compiler import compile_object
    from .analyzer import find_object_references_in_file, find_referencing_objects_in_db
    from . import __version__
except ImportError as e: # Catch the specific ImportError
    print(f"Error: Failed to import modules. Specific error: {e}")
    # Optionally print the full traceback for more details
    print("\n--- Traceback ---")
    traceback.print_exc()
    print("--- End Traceback ---\n")
    print("Make sure the package is installed correctly (`pip install -e .`) and dependencies are met.")
    import sys
    sys.exit(1) # Exit after showing the error

# Setup basic logging configuration for the CLI
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)


def handle_compile(args):
    """Handler for the 'compile' command."""
    log.info(f"Attempting to compile {len(args.files)} file(s)...")
    results = []
    overall_success = True
    for file_path in args.files:
        if not os.path.exists(file_path):
            log.error(f"File not found: {file_path}")
            results.append({"file_path": file_path, "status": "error_file_not_found", "messages": ["File not found."]})
            overall_success = False
            continue

        if not os.path.isfile(file_path):
            log.error(f"Path is not a file: {file_path}")
            results.append({"file_path": file_path, "status": "error_not_a_file", "messages": ["Path is not a file."]})
            overall_success = False
            continue

        log.debug(f"Processing file: {file_path}")
        result = compile_object(file_path)
        results.append(result)
        status = result.get("status", "unknown")
        log.info(f"Result for {os.path.basename(file_path)}: {status.upper()}")
        if status not in ('success', 'success_with_warnings'):
             overall_success = False
             # Log detailed errors if not verbose mode
             if not args.verbose and status.startswith('error'):
                 for msg in result.get("messages", []): log.error(f"  -> {msg}")
             elif not args.verbose and status == 'failed':
                 for msg in result.get("messages", []): log.warning(f"  -> {msg}") # Treat PL/SQL errors as warnings in summary unless verbose

    # Output results
    print("\n--- Compilation Results ---")
    for res in results:
        print(f"File: {res.get('file_path')}")
        print(f"  Status: {res.get('status', 'unknown').upper()}")
        if args.verbose or res.get('status') not in ('success', 'success_with_warnings'):
             messages = res.get('messages', [])
             if messages:
                 print("  Messages:")
                 for msg in messages:
                     print(f"    - {msg}")
        print("-" * 20)

    if not overall_success:
        log.error("One or more files failed to compile or encountered errors.")
        sys.exit(1)
    else:
        log.info("All requested files compiled successfully (possibly with warnings).")


def handle_analyze_file(args):
    """Handler for the 'analyze-file' command."""
    log.info(f"Performing static analysis for references in file: {args.file_path}")
    if not os.path.isfile(args.file_path):
        log.error(f"Error: File not found or is not a file: {args.file_path}")
        sys.exit(1)

    references = find_object_references_in_file(args.file_path)

    print(f"\n--- Static Analysis Results for: {args.file_path} ---")
    if references:
        print(f"Found {len(references)} potential object references:")
        # Sort for consistent output
        references.sort(key=lambda x: (x['line_number'], x['reference']))
        for ref in references:
            print(f"  - Line {ref['line_number']:<4}: {ref['reference']}")
    else:
        print("No potential object references found (or file is empty/unparsable).")


def handle_analyze_db(args):
    """Handler for the 'analyze-db' command."""
    log.info(f"Querying database for objects referencing: Name='{args.object_name}', Schema='{args.schema or 'CURRENT'}', Type='{args.type or 'ANY'}'")

    result = find_referencing_objects_in_db(
        referenced_object_name=args.object_name,
        referenced_schema=args.schema,
        referenced_type=args.type
    )

    status = result.get("status", "unknown")
    print(f"\n--- Database Dependency Analysis Results ---")
    print(f"Queried Object: Name='{result['referenced_object']['name']}', Schema='{result['referenced_object']['schema'] or 'N/A'}', Type='{result['referenced_object']['type'] or 'N/A'}'")
    print(f"Status: {status.upper()}")

    if status == 'success':
        referencing_objects = result.get('referencing_objects', [])
        if referencing_objects:
            print(f"\nFound {len(referencing_objects)} referencing objects:")
            # Sort for consistent output
            referencing_objects.sort(key=lambda x: (x['owner'], x['name'], x['type']))
            # Basic print - consider formatting as a table for better readability
            for obj in referencing_objects:
                 print(f"  - Owner: {obj['owner']:<20} Name: {obj['name']:<30} Type: {obj['type']:<15} DepType: {obj['dependency_type']}")
        else:
            print("\nNo referencing objects found in the database.")
    elif result.get('error_message'):
         log.error(f"Error during analysis: {result['error_message']}")
         sys.exit(1)
    else:
         log.error("Database analysis failed for an unknown reason.")
         sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Oracle Developer Utilities CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}') # Add version later
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable detailed DEBUG logging.")

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Compile Command ---
    parser_compile = subparsers.add_parser("compile", help="Compile one or more Oracle object files.")
    parser_compile.add_argument("files", nargs='+', help="Path(s) to the SQL/PL/SQL file(s) to compile.")
    parser_compile.set_defaults(func=handle_compile)

    # --- Analyze File Command ---
    parser_analyze_file = subparsers.add_parser("analyze-file", help="Analyze a file for potential object references (static analysis).")
    parser_analyze_file.add_argument("file_path", help="Path to the SQL/PL/SQL file to analyze.")
    parser_analyze_file.set_defaults(func=handle_analyze_file)

    # --- Analyze DB Command ---
    parser_analyze_db = subparsers.add_parser("analyze-db", help="Analyze database dependencies for a given object.")
    parser_analyze_db.add_argument("object_name", help="Name of the referenced object (e.g., MY_TABLE, MY_PACKAGE).")
    parser_analyze_db.add_argument("-s", "--schema", help="Schema/Owner of the referenced object (defaults to current schema).", default=None)
    parser_analyze_db.add_argument("-t", "--type", help="Type of the referenced object (e.g., TABLE, PACKAGE, VIEW).", default=None)
    parser_analyze_db.set_defaults(func=handle_analyze_db)

    args = parser.parse_args()

    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        log.debug("Verbose logging enabled.")
    else:
         logging.getLogger().setLevel(logging.INFO) # Default log level set above

    # Execute the handler function associated with the chosen command
    args.func(args)


if __name__ == "__main__":
    main()