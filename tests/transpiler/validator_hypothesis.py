import pytest
import sqlglot
from hypothesis import given
from hypothesis import strategies as st

from transpiler.validator import ASTValidator


@pytest.fixture
def validator():
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

@given(
    st.lists(st.sampled_from(["COUNT", "SUM", "AVG", "MIN", "MAX"]), min_size=1),
    st.lists(st.sampled_from(["pid", "comm", "syscall_name", "latency_us"]), min_size=1),
    st.sampled_from(["pid", "comm", "syscall_name", "latency_us"])
)
def test_valid_sql_property(aggregations, select_cols, where_col):
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
    validator = ASTValidator(schema)
    # Construct a valid SQL string
    aggs = [f"{agg}({col})" for agg, col in zip(aggregations, select_cols, strict=False)]
    select_clause = ", ".join(aggs + select_cols)
    sql = f"SELECT {select_clause} FROM syscalls WHERE {where_col} = 'test'"

    ast = sqlglot.parse_one(sql, read="duckdb")
    # Should never raise ValidationError for these valid combinations
    validator.validate(ast)
