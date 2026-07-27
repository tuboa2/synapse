import dataclasses
from typing import Any

from sqlglot import expressions as exp


class MappingError(Exception):
    pass

@dataclasses.dataclass
class MappedQuery:
    table: str
    platform: str
    probe_type: str
    probe_entry: str
    probe_exit: str
    select_fields: dict[str, str]
    where_fields: dict[str, str]
    aggregations: list[str]

class ASTMapper:
    def __init__(self, tracepoint_matrix: dict[str, Any], platform: str):
        self.matrix = tracepoint_matrix
        self.platform = platform

    def map(self, ast: exp.Expression) -> MappedQuery:
        # Extract table
        tables = list(ast.find_all(exp.Table))
        if not tables:
            raise MappingError("No table found in query")
        table_name = tables[0].name

        # Check matrix for table
        table_config = self.matrix.get("tables", {}).get(table_name)
        if not table_config:
            raise MappingError(f"Table '{table_name}' not found in tracepoint matrix")

        # Check platform support
        platform_config = table_config.get("platforms", {}).get(self.platform)
        if not platform_config:
            raise MappingError(f"Platform '{self.platform}' not supported for table '{table_name}'")

        physical_fields = platform_config.get("fields", {})

        select_fields: dict[str, str] = {}
        where_fields: dict[str, str] = {}
        aggregations: list[str] = []

        # Find columns in SELECT
        # sqlglot parsed ASTs have an `args` dict containing the top-level clauses
        select_clause = ast.args.get("expressions", [])
        for expr in select_clause:
            for col in expr.find_all(exp.Column):
                col_name = col.name
                if col_name:
                    if col_name not in physical_fields:
                        raise MappingError(f"Field '{col_name}' is not mapped for table '{table_name}' on platform '{self.platform}'")
                    select_fields[col_name] = physical_fields[col_name]

        # Find columns in WHERE
        where_clause = ast.args.get("where")
        if where_clause:
            for col in where_clause.find_all(exp.Column):
                col_name = col.name
                if col_name:
                    if col_name not in physical_fields:
                        raise MappingError(f"Field '{col_name}' is not mapped for table '{table_name}' on platform '{self.platform}'")
                    where_fields[col_name] = physical_fields[col_name]

        # Find aggregations
        for func in ast.find_all(exp.AggFunc):
            aggregations.append(func.sql_name().upper())

        return MappedQuery(
            table=table_name,
            platform=self.platform,
            probe_type=platform_config.get("probe_type", ""),
            probe_entry=platform_config.get("probe_entry", ""),
            probe_exit=platform_config.get("probe_exit", ""),
            select_fields=select_fields,
            where_fields=where_fields,
            aggregations=aggregations
        )
