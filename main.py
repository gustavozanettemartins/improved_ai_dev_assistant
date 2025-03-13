#!/usr/bin/env python3
import json
import os
import sys
import asyncio
import argparse
import platform
import psutil
import uuid
from colorama import Fore, Style, init as colorama_init

# Initialize colorama
colorama_init()

# Import the configuration manager first
from config.config_manager import config_manager

# Initialize structured logging as early as possible
config_manager.setup_structured_logging()

# Now import other modules
from utils.structured_logger import get_logger, ContextVars, operation_logger
from utils.error_handler import (
    ErrorHandler, handle_errors, ErrorBoundary, AsyncErrorBoundary,
    AppError, SystemError, NetworkError, ConfigError
)
from core.performance import perf_tracker
from core.dev_assistant import DevAssistant
from cli.command_handler import CommandHandler

# Get a logger for this module
logger = get_logger(__name__)


async def cleanup_resources(dev_assistant, command_handler, logger):
    """
    Perform comprehensive cleanup of all application resources.

    Args:
        dev_assistant: The DevAssistant instance
        command_handler: The CommandHandler instance
        logger: Logger instance for operation tracing
    """
    cleanup_tasks = []
    cleanup_errors = []

    # Track resources that need closing
    resources_to_close = []

    # 1. Close model API connection
    if hasattr(dev_assistant, 'model_api'):
        resources_to_close.append(('model_api', dev_assistant.model_api))

    # 2. Close web search handler if it exists
    if (hasattr(command_handler, 'web_commands') and
            hasattr(command_handler.web_commands, 'search_handler')):
        resources_to_close.append(
            ('web_search', command_handler.web_commands.search_handler)
        )

    # 3. Close any other HTTP sessions that might exist
    if hasattr(dev_assistant, 'http_sessions'):
        for name, session in dev_assistant.http_sessions.items():
            resources_to_close.append((f'http_session_{name}', session))

    # 4. Close response cache
    from utils.cache import response_cache
    resources_to_close.append(('response_cache', response_cache))

    # Close all resources with proper error handling
    for resource_name, resource in resources_to_close:
        try:
            with logger.trace_operation(f"close_{resource_name}"):
                if hasattr(resource, 'close'):
                    if asyncio.iscoroutinefunction(resource.close):
                        # Create task for async close
                        task = asyncio.create_task(resource.close())
                        cleanup_tasks.append(task)
                    else:
                        # Call synchronous close
                        resource.close()
                        logger.info(f"Closed {resource_name} (sync)")
        except Exception as e:
            error_msg = f"Error closing {resource_name}: {e}"
            logger.error(error_msg)
            cleanup_errors.append(error_msg)

    # Wait for all async close operations to complete
    if cleanup_tasks:
        try:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            logger.info(f"Closed {len(cleanup_tasks)} async resources")
        except Exception as e:
            logger.error(f"Error during async resource cleanup: {e}")

    # Handle any pending tasks
    try:
        pending_tasks = [
            task for task in asyncio.all_tasks()
            if not task.done() and task is not asyncio.current_task()
        ]

        if pending_tasks:
            logger.info(f"Cancelling {len(pending_tasks)} pending tasks")
            for task in pending_tasks:
                task.cancel()

            # Wait briefly for tasks to cancel
            await asyncio.gather(*pending_tasks, return_exceptions=True)
    except Exception as e:
        logger.error(f"Error cancelling pending tasks: {e}")

    # Return summary of cleanup operation
    return len(cleanup_tasks), len(cleanup_errors)

@operation_logger(operation_name="main", include_args=True)
async def main(model: str = config_manager.get("default_model")):
    """
    Main application entry point with async support.

    Args:
        model: The model to use for AI assistance
    """
    # Generate a session ID for the application run
    session_id = str(uuid.uuid4())
    ContextVars.set("session_id", session_id)

    logger.info(
        f"Starting AI Development Assistant v{config_manager.get('version', '2.0.0')}",
        extra={"structured_data": {"session_id": session_id}}
    )

    # Print welcome banner
    print(f"""
    {Fore.CYAN}╔═════════════════════════════════════════════════════════╗
    ║ {Fore.YELLOW}AI Development Assistant {config_manager.get('version', '2.0.0')}{Fore.CYAN}                          ║
    ║ {Fore.WHITE}An intelligent assistant for software development{Fore.CYAN}       ║
    ╚═════════════════════════════════════════════════════════╝{Style.RESET_ALL}
        """)

    # Check system information
    print(f"{Fore.GREEN}System Information:{Style.RESET_ALL}")

    # Use an error boundary for system information gathering
    with ErrorBoundary(error_type=SystemError, raise_error=False) as system_info_boundary:
        # Get system information
        cpu_cores = psutil.cpu_count(logical=False)
        cpu_threads = psutil.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024 ** 3)

        print(f"  Python: {platform.python_version()} on {platform.system()} {platform.release()}")
        print(f"  CPU: {cpu_cores} cores, {cpu_threads} threads")
        print(f"  Memory: {memory_gb:.1f} GB total\n")

        # Log system information for diagnostics
        logger.info(
            "System information collected",
            extra={"structured_data": {
                "python_version": platform.python_version(),
                "system": platform.system(),
                "release": platform.release(),
                "cpu_cores": cpu_cores,
                "cpu_threads": cpu_threads,
                "memory_gb": round(memory_gb, 1)
            }}
        )

    # Handle any errors in system information gathering
    if system_info_boundary.error:
        print(f"{Fore.YELLOW}Warning: Could not collect complete system information.{Style.RESET_ALL}")
        logger.warning(f"System information collection incomplete: {system_info_boundary.error}")

    # Initialize components with async error boundary
    async with AsyncErrorBoundary(error_type=AppError, raise_error=True) as init_boundary:
        print(f"{Fore.GREEN}Initializing components...{Style.RESET_ALL}")

        # Create an operation trace for component initialization
        with logger.trace_operation("component_initialization", component="DevAssistant"):
            dev_assistant = DevAssistant(model)
            command_handler = CommandHandler(dev_assistant)

        # Scan for existing projects
        with logger.trace_operation("scan_projects"):
            await dev_assistant.project_manager.scan_projects()
            project_count = len(dev_assistant.project_manager.projects)
            print(f"  Found {project_count} existing projects")

        # Ensure cache directory exists
        os.makedirs(config_manager.get("cache_dir"), exist_ok=True)
        print(f"  Cache directory: {config_manager.get('cache_dir')}")

        # Check API connection
        print(f"  Checking API connection... ", end="")
        try:
            with logger.trace_operation("api_connection_test", model=model):
                test_response = await dev_assistant.model_api.generate_response(
                    model, "Hello, this is a connection test. Please respond with 'Connection successful'.", 0.0
                )

                if "Connection successful" in test_response or "success" in test_response.lower():
                    print(f"{Fore.GREEN}Connected!{Style.RESET_ALL}")
                    logger.info("API connection test successful")
                else:
                    print(f"{Fore.YELLOW}Warning: Unexpected response{Style.RESET_ALL}")
                    logger.warning(
                        "API connection test returned unexpected response",
                        extra={"structured_data": {"response": test_response}}
                    )
        except Exception as e:
            print(f"{Fore.RED}Failed: {e}{Style.RESET_ALL}")
            logger.error(
                "API connection test failed",
                extra={"structured_data": {"error": str(e), "error_type": e.__class__.__name__}}
            )
            # Convert to AppError for consistent handling
            ErrorHandler.handle(e, log_error=True, raise_error=False)

    print(f"\n{Fore.GREEN}Ready! Type :help for a list of commands.{Style.RESET_ALL}\n")

    # Main interaction loop
    try:
        logger.info("Entering main interaction loop")

        while True:
            try:
                # Generate a correlation ID for each command
                command_id = str(uuid.uuid4())
                ContextVars.set("correlation_id", command_id)

                # Get user input with command completion
                user_input = input(f"{Fore.BLUE}>>> {Style.RESET_ALL}")

                # Log the input (without sensitive content)
                logger.info(
                    f"Received user input",
                    extra={"structured_data": {
                        "input_length": len(user_input),
                        "is_command": user_input.startswith(":")
                    }}
                )

                if user_input.lower() == "exit":
                    logger.info("Exit command received")
                    print("Exiting...")
                    break

                # Parse and handle the command with error boundary
                with ErrorBoundary(raise_error=False,
                                   on_error=lambda e: print(f"{Fore.RED}Error: {e.user_message}{Style.RESET_ALL}")):
                    # Trace the command execution
                    with logger.trace_operation("command_execution",
                                                command=user_input.split()[0] if user_input else ""):
                        command_args = command_handler.parse_command(user_input)

                        if not command_args:
                            continue

                        # Check if this is a command or conversation
                        if command_args[0].startswith(":"):
                            command_result = await command_handler.handle_command(command_args)

                            if command_result == ":exit":
                                logger.info("Exit requested from command handler")
                                print("Exiting...")
                                break

                            if command_result:
                                print(command_result)
                        else:
                            # Treat as conversation
                            dev_assistant.conversation.add_message("User", user_input)

                            # Show a streaming response with progress indicator
                            print(f"{Fore.GREEN}AI Assistant is thinking...{Style.RESET_ALL}")

                            response_chunks = []

                            async def handle_chunk(chunk):
                                response_chunks.append(chunk)
                                # To create a nice streaming effect, print the chunk directly
                                print(chunk, end="", flush=True)

                            # Stream the response
                            with logger.trace_operation("model_stream_response", model=dev_assistant.model):
                                await dev_assistant.model_api.stream_response(
                                    dev_assistant.model,
                                    dev_assistant.conversation.get_full_history(),
                                    handle_chunk
                                )

                            # Complete the response by adding a newline
                            print("\n")

                            # Add the complete response to the conversation history
                            full_response = "".join(response_chunks)
                            dev_assistant.conversation.add_message("Model", full_response)

                            # Log the response details
                            logger.info(
                                "Model response received",
                                extra={"structured_data": {
                                    "model": dev_assistant.model,
                                    "response_length": len(full_response),
                                    "tokens_estimate": len(full_response.split())
                                }}
                            )

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt in command loop")
                print("\nKeyboard interrupt detected. Type 'exit' to quit.")
                continue

            except Exception as e:
                # Convert and log the error
                app_error = ErrorHandler.handle(e, log_error=True, raise_error=False)
                print(f"{Fore.RED}Error: {app_error.user_message}{Style.RESET_ALL}")

                if app_error.suggestion:
                    print(f"{Fore.YELLOW}Suggestion: {app_error.suggestion}{Style.RESET_ALL}")

    except KeyboardInterrupt:
        logger.info("Application terminated by keyboard interrupt")
        print("\nExiting...")

    except Exception as e:
        # Log the error and convert it to AppError
        app_error = ErrorHandler.handle(e, log_error=True, raise_error=False)
        logger.critical(f"Unhandled exception in main loop: {app_error}")
        print(f"{Fore.RED}Fatal error: {app_error.user_message}{Style.RESET_ALL}")

    finally:
        # Clean-up with an async error boundary
        async with AsyncErrorBoundary(raise_error=False, error_type=AppError) as cleanup_boundary:
            logger.info("Starting application cleanup")

            # Save conversation history
            print("Saving conversation history...")
            with logger.trace_operation("save_conversation_history"):
                dev_assistant.conversation.save_history()

            # Close API sessions and other resources
            print("Closing connections...")

            # Use the new comprehensive cleanup function
            closed_count, error_count = await cleanup_resources(
                dev_assistant, command_handler, logger
            )

            if error_count > 0:
                logger.warning(f"Encountered {error_count} errors during resource cleanup")

            logger.info(f"Successfully closed {closed_count} resources")


@handle_errors(error_type=ConfigError, log_error=True)
def process_command_line_args():
    """Process command line arguments and update configuration."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="AI Development Assistant")
    parser.add_argument("--model", type=str, default=config_manager.get("default_model"),
                        help="Model to use for AI assistance")
    parser.add_argument("--config", type=str, default="ai_dev_config.json",
                        help="Path to configuration file")
    parser.add_argument("--working-dir", type=str, default=None,
                        help="Working directory for projects")
    parser.add_argument("--no-git", action="store_true",
                        help="Disable Git integration")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--web", action="store_true",
                        help="Start with web interface")
    parser.add_argument("--port", type=int, default=config_manager.get("web_interface_port", 8080),
                        help="Port for web interface")

    args = parser.parse_args()

    # Update configuration if command line args provided
    if args.working_dir:
        config_manager.set("working_dir", args.working_dir)

    if args.no_git:
        config_manager.set("git_integration", False)

    if args.debug:
        config_manager.set("logging.console_level", "DEBUG")
        config_manager.set("logging.file_level", "DEBUG")

    if args.web:
        config_manager.set("enable_web_interface", True)
        config_manager.set("web_interface_port", args.port)

    # Set up structured logging again with updated config
    config_manager.setup_structured_logging()

    # Handle special import requirements for aiohttp
    if config_manager.get("enable_web_interface", False):
        try:
            import aiohttp
            import socketio

            logger.info("Web interface dependencies found")
        except ImportError as e:
            logger.warning(
                "Web interface dependencies not installed, disabling web interface",
                extra={"structured_data": {"error": str(e)}}
            )
            config_manager.set("enable_web_interface", False)
            print(
                f"{Fore.YELLOW}Web interface dependencies not installed. Run: pip install aiohttp python-socketio{Style.RESET_ALL}")

    # Add proper handling of all imports
    try:
        import fnmatch  # Used in search_code function
        import psutil  # Used for system info
        import json  # Missing import
    except ImportError as e:
        logger.warning(
            f"Optional dependency not found",
            extra={"structured_data": {"dependency": str(e)}}
        )
        print(f"{Fore.YELLOW}Optional dependency not found: {e}. Some features may be limited.{Style.RESET_ALL}")

    return args.model


if __name__ == "__main__":
    try:
        # Set up correlation ID for the application
        app_correlation_id = str(uuid.uuid4())
        ContextVars.set("correlation_id", app_correlation_id)

        # Process command line arguments
        model = process_command_line_args()

        # Run the async main function
        asyncio.run(main(model))
        logger.info("Application exited normally")

    except KeyboardInterrupt:
        print(f"\n{Fore.CYAN}Application terminated by user{Style.RESET_ALL}")
        logger.info("Application terminated by user")

    except Exception as e:
        # Handle any unhandled exceptions
        app_error = ErrorHandler.handle(e, log_error=True, raise_error=False)
        logger.critical(f"Fatal error in application entry point: {app_error}")
        print(f"{Fore.RED}Fatal error: {app_error.user_message}{Style.RESET_ALL}")
        print(f"{Fore.RED}See log file for details{Style.RESET_ALL}")
        sys.exit(1)