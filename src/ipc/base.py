import abc
from typing import Any


class IPCServer(abc.ABC):
    @abc.abstractmethod
    async def start(self) -> None:
        """Start listening for incoming connections."""
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        """Stop the server and cleanup resources."""
        pass

class IPCClient(abc.ABC):
    @abc.abstractmethod
    async def connect(self) -> None:
        """Establish connection to the server."""
        pass

    @abc.abstractmethod
    async def send_message(self, message: dict[str, Any]) -> None:
        """Send a JSON-serializable message to the server."""
        pass

    @abc.abstractmethod
    async def receive_message(self) -> dict[str, Any]:
        """Receive a JSON-serializable message from the server."""
        pass

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Close the connection."""
        pass
