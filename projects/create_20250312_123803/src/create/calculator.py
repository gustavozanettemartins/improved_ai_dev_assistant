"""
Module to handle arithmetic operations.
"""

import logging

# Setting up basic configuration for logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class Calculator:
    """
    A class to represent a simple calculator.

    Attributes:
        None
    """

    def add(self, a: float, b: float) -> float:
        """
        Add two numbers.

        Args:
            a (float): First number.
            b (float): Second number.

        Returns:
            float: The sum of the two numbers.
        """
        logging.debug(f"Adding {a} and {b}")
        return a + b

    def subtract(self, a: float, b: float) -> float:
        """
        Subtract second number from first.

        Args:
            a (float): First number.
            b (float): Second number.

        Returns:
            float: The difference between the two numbers.
        """
        logging.debug(f"Subtracting {b} from {a}")
        return a - b

    def multiply(self, a: float, b: float) -> float:
        """
        Multiply two numbers.

        Args:
            a (float): First number.
            b (float): Second number.

        Returns:
            float: The product of the two numbers.
        """
        logging.debug(f"Multiplying {a} and {b}")
        return a * b

    def divide(self, a: float, b: float) -> float:
        """
        Divide first number by second.

        Args:
            a (float): First number.
            b (float): Second number.

        Returns:
            float: The quotient of the two numbers.

        Raises:
            ValueError: If the divisor is zero.
        """
        logging.debug(f"Dividing {a} by {b}")
        if b == 0:
            logging.error("Attempted to divide by zero")
            raise ValueError("Cannot divide by zero.")
        return a / b