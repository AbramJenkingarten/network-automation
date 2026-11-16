"""Custom exceptions for network automation."""


class NetworkAutomationError(Exception):
    """Base exception for network automation errors."""
    pass


class ConnectionError(NetworkAutomationError):
    """Raised when connection to device fails."""
    pass


class AuthenticationError(NetworkAutomationError):
    """Raised when authentication fails."""
    pass


class ConfigurationError(NetworkAutomationError):
    """Raised when configuration operation fails."""
    pass


class CommandError(NetworkAutomationError):
    """Raised when command execution fails."""
    pass


class TemplateError(NetworkAutomationError):
    """Raised when template rendering fails."""
    pass


class ValidationError(NetworkAutomationError):
    """Raised when validation fails."""
    pass


class UnsupportedDeviceError(NetworkAutomationError):
    """Raised when device type is not supported."""
    pass


class TimeoutError(NetworkAutomationError):
    """Raised when operation times out."""
    pass
