from transpiler.mapper import MappedQuery
from transpiler.codegen.base import CodeGenerator

class DTraceGenerator(CodeGenerator):
    def generate(self, query: MappedQuery) -> str:
        # Dummy generator for DTrace
        return f"/* DTrace script for {query.table} */\n{query.probe_entry} {{ printf(\"Hit\"); }}"
