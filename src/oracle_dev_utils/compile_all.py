import os
import argparse
import logging
from typing import List
import sys
from pathlib import Path

# Adjust sys.path to find the src directory if running the script directly
# This is often needed when scripts are outside the main package src layout
project_root = Path(__file__).resolve().parents[1]
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    # Now import from the package
    from oracle_dev_utils.compiler import compile_object
except ImportError as e:
    print(f"Error importing compiler module: {e}")
    print("Ensure you have installed the package ('pip install -e .') or that src path is correct.")
    sys.exit(1)


logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def find_sql_files(directory: str, extensions: List[str]) -> List[str]:
    """Finds files with specified extensions recursively."""
    found_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext.lower()) for ext in extensions):
                found_files.append(os.path.join(root, file))
    return found_files

def main():
    parser = argparse.ArgumentParser(description="Compile Oracle SQL/PL/SQL files found in a directory.")
    parser.add_argument("directory", help="Directory to search for files.")
    parser.add_argument(
        "--ext",
        nargs='+',
        default=['.sql', '.pks', '.pkb', '.pck', '.fnc', '.prc', '.trg', '.vw', '.tps', '.tpb'],
        help="File extensions to compile (default: .sql, .pks, .pkb, etc.)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging."
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not os.path.isdir(args.directory):
        logging.error(f"Error: Directory not found - {args.directory}")
        sys.exit(1)

    logging.info(f"Searching for files with extensions {args.ext} in '{args.directory}'...")
    files_to_compile = find_sql_files(args.directory, args.ext)

    if not files_to_compile:
        logging.warning("No files found to compile.")
        sys.exit(0)

    logging.info(f"Found {len(files_to_compile)} files to compile.")

    success_count = 0
    warning_count = 0
    error_count = 0

    # Ensure DB connection details are set in .env
    # The compile_object function handles the connection setup
    print("-" * 30)
    print("Starting compilation process...")
    print("Ensure DB connection details are set in '.env' file.")
    print("-" * 30)


    for file_path in sorted(files_to_compile): # Sort for consistent order
        logging.info(f"Compiling: {file_path}")
        result = compile_object(file_path) # compile_object handles its own logging

        status = result.get("status", "unknown")
        object_name = result.get("object_name", "N/A")
        messages = result.get("messages", [])

        print(f"--- Result for: {os.path.basename(file_path)} (Object: {object_name}) ---")
        print(f"Status: {status.upper()}")
        if messages:
            print("Messages:")
            for msg in messages:
                print(f"  - {msg}")
        print("-" * (len(os.path.basename(file_path)) + 20)) # Dynamic separator length

        if status == 'success':
            success_count += 1
        elif status == 'success_with_warnings':
            warning_count += 1
            success_count += 1 # Still technically compiled
        else:
            error_count += 1


    print("\n--- Compilation Summary ---")
    print(f"Total Files Processed: {len(files_to_compile)}")
    print(f"Successful Compilations: {success_count}")
    print(f"  (Including Warnings):  {warning_count}")
    print(f"Failed Compilations:   {error_count}")
    print("-" * 27)

    if error_count > 0:
        sys.exit(1) # Exit with error code if failures occurred
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()