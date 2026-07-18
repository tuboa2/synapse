import pytest
import sqlglot
from synapse.transpiler.validator import ASTValidator, ValidationError

@pytest.fixture
def validator():
    # Provide a minimal mock schema for testing or load the actual one
    # For now, we will use a small dictionary simulating the loaded registry
    schema = {
        "tables": {
            "syscalls": {
                "columns": {
                    "pid": "int",
                    "comm": "string",
                    "syscall_name": "string",
                    "latency_us": "int"
                }
            }
        },
        "allowed_functions": ["COUNT", "SUM", "AVG", "MIN", "MAX"]
    }
    return ASTValidator(schema)

def test_valid_query(validator):
    sql = """
    SELECT pid, comm, COUNT(*) as syscall_count
    FROM syscalls
    WHERE syscall_name = 'read' AND latency_us > 1000
    GROUP BY pid, comm
    HAVING COUNT(*) > 50
    """
    ast = sqlglot.parse_one(sql, read="duckdb")
    # Should not raise an exception
    validator.validate(ast)

def test_invalid_table(validator):
    sql = "SELECT pid FROM unknown_table"
    ast = sqlglot.parse_one(sql, read="duckdb")
    with pytest.raises(ValidationError, match="Table 'unknown_table' is not allowed"):
        validator.validate(ast)

def test_invalid_column(validator):
    sql = "SELECT unknown_col FROM syscalls"
    ast = sqlglot.parse_one(sql, read="duckdb")
    with pytest.raises(ValidationError, match="Column 'unknown_col' not found in table 'syscalls'"):
        validator.validate(ast)

def test_invalid_where_column(validator):
    sql = "SELECT pid FROM syscalls WHERE unknown_col = 1"
    ast = sqlglot.parse_one(sql, read="duckdb")
    with pytest.raises(ValidationError, match="Column 'unknown_col' not found in table 'syscalls'"):
        validator.validate(ast)

def test_invalid_function(validator):
    sql = "SELECT SYSTEM('ls') FROM syscalls"
    ast = sqlglot.parse_one(sql, read="duckdb")
    with pytest.raises(ValidationError, match="Function 'SYSTEM' is not allowed"):
        validator.validate(ast)

def test_no_subqueries_allowed(validator):
    sql = "SELECT pid FROM (SELECT pid FROM syscalls)"
    ast = sqlglot.parse_one(sql, read="duckdb")
    with pytest.raises(ValidationError, match="Subqueries are not supported"):
        validator.validate(ast)

def test_no_joins_allowed(validator):
    sql = "SELECT a.pid FROM syscalls a JOIN syscalls b ON a.pid = b.pid"
    ast = sqlglot.parse_one(sql, read="duckdb")
    with pytest.raises(ValidationError, match="JOIN operations are not supported"):
        validator.validate(ast)
