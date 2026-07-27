from transpiler.codegen.dtrace_codegen import DTraceGenerator
from transpiler.codegen.ebpf_codegen import eBPFGenerator
from transpiler.codegen.windows_codegen import WindowsGenerator
from transpiler.mapper import MappedQuery


class EmitterError(Exception):
    pass

class QueryEmitter:
    def __init__(self):
        self.generators = {
            "linux": eBPFGenerator(),
            "macos": DTraceGenerator(),
            "windows": WindowsGenerator()
        }

    def emit(self, query: MappedQuery) -> str:
        generator = self.generators.get(query.platform)
        if not generator:
            raise EmitterError(f"No code generator found for platform '{query.platform}'")

        return generator.generate(query)
