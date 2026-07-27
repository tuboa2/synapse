import pytest
import sqlglot

from transpiler.mapper import ASTMapper, MappedQuery, MappingError


@pytest.fixture
def tracepoint_matrix():
    return {
        "tables": {
            "syscalls": {
                "platforms": {
                    "linux": {
                        "probe_type": "tracepoint",
                        "probe_entry": "raw_syscalls:sys_enter",
                        "probe_exit": "raw_syscalls:sys_exit",
                        "fields": {
                            "pid": "bpf_get_current_pid_tgid() >> 32",
                            "comm": "bpf_get_current_comm",
                            "syscall_name": "args->id",
                            "latency_us": "latency_calculation_macro"
                        }
                    }
                }
            }
        }
    }

def test_map_valid_query_linux(tracepoint_matrix):
    sql = """
    SELECT pid, COUNT(*) as syscall_count
    FROM syscalls
    WHERE latency_us > 1000 AND syscall_name = 'read'
    """
    ast = sqlglot.parse_one(sql, read="duckdb")
    mapper = ASTMapper(tracepoint_matrix, platform="linux")
    mapped = mapper.map(ast)

    assert isinstance(mapped, MappedQuery)
    assert mapped.table == "syscalls"
    assert mapped.platform == "linux"
    assert mapped.probe_entry == "raw_syscalls:sys_enter"

    # Logical fields mapped to physical expressions
    assert mapped.select_fields == {"pid": "bpf_get_current_pid_tgid() >> 32"}

    # The where fields that were referenced
    assert mapped.where_fields == {
        "latency_us": "latency_calculation_macro",
        "syscall_name": "args->id"
    }

    # Aggregations extracted
    assert "COUNT" in mapped.aggregations

def test_map_unsupported_platform(tracepoint_matrix):
    sql = "SELECT pid FROM syscalls"
    ast = sqlglot.parse_one(sql, read="duckdb")

    mapper = ASTMapper(tracepoint_matrix, platform="windows")
    with pytest.raises(MappingError, match="Platform 'windows' not supported for table 'syscalls'"):
        mapper.map(ast)

def test_map_missing_field_in_matrix(tracepoint_matrix):
    sql = "SELECT unknown_field FROM syscalls"
    ast = sqlglot.parse_one(sql, read="duckdb")

    mapper = ASTMapper(tracepoint_matrix, platform="linux")
    with pytest.raises(MappingError, match="Field 'unknown_field' is not mapped for table 'syscalls' on platform 'linux'"):
        mapper.map(ast)
