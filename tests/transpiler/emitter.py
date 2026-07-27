import pytest

from transpiler.emitter import EmitterError, QueryEmitter
from transpiler.mapper import MappedQuery


def test_emit_linux():
    # Setup a mapped query
    query = MappedQuery(
        table="syscalls",
        platform="linux",
        probe_type="tracepoint",
        probe_entry="raw_syscalls:sys_enter",
        probe_exit="raw_syscalls:sys_exit",
        select_fields={
            "pid": "bpf_get_current_pid_tgid() >> 32",
            "comm": "bpf_get_current_comm"
        },
        where_fields={
            "latency_us": "latency_calculation_macro"
        },
        aggregations=["COUNT"]
    )

    emitter = QueryEmitter()
    code = emitter.emit(query)

    assert "BPF_PERF_OUTPUT(events);" in code
    assert "struct event_t {" in code
    assert "u64 pid;" in code
    assert "char comm[64];" in code
    assert "TRACEPOINT_PROBE(raw_syscalls, sys_enter) {" in code
    assert "event.pid = bpf_get_current_pid_tgid() >> 32;" in code
    assert "bpf_probe_read_user_str(&event.comm, sizeof(event.comm), (void *)(bpf_get_current_comm));" in code
    assert "events.perf_submit(args, &event, sizeof(event));" in code

def test_emit_unsupported_platform():
    query = MappedQuery(
        table="syscalls",
        platform="unknown",
        probe_type="tracepoint",
        probe_entry="",
        probe_exit="",
        select_fields={},
        where_fields={},
        aggregations=[]
    )

    emitter = QueryEmitter()
    with pytest.raises(EmitterError, match="No code generator found for platform 'unknown'"):
        emitter.emit(query)
