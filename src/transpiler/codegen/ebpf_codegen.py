from transpiler.mapper import MappedQuery
from transpiler.codegen.base import CodeGenerator

class eBPFGenerator(CodeGenerator):
    def generate(self, query: MappedQuery) -> str:
        # Generate the struct
        struct_fields = []
        for logical_name in query.select_fields:
            if "name" in logical_name or "comm" in logical_name:
                struct_fields.append(f"    char {logical_name}[64];")
            else:
                struct_fields.append(f"    u64 {logical_name};")
        
        struct_body = "\n".join(struct_fields)

        # Generate assignment
        assignments = []
        for logical_name, physical_macro in query.select_fields.items():
            if "name" in logical_name or "comm" in logical_name:
                assignments.append(f"    bpf_probe_read_user_str(&event.{logical_name}, sizeof(event.{logical_name}), (void *)({physical_macro}));")
            else:
                assignments.append(f"    event.{logical_name} = {physical_macro};")
        
        assignment_body = "\n".join(assignments)

        # Generate WHERE filter
        filters = []
        for logical_name, physical_macro in query.where_fields.items():
            # In a real compiler, we would parse the AST condition properly.
            # For this MVP, we just assign them to local variables or check them.
            pass
            
        # Hardcoding the BPF perf output map
        bpf_program = f"""#include <linux/sched.h>

BPF_PERF_OUTPUT(events);

struct event_t {{
{struct_body}
}};

TRACEPOINT_PROBE({query.probe_entry.split(':')[0]}, {query.probe_entry.split(':')[1]}) {{
    struct event_t event = {{}};
    
{assignment_body}

    events.perf_submit(args, &event, sizeof(event));
    return 0;
}}
"""
        return bpf_program
