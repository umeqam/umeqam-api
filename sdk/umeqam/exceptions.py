"""
UMEQAM SDK — Exceptions
"""


class UMEQAMError(Exception):
    """Base exception for UMEQAM SDK."""
    pass


class AuthenticationError(UMEQAMError):
    """Invalid or missing API key."""
    pass


class RateLimitError(UMEQAMError):
    """Rate limit or quota exceeded."""
    pass


class APIError(UMEQAMError):
    """Generic API error with status code."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class ConnectionError(UMEQAMError):
    """Cannot reach UMEQAM API."""
    pass
