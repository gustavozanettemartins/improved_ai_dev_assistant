from typing import Union

class Calculator:
    """A simple calculator class to perform basic arithmetic operations."""

    def add(self, a: float, b: float) -> float:
        """Add two numbers.

        Args:
            a (float): The first number.
            b (float): The second number.

        Returns:
            float: The sum of the two numbers.
        """
        return a + b

    def subtract(self, a: float, b: float) -> float:
        """Subtract two numbers.

        Args:
            a (float): The first number.
            b (float): The second number.

        Returns:
            float: The difference of the two numbers.
        """
        return a - b

    def multiply(self, a: float, b: float) -> float:
        """Multiply two numbers.

        Args:
            a (float): The first number.
            b (float): The second number.

        Returns:
            float: The product of the two numbers.
        """
        return a * b

    def divide(self, a: float, b: float) -> Union[float, str]:
        """Divide two numbers.

        Args:
            a (float): The first number.
            b (float): The second number.

        Returns:
            float or str: The quotient of the two numbers or an error message if division by zero is attempted.
        """
        try:
            return a / b
        except ZeroDivisionError:
            return "Cannot divide by zero."