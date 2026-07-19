from transpiler.mapper import MappedQuery
from transpiler.codegen.base import CodeGenerator

class WindowsGenerator(CodeGenerator):
    def generate(self, query: MappedQuery) -> str:
        # Dummy generator for Windows
        return f"# Windows ETW/psutil polling logic for {query.table}\npass"
