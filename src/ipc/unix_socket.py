import asyncio
import contextlib
import json
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

from .base import IPCClient, IPCServer

logger = logging.getLogger(__name__)

class UnixSocketServer(IPCServer):
    def __init__(
        self,
        socket_path: str,
        message_handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
    ) -> None:
        self.socket_path = socket_path
        self.message_handler = message_handler
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        # Ensure stale socket file is removed before binding
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except OSError as e:
                logger.error(f"Failed to remove stale socket {self.socket_path}: {e}")

        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.socket_path
        )
        logger.info(f"Unix IPC Server listening on {self.socket_path}")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer_name = writer.get_extra_info('peername') or "Unknown"
        logger.debug(f"Client connected: {peer_name}")
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                try:
                    message = json.loads(data.decode("utf-8"))
                except json.JSONDecodeError:
                    logger.warning("Received invalid JSON payload")
                    continue

                response = await self.message_handler(message)
                response_data = json.dumps(response).encode("utf-8") + b"\n"
                writer.write(response_data)
                await writer.drain()
        except asyncio.CancelledError:
            logger.info("Client handler cancelled")
        except Exception as e:
            logger.error(f"Error handling IPC client: {e}", exc_info=True)
        finally:
            writer.close()
            await writer.wait_closed()
            logger.debug(f"Client disconnected: {peer_name}")

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Unix IPC Server stopped")
            if os.path.exists(self.socket_path):
                with contextlib.suppress(OSError):
                    os.unlink(self.socket_path)

class UnixSocketClient(IPCClient):
    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        self._reader, self._writer = await asyncio.open_unix_connection(self.socket_path)
        logger.debug(f"Connected to IPC server at {self.socket_path}")

    async def send_message(self, message: dict[str, Any]) -> None:
        if not self._writer:
            raise ConnectionError("Client is not connected")
        data = json.dumps(message).encode("utf-8") + b"\n"
        self._writer.write(data)
        await self._writer.drain()

    async def receive_message(self) -> dict[str, Any]:
        if not self._reader:
            raise ConnectionError("Client is not connected")
        data = await self._reader.readline()
        if not data:
            raise ConnectionError("Connection closed by server")
        return json.loads(data.decode("utf-8"))

    async def disconnect(self) -> None:
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None
            logger.debug("Disconnected from IPC server")
