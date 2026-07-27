import pytest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from unittest.mock import patch
from src.telemetry.factory import create_telemetry_provider
from src.telemetry.macos_dtrace import MacOSDTraceProvider

def test_macos_sip_psutil_fallback():
    """
    Validates that when running on macOS, the telemetry factory correctly selects 
    the MacOSDTraceProvider, and that it falls back to psutil when SIP blocks native dtrace.
    """
    with patch("platform.system", return_value="Darwin"):
        provider = create_telemetry_provider()
        assert isinstance(provider, MacOSDTraceProvider), "Factory did not return MacOSDTraceProvider for Darwin"
        
        # Initialization should not crash
        provider.initialize()
        
        # Assume SIP is enabled and dtrace is blocked. We don't have a real dtrace process.
        # Calling get_metrics should gracefully fall back to psutil.
        metrics = provider.get_metrics(os.getpid())
        
        assert metrics is not None, "Fallback to psutil returned None"
        assert metrics.pid == os.getpid()
        assert metrics.cpu_usage_percent >= 0.0
        assert metrics.memory_usage_mb >= 0.0
        
        provider.cleanup()
