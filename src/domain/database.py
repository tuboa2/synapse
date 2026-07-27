import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

class TelemetryDatabase:
    """
    DuckDB-backed in-memory datastore for telemetry state.
    Operations are executed in a thread pool to prevent event loop blocking.
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._conn = duckdb.connect(db_path)
        # DuckDB in-memory can be fast, but we enforce async non-blocking using an executor
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="DuckDBWorker")
        self._initialize_schema()
        logger.info(f"Initialized DuckDB telemetry datastore at {self.db_path}")

    def _initialize_schema(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS process_telemetry (
                timestamp TIMESTAMP,
                pid INTEGER,
                cpu_usage DOUBLE,
                memory_usage DOUBLE
            )
        """)

    async def insert_telemetry(self, pid: int, cpu: float, memory: float) -> None:
        """Asynchronously insert telemetry metrics."""
        query = "INSERT INTO process_telemetry VALUES (CURRENT_TIMESTAMP, ?, ?, ?)"
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._executor,
            self._conn.execute,
            query,
            [pid, cpu, memory]
        )

    async def get_recent_telemetry(self, limit: int = 100) -> list[tuple[Any, ...]]:
        """Asynchronously retrieve recent telemetry records."""
        query = "SELECT timestamp, pid, cpu_usage, memory_usage FROM process_telemetry ORDER BY timestamp DESC LIMIT ?"
        loop = asyncio.get_running_loop()

        def _fetch() -> list[tuple[Any, ...]]:
            return self._conn.execute(query, [limit]).fetchall()

        return await loop.run_in_executor(self._executor, _fetch)

    def close(self) -> None:
        """Shutdown thread pool and close database connection."""
        self._executor.shutdown(wait=True)
        self._conn.close()
        logger.info("DuckDB datastore closed")
