from abc import ABC, abstractmethod

from transpiler.mapper import MappedQuery


class CodeGenerator(ABC):
    @abstractmethod
    def generate(self, query: MappedQuery) -> str:
        """Takes a MappedQuery and returns the physical script/code as a string."""
        pass
