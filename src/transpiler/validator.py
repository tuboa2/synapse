from typing import Any

from sqlglot import expressions as exp


class ValidationError(Exception):
    pass

class ASTValidator:
    def __init__(self, schema_registry: dict[str, Any]):
        self.schema = schema_registry

    def validate(self, ast: exp.Expression) -> None:
        if not ast:
            return

        # Deny subqueries
        if list(ast.find_all(exp.Subquery)):
            raise ValidationError("Subqueries are not supported")

        # Deny joins
        if list(ast.find_all(exp.Join)):
            raise ValidationError("JOIN operations are not supported")

        # Extract FROM table
        tables = list(ast.find_all(exp.Table))
        if not tables:
            raise ValidationError("Query must contain a FROM clause")

        table_name = tables[0].name

        if table_name not in self.schema.get("tables", {}):
            raise ValidationError(f"Table '{table_name}' is not allowed")

        allowed_columns = self.schema["tables"][table_name].get("columns", {})
        allowed_functions = set(self.schema.get("allowed_functions", []))

        # Check all column references
        for column in ast.find_all(exp.Column):
            col_name = column.name
            # If it's a star (*) like COUNT(*), col_name might be empty, handled by Star expression
            if not col_name:
                continue

            if col_name not in allowed_columns:
                raise ValidationError(f"Column '{col_name}' not found in table '{table_name}'")

        # Check all functions (aggregations)
        for func in ast.find_all(exp.Func):
            if isinstance(func, exp.Binary):
                continue

            if isinstance(func, exp.Anonymous):
                func_name = func.name.upper()
            else:
                func_name = func.sql_name().upper()

            if func_name not in allowed_functions:
                raise ValidationError(f"Function '{func_name}' is not allowed")
