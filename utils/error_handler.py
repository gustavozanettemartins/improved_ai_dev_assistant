#!/usr/bin/env python3

import traceback
import inspect
import asyncio
from typing import Dict, Any, Optional, Union, List, Callable, Type, TypeVar, Generic
import functools
import time
import os
from enum import Enum

from utils.structured_logger import get_logger, ContextVars

# Type variable for return value
T = TypeVar('T')

# Logger for this module
logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    DEBUG = 10  # Minor issues that don't affect operation
    INFO = 20  # Informational issues that are handled automatically
    WARNING = 30  # Issues that might require attention but don't stop operation
    ERROR = 40  # Errors that prevent a specific operation but not the whole application
    CRITICAL = 50  # Errors that might cause the application to fail


class ErrorCategory(Enum):
    """Categories of errors for better organization and handling."""
    SYSTEM = "system"  # System-level errors (file system, OS, etc.)
    NETWORK = "network"  # Network-related errors (connectivity, timeouts, etc.)
    DATABASE = "database"  # Database errors (connection, query, etc.)
    API = "api"  # API-related errors (external services, responses, etc.)
    VALIDATION = "validation"  # Validation errors (input validation, schema, etc.)
    BUSINESS = "business"  # Business logic errors (workflow, rules, etc.)
    SECURITY = "security"  # Security-related errors (auth, permissions, etc.)
    CONFIG = "config"  # Configuration errors (missing/invalid config, etc.)
    RESOURCE = "resource"  # Resource-related errors (memory, CPU, etc.)
    UNKNOWN = "unknown"  # Unknown or uncategorized errors


class AppError(Exception):
    """
    Base exception class for application-specific errors with structured information.

    This provides consistent error handling with rich metadata for logging
    and client feedback.
    """

    def __init__(self,
                 message: str,
                 category: ErrorCategory = ErrorCategory.UNKNOWN,
                 severity: ErrorSeverity = ErrorSeverity.ERROR,
                 cause: Optional[Exception] = None,
                 details: Optional[Dict[str, Any]] = None,
                 user_message: Optional[str] = None,
                 error_code: Optional[str] = None,
                 correlation_id: Optional[str] = None,
                 retry_allowed: bool = True,
                 suggestion: Optional[str] = None):
        """
        Initialize application error with metadata.

        Args:
            message: Technical error message
            category: Error category for grouping and handling
            severity: Error severity level
            cause: Original exception that caused this error
            details: Additional error details as a dictionary
            user_message: User-friendly error message (defaults to technical message if None)
            error_code: Unique error code for reference
            correlation_id: Request correlation ID for tracing
            retry_allowed: Whether the operation can be retried
            suggestion: Suggested action to resolve the error
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.cause = cause
        self.details = details or {}
        self.user_message = user_message or message
        self.error_code = error_code or self._generate_error_code()
        self.correlation_id = correlation_id or ContextVars.get('correlation_id')
        self.retry_allowed = retry_allowed
        self.suggestion = suggestion
        self.timestamp = time.time()

        # Capture callstack information but exclude the error handling framework
        self.callstack = self._clean_traceback()

    def _generate_error_code(self) -> str:
        """Generate a unique error code based on exception class and location."""
        try:
            frame = inspect.currentframe()
            if frame and frame.f_back:
                frame = frame.f_back  # Get the caller's frame
                filename = os.path.basename(frame.f_code.co_filename)
                lineno = frame.f_lineno
                return f"{self.__class__.__name__}_{filename}_{lineno}"
        except Exception:
            pass
        return self.__class__.__name__

    def _clean_traceback(self) -> List[str]:
        """Get a clean traceback without the error handling framework frames."""
        tb = traceback.extract_stack()
        # Filter out frames from the error handling framework
        filtered_tb = [frame for frame in tb if 'error_handler.py' not in frame.filename]
        return [str(frame) for frame in filtered_tb]

    def to_dict(self) -> Dict[str, Any]:
        """Convert the error to a dictionary for structured logging and serialization."""
        result = {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "error_code": self.error_code,
            "user_message": self.user_message,
            "retry_allowed": self.retry_allowed,
            "timestamp": self.timestamp
        }

        if self.correlation_id:
            result["correlation_id"] = self.correlation_id

        if self.suggestion:
            result["suggestion"] = self.suggestion

        if self.cause:
            result["cause"] = {
                "type": self.cause.__class__.__name__,
                "message": str(self.cause)
            }

        if self.details:
            result["details"] = self.details

        return result

    def __str__(self) -> str:
        """String representation of the error."""
        base = f"{self.__class__.__name__}[{self.error_code}]: {self.message}"
        if self.suggestion:
            base += f" Suggestion: {self.suggestion}"
        return base


# Define specific error subclasses for common error categories

class SystemError(AppError):
    """System-related errors like file system, environment, etc."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.SYSTEM)
        super().__init__(message, **kwargs)


class NetworkError(AppError):
    """Network-related errors like connection issues, timeouts, etc."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.NETWORK)
        super().__init__(message, **kwargs)


class ApiError(AppError):
    """API-related errors like failed requests, unexpected responses, etc."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.API)
        super().__init__(message, **kwargs)


class ValidationError(AppError):
    """Validation errors for inputs, schemas, etc."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.VALIDATION)
        kwargs.setdefault('severity', ErrorSeverity.WARNING)
        super().__init__(message, **kwargs)


class BusinessError(AppError):
    """Business logic errors like workflow, rule violations, etc."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.BUSINESS)
        super().__init__(message, **kwargs)


class SecurityError(AppError):
    """Security-related errors like authentication, authorization, etc."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.SECURITY)
        kwargs.setdefault('severity', ErrorSeverity.ERROR)
        super().__init__(message, **kwargs)


class ConfigError(AppError):
    """Configuration errors like missing or invalid configuration."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.CONFIG)
        super().__init__(message, **kwargs)


class ResourceError(AppError):
    """Resource-related errors like memory, CPU, etc."""

    def __init__(self, message: str, **kwargs):
        kwargs.setdefault('category', ErrorCategory.RESOURCE)
        super().__init__(message, **kwargs)


class ErrorConverter:
    """
    Converts standard exceptions to application-specific exceptions.

    This allows for consistent error handling and enriched error information.
    """

    # Mapping of standard exception types to app-specific error classes
    DEFAULT_MAPPINGS = {
        ConnectionError: NetworkError,
        TimeoutError: NetworkError,
        FileNotFoundError: SystemError,
        PermissionError: SecurityError,
        ValueError: ValidationError,
        TypeError: ValidationError,
        KeyError: ValidationError,
        IndexError: ValidationError,
        AttributeError: ValidationError,
        ImportError: SystemError,
        ModuleNotFoundError: SystemError,
        MemoryError: ResourceError,
        OSError: SystemError,
        IOError: SystemError,

        # Async-specific errors
        asyncio.TimeoutError: NetworkError,
        asyncio.CancelledError: AppError,
    }

    # Additional mappings that can be registered at runtime
    _custom_mappings: Dict[Type[Exception], Type[AppError]] = {}

    @classmethod
    def register_mapping(cls, exception_type: Type[Exception], error_class: Type[AppError]) -> None:
        """
        Register a custom exception mapping.

        Args:
            exception_type: The standard exception type to convert
            error_class: The application-specific error class to convert to
        """
        cls._custom_mappings[exception_type] = error_class

    @classmethod
    def convert(cls, exc: Exception, default_message: Optional[str] = None) -> AppError:
        """
        Convert a standard exception to an application-specific exception.

        Args:
            exc: The exception to convert
            default_message: Optional default message to use if not derived from exception

        Returns:
            An application-specific exception instance
        """
        # If it's already an AppError, just return it
        if isinstance(exc, AppError):
            return exc

        # Check custom mappings first, then default mappings
        for mapping_dict in (cls._custom_mappings, cls.DEFAULT_MAPPINGS):
            for exc_type, error_class in mapping_dict.items():
                if isinstance(exc, exc_type):
                    # Create an instance of the mapped error class
                    message = default_message or str(exc)
                    return error_class(
                        message=message,
                        cause=exc,
                        details={"original_type": exc.__class__.__name__}
                    )

        # If no mapping found, convert to a generic AppError
        message = default_message or str(exc)
        return AppError(
            message=message,
            cause=exc,
            details={"original_type": exc.__class__.__name__}
        )


class ErrorHandler:
    """
    Central error handler for standardized error processing.

    This class provides methods for consistent error handling, logging,
    and conversion across the application.
    """

    @staticmethod
    def handle(exc: Exception,
               log_error: bool = True,
               raise_error: bool = True,
               default_message: Optional[str] = None,
               context: Optional[Dict[str, Any]] = None) -> AppError:
        """
        Handle an exception with standardized processing.

        Args:
            exc: The exception to handle
            log_error: Whether to log the error
            raise_error: Whether to re-raise the error after processing
            default_message: Optional default message if not using the exception message
            context: Additional context for the error

        Returns:
            Processed AppError instance

        Raises:
            AppError: The processed error if raise_error is True
        """
        # Convert to AppError if it's not already
        app_error = ErrorConverter.convert(exc, default_message)

        # Add context if provided
        if context and isinstance(app_error.details, dict):
            app_error.details.update({"context": context})

        # Log the error if requested
        if log_error:
            ErrorHandler.log_error(app_error)

        # Re-raise if requested
        if raise_error:
            raise app_error

        return app_error

    @staticmethod
    def log_error(error: Union[AppError, Exception], logger_name: Optional[str] = None) -> None:
        """
        Log an error with appropriate severity and structured information.

        Args:
            error: The error to log
            logger_name: Optional logger name (defaults to module where error occurred)
        """
        # Convert to AppError if needed
        if not isinstance(error, AppError):
            error = ErrorConverter.convert(error)

        # Determine the logger to use
        log = logger
        if logger_name:
            log = get_logger(logger_name)

        # Determine log level based on severity
        if isinstance(error, AppError):
            severity = error.severity
            log_level = severity.value
            error_dict = error.to_dict()
        else:
            log_level = ErrorSeverity.ERROR.value
            error_dict = {
                "error_type": error.__class__.__name__,
                "message": str(error)
            }

        # Create structured log entry
        extra = {"structured_data": error_dict}

        # Log with appropriate level
        if log_level >= ErrorSeverity.CRITICAL.value:
            log.critical(f"CRITICAL: {error}", extra=extra)
        elif log_level >= ErrorSeverity.ERROR.value:
            log.error(f"ERROR: {error}", extra=extra)
        elif log_level >= ErrorSeverity.WARNING.value:
            log.warning(f"WARNING: {error}", extra=extra)
        elif log_level >= ErrorSeverity.INFO.value:
            log.info(f"INFO: {error}", extra=extra)
        else:
            log.debug(f"DEBUG: {error}", extra=extra)

    @staticmethod
    def create_error(error_type: Type[AppError], message: str, **kwargs) -> AppError:
        """
        Create an application error with the given type and parameters.

        Args:
            error_type: Type of AppError to create
            message: Error message
            **kwargs: Additional error parameters

        Returns:
            Created AppError instance
        """
        return error_type(message, **kwargs)


def handle_errors(log_error: bool = True,
                  raise_error: bool = True,
                  default_message: Optional[str] = None,
                  error_type: Optional[Type[AppError]] = None,
                  context_provider: Optional[Callable[[], Dict[str, Any]]] = None,
                  logger_name: Optional[str] = None):
    """
    Decorator for handling errors in functions and methods.

    Args:
        log_error: Whether to log the error
        raise_error: Whether to re-raise the error after processing
        default_message: Optional default message if not using the exception message
        error_type: Optional specific error type to convert to
        context_provider: Optional function to provide additional context
        logger_name: Optional logger name to use

    Returns:
        Decorator function
    """

    def decorator(func):
        # Determine if the function is async
        is_async = asyncio.iscoroutinefunction(func)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                # Get additional context if provided
                context = {}
                if context_provider:
                    try:
                        context = context_provider()
                    except Exception as context_exc:
                        # Don't let context provider errors overshadow the original error
                        logger.warning(f"Error getting error context: {context_exc}")

                # Convert the exception if a specific type was requested
                if error_type and not isinstance(exc, error_type):
                    app_error = error_type(
                        message=default_message or str(exc),
                        cause=exc,
                        details={"context": context} if context else None
                    )
                else:
                    # Use the standard error handling
                    app_error = ErrorHandler.handle(
                        exc,
                        log_error=log_error,
                        raise_error=False,  # Handle raising ourselves
                        default_message=default_message,
                        context=context
                    )

                # Log with specified logger if provided
                if log_error and logger_name:
                    ErrorHandler.log_error(app_error, logger_name)

                # Re-raise if requested
                if raise_error:
                    raise app_error

                return None

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                # Get additional context if provided
                context = {}
                if context_provider:
                    try:
                        context = context_provider()
                    except Exception as context_exc:
                        # Don't let context provider errors overshadow the original error
                        logger.warning(f"Error getting error context: {context_exc}")

                # Convert the exception if a specific type was requested
                if error_type and not isinstance(exc, error_type):
                    app_error = error_type(
                        message=default_message or str(exc),
                        cause=exc,
                        details={"context": context} if context else None
                    )
                else:
                    # Use the standard error handling
                    app_error = ErrorHandler.handle(
                        exc,
                        log_error=log_error,
                        raise_error=False,  # Handle raising ourselves
                        default_message=default_message,
                        context=context
                    )

                # Log with specified logger if provided
                if log_error and logger_name:
                    ErrorHandler.log_error(app_error, logger_name)

                # Re-raise if requested
                if raise_error:
                    raise app_error

                return None

        # Return the appropriate wrapper based on whether the function is async
        return async_wrapper if is_async else wrapper

    return decorator


class ErrorBoundary(Generic[T]):
    """
    Context manager for handling errors in a specific scope.

    This is similar to try/except but with standardized error handling.
    """

    def __init__(self,
                 log_error: bool = True,
                 raise_error: bool = True,
                 default_message: Optional[str] = None,
                 error_type: Optional[Type[AppError]] = None,
                 context: Optional[Dict[str, Any]] = None,
                 fallback_value: Optional[T] = None,
                 on_error: Optional[Callable[[AppError], None]] = None,
                 logger_name: Optional[str] = None):
        """
        Initialize the error boundary.

        Args:
            log_error: Whether to log the error
            raise_error: Whether to re-raise the error after processing
            default_message: Optional default message if not using the exception message
            error_type: Optional specific error type to convert to
            context: Additional context for the error
            fallback_value: Value to return if an error occurs and raise_error is False
            on_error: Optional callback to invoke when an error occurs
            logger_name: Optional logger name to use
        """
        self.log_error = log_error
        self.raise_error = raise_error
        self.default_message = default_message
        self.error_type = error_type
        self.context = context or {}
        self.fallback_value = fallback_value
        self.on_error = on_error
        self.logger_name = logger_name
        self.error = None

    def __enter__(self) -> 'ErrorBoundary[T]':
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Handle any errors when exiting the context."""
        if exc_val is None:
            return False

        try:
            # Convert the exception if a specific type was requested
            if self.error_type and not isinstance(exc_val, self.error_type):
                app_error = self.error_type(
                    message=self.default_message or str(exc_val),
                    cause=exc_val,
                    details={"context": self.context} if self.context else None
                )
            else:
                # Use the standard error handling
                app_error = ErrorHandler.handle(
                    exc_val,
                    log_error=self.log_error and not self.logger_name,  # Only log here if not using a specific logger
                    raise_error=False,  # Handle raising ourselves
                    default_message=self.default_message,
                    context=self.context
                )

            # Store the error
            self.error = app_error

            # Log with specified logger if provided
            if self.log_error and self.logger_name:
                ErrorHandler.log_error(app_error, self.logger_name)

            # Call the error callback if provided
            if self.on_error:
                self.on_error(app_error)

            # Re-raise if requested
            if self.raise_error:
                raise app_error

            # Suppress the exception
            return True
        except Exception as e:
            # If we encounter an error while handling the error, log it and re-raise the original
            logger.exception(f"Error in error boundary: {e}")
            return False


class AsyncErrorBoundary(Generic[T]):
    """
    Async context manager for handling errors in async code.

    This is similar to try/except but for async code with standardized error handling.
    """

    def __init__(self,
                 log_error: bool = True,
                 raise_error: bool = True,
                 default_message: Optional[str] = None,
                 error_type: Optional[Type[AppError]] = None,
                 context: Optional[Dict[str, Any]] = None,
                 fallback_value: Optional[T] = None,
                 on_error: Optional[Callable[[AppError], None]] = None,
                 logger_name: Optional[str] = None):
        """
        Initialize the async error boundary.

        Args:
            log_error: Whether to log the error
            raise_error: Whether to re-raise the error after processing
            default_message: Optional default message if not using the exception message
            error_type: Optional specific error type to convert to
            context: Additional context for the error
            fallback_value: Value to return if an error occurs and raise_error is False
            on_error: Optional callback to invoke when an error occurs
            logger_name: Optional logger name to use
        """
        self.log_error = log_error
        self.raise_error = raise_error
        self.default_message = default_message
        self.error_type = error_type
        self.context = context or {}
        self.fallback_value = fallback_value
        self.on_error = on_error
        self.logger_name = logger_name
        self.error = None

    async def __aenter__(self) -> 'AsyncErrorBoundary[T]':
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Handle any errors when exiting the context."""
        if exc_val is None:
            return False

        try:
            # Convert the exception if a specific type was requested
            if self.error_type and not isinstance(exc_val, self.error_type):
                app_error = self.error_type(
                    message=self.default_message or str(exc_val),
                    cause=exc_val,
                    details={"context": self.context} if self.context else None
                )
            else:
                # Use the standard error handling
                app_error = ErrorHandler.handle(
                    exc_val,
                    log_error=self.log_error and not self.logger_name,  # Only log here if not using a specific logger
                    raise_error=False,  # Handle raising ourselves
                    default_message=self.default_message,
                    context=self.context
                )

            # Store the error
            self.error = app_error

            # Log with specified logger if provided
            if self.log_error and self.logger_name:
                ErrorHandler.log_error(app_error, self.logger_name)

            # Call the error callback if provided
            if self.on_error:
                if asyncio.iscoroutinefunction(self.on_error):
                    await self.on_error(app_error)
                else:
                    self.on_error(app_error)

            # Re-raise if requested
            if self.raise_error:
                raise app_error

            # Suppress the exception
            return True
        except Exception as e:
            # If we encounter an error while handling the error, log it and re-raise the original
            logger.exception(f"Error in async error boundary: {e}")
            return False