"""
UMEQAM Python SDK
Runtime compliance engine for AI in regulated industries.

Usage:
    import umeqam

    client = umeqam.Client(api_key="your-key")
    result = client.medical.analyze("Take aspirin daily without a doctor.")
    print(result.verdict)  # FAIL
"""

from .client import UMEQAMClient as Client
from .models import ComplianceResult, HealthResult, AskResult, Judge
from .exceptions import (
    UMEQAMError,
    AuthenticationError,
    RateLimitError,
    APIError,
    ConnectionError,
)

__version__ = "1.0.0"
__all__ = [
    "Client",
    "ComplianceResult",
    "HealthResult",
    "AskResult",
    "Judge",
    "UMEQAMError",
    "AuthenticationError",
    "RateLimitError,\n    \"APIError\",\n    \"ConnectionError\",\n]\n