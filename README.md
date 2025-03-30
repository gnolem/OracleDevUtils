# OracleDevUtils

A collection of utilities for Oracle development, including object compilation and dependency analysis.

## Features

*   Compile Oracle objects (Packages, Procedures, Functions, Views, etc.) from files.
*   Analyze PL/SQL code for potential object references (static analysis).
*   Query database metadata (ALL_DEPENDENCIES) to find actual object dependencies (finds objects that *use* a specific target object).
*   Command-line interface for easy execution.

## Setup

1.  **Clone the repository.**
    ```bash
    git clone <your-repository-url>
    cd OracleDevUtils
    ```
2.  **Create and activate a virtual environment:**
    *   Make sure you have Python 3 installed.
    *   Run the following in your command prompt (`cmd`) from the `OracleDevUtils` directory:
    ```bash
    python -m venv .venv
    .\.venv\Scripts\activate
    ```
    *   You should see `(.venv)` prefixed on your command prompt line, indicating the virtual environment is active.

3.  **Install dependencies (including the project in editable mode):**
    *   While the virtual environment is active, run:
    ```bash
    pip install -e .[dev]
    ```
    *   *(The `[dev]` installs testing and linting tools. Use `pip install -e .` for just runtime dependencies if preferred. The `-e .` makes the `oracle-dev-tool` command available).*

4.  **Configure database connection:**
    *   Copy the example environment file:
        ```bash
        copy .env.example .env
        ```
    *   **Edit the `.env` file** using a text editor (like Notepad, VS Code, etc.).
    *   Fill in your database credentials (`DB_USER`, `DB_PASSWORD`).
    *   Provide **either** `DB_TNS_ALIAS` (if you use `tnsnames.ora`) **or** `DB_DSN` (if you use an Easy Connect string or full DSN).
    *   If your Oracle Instant Client libraries (`oci.dll` etc.) are **not** in your system's PATH, uncomment and set `ORACLE_LIB_DIR` to the directory containing them.
    *   If your `tnsnames.ora` file is **not** in the default location or specified by the system environment variable `TNS_ADMIN`, uncomment and set `TNS_ADMIN` to the directory containing it.
    *   **Save the `.env` file.** The application will automatically load these settings.

## Usage

**Important:** Ensure your virtual environment is activated (`.\.venv\Scripts\activate`) before running these commands.

### Command Line Interface (`oracle-dev-tool`)

The tool provides a command-line interface. Run with `-h` or `--help` to see all available commands and their options:

```bash
oracle-dev-tool -h
oracle-dev-tool compile -h
oracle-dev-tool analyze-file -h
oracle-dev-tool analyze-db -h
```

### Compiling Objects (`compile`)

This command connects to the database (using details from `.env`) and attempts to compile one or more Oracle object files.

**Syntax:**

```bash
oracle-dev-tool compile <file_path_1> [file_path_2 ...] [--stop-on-error]
```

**Examples:**

1.  **Compile a single package body:**
    ```bash
    oracle-dev-tool compile "C:\path\to\your\project\packages\my_package_body.pkb"
    ```
    *(Use quotes if your path contains spaces)*

2.  **Compile multiple files (a package spec and body):**
    ```bash
    oracle-dev-tool compile specs\my_package.pks bodies\my_package.pkb
    ```

3.  **Compile all `.sql` files in a directory (using shell wildcards):**
    *   *Note: `cmd.exe` wildcard support can be limited. You might need to list files explicitly or use `for` loops in `cmd`. The example below works best in shells like Git Bash, PowerShell, or Linux/macOS terminals.*
    ```bash
    # Example for shells supporting globbing:
    oracle-dev-tool compile views\*.sql
    ```
    *(Check if your specific shell expands the `*` correctly)*

**Output:** Prints the status (success or failure) for each file compilation attempt, including any Oracle compilation errors.

**Requires:** Database connection configured in `.env`.

### Static File Analysis (`analyze-file`)

This command analyzes a PL/SQL file *without* connecting to the database. It scans the code for patterns that look like database object references (e.g., `schema.object`, `table_name`, `package.function`).

**Syntax:**

```bash
oracle-dev-tool analyze-file <file_path>
```

**Example:**

```bash
oracle-dev-tool analyze-file "C:\path\to\your\project\procedures\process_data.prc"
```

**Output:** Lists the potential object references found, along with the line number where each reference occurs in the file. This is based on pattern matching and may include local variables or keywords if the patterns overlap.

**Requires:** Does **not** require database connection.

### Database Dependency Analysis (`analyze-db`)

This command connects to the database (using details from `.env`) and queries `ALL_DEPENDENCIES` to find objects that **reference** (depend on) the specified target object.

**Syntax:**

```bash
oracle-dev-tool analyze-db <object_name> [--schema <schema_name>] [--type <object_type>]
```

*   `<object_name>`: The name of the object you want to find dependents for (e.g., `MY_TABLE`, `MY_PACKAGE`). Case-insensitive.
*   `--schema`: (Optional) The owner/schema of the target object. If omitted, defaults based on connection settings or current schema. Case-insensitive.
*   `--type`: (Optional) The type of the target object (e.g., `TABLE`, `VIEW`, `PACKAGE`, `FUNCTION`). Helps narrow down the search. Case-insensitive.

**Examples:**

1.  **Find objects referencing the table `EMPLOYEES` owned by `HR`:**
    ```bash
    oracle-dev-tool analyze-db EMPLOYEES --schema HR --type TABLE
    ```

2.  **Find objects referencing the package `MY_APP_PKG` (assuming it's in your connected schema):**
    ```bash
    oracle-dev-tool analyze-db MY_APP_PKG --type PACKAGE
    ```

3.  **Find objects referencing an object named `COMMON_UTILITY` (could be package, type, etc.) in any schema your user can see:**
    ```bash
    oracle-dev-tool analyze-db COMMON_UTILITY
    ```
    *(Note: Results might be broad without schema/type)*

**Output:** Lists the objects found in the database (`OWNER`, `NAME`, `TYPE`) that depend on the target object you specified.

**Requires:** Database connection configured in `.env`.

---

*Remember to consult the `--help` option for the most up-to-date commands and arguments.*
```