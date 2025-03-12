import re

def is_valid_number(value: str) -> bool:
    """
    Validates if the given value is a valid number (integer or float).

    Args:
        value (str): The string to validate.

    Returns:
        bool: True if the value is a valid number, False otherwise.
    """
    return re.match(r'^-?\d+(\.\d+)?$', value) is not None

def safe_cast(value: str, target_type: type) -> any:
    """
    Safely casts a string to a specified type.

    Args:
        value (str): The string to cast.
        target_type (type): The type to cast the string into.

    Returns:
        any: The casted value if successful, None otherwise.
    """
    try:
        return target_type(value)
    except (ValueError, TypeError):
        return None

def log_error(message: str) -> None:
    """
    Logs an error message to the console.

    Args:
        message (str): The error message to log.
    """
    print(f"ERROR: {message}")

# Example usage
if __name__ == "__main__":
    print(is_valid_number("123"))  # True
    print(is_valid_number("-45.67"))  # True
    print(is_valid_number("abc"))  # False

    print(safe_cast("10", int))  # 10
    print(safe_cast("abc", int))  # None

    log_error("An error occurred.")