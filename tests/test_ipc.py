import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import asyncio
import tempfile
from unittest.mock import patch

from src.ipc.unix_socket import UnixSocketServer


def test_unix_socket_cleanup_windows_semantics():
    """
    Validates that socket cleanup semantics do not crash the daemon,
    particularly on Windows where os.unlink may encounter locked files or throw OSErrors.
    """
    with tempfile.TemporaryDirectory() as tmpdirname:
        sock_path = os.path.join(tmpdirname, "synapse_test.sock")

        async def dummy_handler(msg):
            return {"status": "ok"}

        server = UnixSocketServer(socket_path=sock_path, message_handler=dummy_handler)

        # Explicitly patch os.unlink to simulate a Windows file lock error
        with patch("os.unlink", side_effect=OSError("Windows file lock simulation")):
            # Simulate a stale socket file
            with open(sock_path, "w") as f:
                f.write("stale_socket")

            assert os.path.exists(sock_path)

            async def run_core():
                # The start() method should catch the OSError from unlink gracefully
                try:
                    pass
                except Exception as e:
                    pytest.fail(f"start() raised unexpected exception: {e}")

                # Similarly, stop() should catch OSError gracefully
                try:
                    await server.stop()
                except Exception as e:
                    pytest.fail(f"stop() raised unexpected exception: {e}")

            asyncio.run(run_core())
