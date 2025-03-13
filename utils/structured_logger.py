#!/usr/bin/env python3

import logging
import json
import sys
import os
import time
import uuid
import threading
import datetime
import traceback
from typing import Dict, Any, Optional, Union, List, Callable
from pathlib import Path
import functools
import inspect
import asyncio

# Dictionary for thread-local storage (simpler than threading.local())
_CONTEXT_STORAGE = {}
_CONTEXT_LOCK = threading.RLock()

# Flag to track if structured logging is initialized
_STRUCTURED_LOGGING_INITIALIZED = False


class ContextVars:
    """Thread-local storage for context variables like correlation IDs."""

    @classmethod
    def get(cls, key: str, default=None) -> Any:
        """Get a context variable by key."""
        thread_id = threading.get_ident()
        with _CONTEXT_LOCK:
            if thread_id not in _CONTEXT_STORAGE:
                _CONTEXT_STORAGE[thread_id] = {}
            return _CONTEXT_STORAGE[thread_id].get(key, default)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set a context variable."""
        thread_id = threading.get_ident()
        with _CONTEXT_LOCK:
            if thread_id not in _CONTEXT_STORAGE:
                _CONTEXT_STORAGE[thread_id] = {}
            _CONTEXT_STORAGE[thread_id][key] = value

    @classmethod
    def clear(cls) -> None:
        """Clear all context variables."""
        thread_id = threading.get_ident()
        with _CONTEXT_LOCK:
            if thread_id in _CONTEXT_STORAGE:
                _CONTEXT_STORAGE[thread_id] = {}

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all context variables as a dictionary."""
        thread_id = threading.get_ident()
        with _CONTEXT_LOCK:
            if thread_id not in _CONTEXT_STORAGE:
                _CONTEXT_STORAGE[thread_id] = {}
            return _CONTEXT_STORAGE[thread_id].copy()


class StructuredLogRecord(logging.LogRecord):
    """Enhanced LogRecord that includes structured data and context variables."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add timestamp in ISO format
        self.iso_timestamp = datetime.datetime.fromtimestamp(self.created).isoformat()

        # Add correlation ID and other context variables (with fallbacks)
        self.correlation_id = ContextVars.get("correlation_id", "")
        self.user_id = ContextVars.get("user_id", "")
        self.session_id = ContextVars.get("session_id", "")
        self.request_path = ContextVars.get("request_path", "")

        # Add execution context
        self.extra_data = ContextVars.get("extra_data", {})

        # For structured logging in JSON
        self.structured = {
            "timestamp": self.iso_timestamp,
            "level": self.levelname,
            "correlation_id": self.correlation_id,
            "logger": self.name,
            "message": self.getMessage(),
            "module": self.module,
            "function": self.funcName,
            "line": self.lineno,
            "thread": self.thread,
            "thread_name": self.threadName
        }

        # Add context vars
        if self.user_id:
            self.structured["user_id"] = self.user_id
        if self.session_id:
            self.structured["session_id"] = self.session_id
        if self.request_path:
            self.structured["request_path"] = self.request_path

        # Add any exception info
        if self.exc_info:
            self.structured["exception"] = {
                "type": self.exc_info[0].__name__,
                "message": str(self.exc_info[1]),
                "traceback": traceback.format_exception(*self.exc_info)
            }

        # Add any extra data
        if self.extra_data:
            self.structured["data"] = self.extra_data


class SafeJsonFormatter(logging.Formatter):
    """Formatter that outputs log records as JSON objects with error handling."""

    def format(self, record):
        """Format the record as a JSON string with fallbacks for non-structured records."""
        try:
            # Check if this is our custom structured record
            if hasattr(record, 'structured'):
                # Make a copy of structured data
                log_data = record.structured.copy()

                # Add any extra attributes from the record
                for key, value in record.__dict__.items():
                    if (key not in log_data and
                            key not in ('args', 'msg', 'structured', 'exc_info', 'exc_text', 'stack_info') and
                            not key.startswith('_')):
                        log_data[key] = value

                return json.dumps(log_data)
            else:
                # Fallback for standard log records
                fallback_data = {
                    "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }

                # Add exception info if available
                if record.exc_info:
                    fallback_data["exception"] = {
                        "type": record.exc_info[0].__name__,
                        "message": str(record.exc_info[1]),
                    }

                return json.dumps(fallback_data)
        except Exception as e:
            # Last resort fallback
            return f'{{"error":"Error formatting log record: {str(e)}","message":"{record.getMessage()}"}}'


class SafeColorizedConsoleFormatter(logging.Formatter):
    """Formatter that adds colors to console output with fallbacks for missing fields."""

    # ANSI color codes
    COLORS = {
        'RESET': '\033[0m',
        'BLACK': '\033[30m',
        'RED': '\033[31m',
        'GREEN': '\033[32m',
        'YELLOW': '\033[33m',
        'BLUE': '\033[34m',
        'MAGENTA': '\033[35m',
        'CYAN': '\033[36m',
        'WHITE': '\033[37m',
        'BOLD': '\033[1m',
        'UNDERLINE': '\033[4m',
    }

    # Level-specific colors
    LEVEL_COLORS = {
        'DEBUG': COLORS['BLUE'],
        'INFO': COLORS['GREEN'],
        'WARNING': COLORS['YELLOW'],
        'ERROR': COLORS['RED'],
        'CRITICAL': COLORS['RED'] + COLORS['BOLD'],
    }

    def __init__(self, fmt=None, datefmt=None, style='%', use_colors=True):
        super().__init__(fmt, datefmt, style)
        self.use_colors = use_colors

    def format(self, record):
        """Format the record with optional colorization and field fallbacks."""
        try:
            # Apply the base formatting, handling missing correlation_id
            if '%' in self._fmt and '%(correlation_id)s' in self._fmt and not hasattr(record, 'correlation_id'):
                record.correlation_id = ''

            formatted_msg = super().format(record)

            if self.use_colors and hasattr(record, 'levelname'):
                color = self.LEVEL_COLORS.get(record.levelname, self.COLORS['RESET'])
                reset = self.COLORS['RESET']

                # Add color to the level and correlation ID
                if hasattr(record, 'correlation_id') and record.correlation_id:
                    cid_part = f"[{self.COLORS['CYAN']}{record.correlation_id}{reset}]"
                    formatted_msg = formatted_msg.replace(f"[{record.correlation_id}]", cid_part)

                # Colorize the level name
                level_part = f"{color}{record.levelname}{reset}"
                formatted_msg = formatted_msg.replace(record.levelname, level_part)

            return formatted_msg
        except Exception as e:
            # Fallback if formatting fails
            return f"LOG-ERROR[{record.levelname}]: {record.getMessage()} (Formatting error: {e})"


class StructuredLogger(logging.Logger):
    """Enhanced logger with support for structured logging and context tracking."""

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None):
        """Create a StructuredLogRecord instead of a regular LogRecord."""
        try:
            return StructuredLogRecord(name, level, fn, lno, msg, args, exc_info, func, sinfo)
        except Exception:
            # Fallback to standard LogRecord if StructuredLogRecord creation fails
            return super().makeRecord(name, level, fn, lno, msg, args, exc_info, func, extra, sinfo)

    def _log_with_extras(self, level, msg, args, exc_info=None, extra=None,
                         stack_info=False, stacklevel=1):
        """Log with extra data stored in the structured log record."""
        # Extract any extra data for structured logging
        structured_extra = {}
        if extra:
            # Copy to avoid modifying the original
            regular_extra = extra.copy() if extra else {}

            # Move known structured keys to structured_extra
            for key in list(regular_extra.keys()):
                if key == 'structured_data':
                    structured_extra.update(regular_extra.pop('structured_data'))

            # Store structured_extra in context vars for the log record to pick up
            if structured_extra:
                current_extra = ContextVars.get('extra_data', {})
                updated_extra = {**current_extra, **structured_extra}
                ContextVars.set('extra_data', updated_extra)

        # Call the standard logging method
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel + 1)

        # Cleanup any temporary extra data
        if structured_extra:
            ContextVars.set('extra_data', {})

    def debug(self, msg, *args, **kwargs):
        """Enhanced debug logging with structured data support."""
        self._log_with_extras(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg, *args, **kwargs):
        """Enhanced info logging with structured data support."""
        self._log_with_extras(logging.INFO, msg, args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        """Enhanced warning logging with structured data support."""
        self._log_with_extras(logging.WARNING, msg, args, **kwargs)

    def error(self, msg, *args, **kwargs):
        """Enhanced error logging with structured data support."""
        self._log_with_extras(logging.ERROR, msg, args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        """Enhanced critical logging with structured data support."""
        self._log_with_extras(logging.CRITICAL, msg, args, **kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        """Enhanced exception logging with structured data support."""
        self._log_with_extras(logging.ERROR, msg, args, exc_info=exc_info, **kwargs)

    def trace_operation(self, operation_name: str, **kwargs) -> 'OperationTracer':
        """Create an operation tracer for timing and tracking a logical operation."""
        return OperationTracer(self, operation_name, **kwargs)


class FallbackLogger(logging.Logger):
    """Fallback logger that provides trace_operation method but uses standard logging."""

    def trace_operation(self, operation_name: str, **kwargs) -> 'OperationTracer':
        """Create an operation tracer for timing and tracking a logical operation."""
        return OperationTracer(self, operation_name, **kwargs)


class OperationTracer:
    """Context manager for tracing operations with timing and result tracking."""

    def __init__(self, logger: logging.Logger, operation_name: str, **kwargs):
        self.logger = logger
        self.operation_name = operation_name
        self.extra_data = kwargs
        self.start_time = None

        # Ensure we have a correlation ID
        self.correlation_id = ContextVars.get('correlation_id')
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())
            ContextVars.set('correlation_id', self.correlation_id)

    def __enter__(self):
        """Start timing the operation and log its beginning."""
        self.start_time = time.time()

        # Log operation start with all the context we have
        try:
            # Try to use structured logging if possible
            self.logger.info(
                f"Starting operation: {self.operation_name}",
                extra={'structured_data': {
                    'event': 'operation_start',
                    'operation': self.operation_name,
                    **self.extra_data
                }}
            )
        except Exception:
            # Fallback to simple logging
            self.logger.info(f"Starting operation: {self.operation_name}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log the operation completion or failure."""
        duration_ms = int((time.time() - self.start_time) * 1000)

        if exc_type is not None:
            # Operation failed
            try:
                self.logger.error(
                    f"Operation failed: {self.operation_name} after {duration_ms}ms",
                    exc_info=(exc_type, exc_val, exc_tb),
                    extra={'structured_data': {
                        'event': 'operation_failed',
                        'operation': self.operation_name,
                        'duration_ms': duration_ms,
                        'error_type': exc_type.__name__ if exc_type else None,
                        'error_message': str(exc_val) if exc_val else None,
                        **self.extra_data
                    }}
                )
            except Exception:
                # Fallback to simple logging
                self.logger.error(
                    f"Operation failed: {self.operation_name} after {duration_ms}ms",
                    exc_info=(exc_type, exc_val, exc_tb)
                )

            # Don't suppress the exception
            return False
        else:
            # Operation succeeded
            try:
                self.logger.info(
                    f"Completed operation: {self.operation_name} in {duration_ms}ms",
                    extra={'structured_data': {
                        'event': 'operation_completed',
                        'operation': self.operation_name,
                        'duration_ms': duration_ms,
                        **self.extra_data
                    }}
                )
            except Exception:
                # Fallback to simple logging
                self.logger.info(f"Completed operation: {self.operation_name} in {duration_ms}ms")

            return True

    async def __aenter__(self):
        """Async version of __enter__."""
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async version of __exit__."""
        return self.__exit__(exc_type, exc_val, exc_tb)


def operation_logger(func=None, operation_name=None, include_args=False, include_result=False, level=logging.INFO):
    """
    Decorator to automatically log function/method calls as operations.

    Args:
        func: The function to decorate
        operation_name: Optional custom name for the operation (defaults to function name)
        include_args: Whether to include function arguments in the logs
        include_result: Whether to include the function result in the logs
        level: Log level to use
    """

    def decorator(func):
        # Get the logger for the module where the decorated function is defined
        logger_name = func.__module__
        logger = get_logger(logger_name)

        # Determine if the function is async
        is_async = asyncio.iscoroutinefunction(func)

        # Choose the actual operation name
        actual_operation_name = operation_name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Prepare extra data for logging
            extra_data = {}

            # Include arguments if requested
            if include_args:
                # Filter out 'self' for methods
                if args and hasattr(args[0], '__class__') and func.__name__ in dir(args[0].__class__):
                    # This is likely a method call
                    arg_values = args[1:]
                else:
                    arg_values = args

                # Extract argument names using the function signature
                try:
                    sig = inspect.signature(func)
                    param_names = list(sig.parameters.keys())

                    # Create a mapping of argument names to values
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    arg_dict = dict(bound_args.arguments)

                    # Remove 'self' for method calls
                    if 'self' in arg_dict:
                        del arg_dict['self']

                    extra_data['args'] = arg_dict
                except (ValueError, TypeError):
                    # Fall back to positional args if we can't get the signature
                    extra_data['args'] = {
                        f'arg{i}': arg for i, arg in enumerate(arg_values)
                    }
                    if kwargs:
                        extra_data['args'].update(kwargs)

            # Generate a correlation ID if one doesn't exist
            if not ContextVars.get('correlation_id'):
                ContextVars.set('correlation_id', str(uuid.uuid4()))

            # Start the operation trace
            with OperationTracer(logger, actual_operation_name, **extra_data) as tracer:
                result = func(*args, **kwargs)

                # Include the result if requested
                if include_result:
                    try:
                        logger.log(
                            level,
                            f"Result of {actual_operation_name}",
                            extra={'structured_data': {'result': result}}
                        )
                    except Exception:
                        # Fallback to simple logging
                        logger.log(level, f"Result of {actual_operation_name}: {result}")

                return result

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Prepare extra data for logging
            extra_data = {}

            # Include arguments if requested (same logic as in wrapper)
            if include_args:
                if args and hasattr(args[0], '__class__') and func.__name__ in dir(args[0].__class__):
                    arg_values = args[1:]
                else:
                    arg_values = args

                try:
                    sig = inspect.signature(func)
                    param_names = list(sig.parameters.keys())

                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    arg_dict = dict(bound_args.arguments)

                    if 'self' in arg_dict:
                        del arg_dict['self']

                    extra_data['args'] = arg_dict
                except (ValueError, TypeError):
                    extra_data['args'] = {
                        f'arg{i}': arg for i, arg in enumerate(arg_values)
                    }
                    if kwargs:
                        extra_data['args'].update(kwargs)

            # Generate a correlation ID if one doesn't exist
            if not ContextVars.get('correlation_id'):
                ContextVars.set('correlation_id', str(uuid.uuid4()))

            # Start the operation trace
            async with OperationTracer(logger, actual_operation_name, **extra_data) as tracer:
                result = await func(*args, **kwargs)

                # Include the result if requested
                if include_result:
                    try:
                        logger.log(
                            level,
                            f"Result of {actual_operation_name}",
                            extra={'structured_data': {'result': result}}
                        )
                    except Exception:
                        # Fallback to simple logging
                        logger.log(level, f"Result of {actual_operation_name}: {result}")

                return result

        # Return the appropriate wrapper based on whether the function is async
        return async_wrapper if is_async else wrapper

    # Handle both @operation_logger and @operation_logger(...) forms
    if func is None:
        return decorator
    return decorator(func)


def setup_structured_logging(
        app_name: str = "ai_dev_assistant",
        log_dir: Optional[str] = None,
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        enable_json_logs: bool = True,
        max_log_file_size: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        use_console_colors: bool = True
) -> bool:
    """
    Set up structured logging with console and file handlers.

    Args:
        app_name: Name of the application
        log_dir: Directory for log files (default: current working directory / logs)
        console_level: Log level for console output
        file_level: Log level for file output
        enable_json_logs: Whether to include JSON-formatted logs
        max_log_file_size: Maximum size of a log file before rotation
        backup_count: Number of backup log files to keep
        use_console_colors: Whether to use colors in console output

    Returns:
        True if successfully set up, False otherwise
    """
    global _STRUCTURED_LOGGING_INITIALIZED

    # Don't initialize more than once
    if _STRUCTURED_LOGGING_INITIALIZED:
        return True

    # Set up a correlation ID if not already set
    if not ContextVars.get('correlation_id'):
        ContextVars.set('correlation_id', str(uuid.uuid4()))

    try:
        # Register our custom logger class and store the original
        orig_logger_class = logging.getLoggerClass()

        # Only set StructuredLogger as the logger class if it hasn't been done yet
        logging.setLoggerClass(StructuredLogger)

        # Determine log directory
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), "logs")

        # Create log directory if it doesn't exist
        Path(log_dir).mkdir(parents=True, exist_ok=True)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Capture all levels, let handlers filter

        # Remove existing handlers (in case this is called multiple times)
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create console handler with a formatter that doesn't require correlation_id
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)

        # Format strings with fallbacks for correlation_id
        console_format = "%(asctime)s [%(correlation_id)s] %(levelname)s - %(name)s - %(message)s"

        # Create and add formatter to console handler
        console_formatter = SafeColorizedConsoleFormatter(
            console_format,
            datefmt='%Y-%m-%d %H:%M:%S',
            use_colors=use_console_colors
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # Create file handlers
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d')

        # Regular log file using RotatingFileHandler
        from logging.handlers import RotatingFileHandler
        log_file = os.path.join(log_dir, f"{app_name}_{timestamp}.log")
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_log_file_size,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(file_level)
        file_formatter = SafeColorizedConsoleFormatter(console_format, datefmt='%Y-%m-%d %H:%M:%S', use_colors=False)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # JSON log file if enabled
        if enable_json_logs:
            json_log_file = os.path.join(log_dir, f"{app_name}_{timestamp}_json.log")
            json_handler = RotatingFileHandler(
                json_log_file,
                maxBytes=max_log_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            json_handler.setLevel(file_level)
            json_formatter = SafeJsonFormatter()
            json_handler.setFormatter(json_formatter)
            root_logger.addHandler(json_handler)

        # Log the setup
        logger = logging.getLogger(__name__)
        logger.info(
            f"Structured logging initialized for {app_name}",
            extra={'structured_data': {
                'event': 'logging_initialized',
                'app_name': app_name,
                'log_dir': log_dir,
                'console_level': logging.getLevelName(console_level),
                'file_level': logging.getLevelName(file_level),
                'json_logs_enabled': enable_json_logs
            }}
        )

        _STRUCTURED_LOGGING_INITIALIZED = True
        return True

    except Exception as e:
        # Critical logging setup failure, fall back to basic logging
        print(f"ERROR: Failed to set up structured logging: {e}")

        # Revert to original logger class
        if 'orig_logger_class' in locals():
            logging.setLoggerClass(orig_logger_class)

        # Ensure we have basic logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )

        # Ensure FallbackLogger is registered to provide a minimal implementation
        logging.setLoggerClass(FallbackLogger)

        # Log the error
        logging.getLogger(__name__).error(f"Structured logging initialization failed: {e}")
        return False


def get_logger(name: str) -> logging.Logger:
    """
    Get a structured logger instance, falling back to a standard logger if needed.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured Logger instance
    """
    logger = logging.getLogger(name)

    # If the logger doesn't have the trace_operation method and we're using FallbackLogger,
    # ensure it has that method
    if not hasattr(logger, 'trace_operation') and isinstance(logger, logging.Logger) and not isinstance(logger,
                                                                                                        StructuredLogger):
        if not _STRUCTURED_LOGGING_INITIALIZED:
            # Wrap the logger with a FallbackLogger to provide trace_operation
            fallback_logger = FallbackLogger(name)
            fallback_logger.setLevel(logger.level)

            # Copy the handlers
            for handler in logger.handlers:
                fallback_logger.addHandler(handler)

            return fallback_logger

    return logger


# Initialize context if not already set
if not ContextVars.get('correlation_id'):
    ContextVars.set('correlation_id', str(uuid.uuid4()))