import unittest
from unittest.mock import patch

# Importing the Calculator class from calculator module
from calculator import Calculator


class TestCalculator(unittest.TestCase):
    """
    A TestCase class for testing the Calculator class.
    """

    def setUp(self):
        """
        Set up a new instance of the Calculator before each test method runs.
        """
        self.calc = Calculator()

    def tearDown(self):
        """
        Clean up after each test method runs.
        This is typically where you would reset any shared resources or state.
        In this case, there's nothing to clean up.
        """
        pass

    def test_addition_positive_numbers(self):
        """
        Test adding two positive numbers.
        """
        self.assertEqual(self.calc.add(10.5, 20.3), 30.8)

    def test_addition_negative_numbers(self):
        """
        Test adding two negative numbers.
        """
        self.assertEqual(self.calc.add(-10.5, -20.3), -30.8)

    def test_addition_mixed_signs(self):
        """
        Test adding a positive and a negative number.
        """
        self.assertEqual(self.calc.add(10.5, -20.3), -9.8)

    def test_subtraction_positive_numbers(self):
        """
        Test subtracting two positive numbers where the first is larger.
        """
        self.assertEqual(self.calc.subtract(20.3, 10.5), 9.8)

    def test_subtraction_positive_numbers_swap_order(self):
        """
        Test subtracting two positive numbers where the second is larger.
        """
        self.assertEqual(self.calc.subtract(10.5, 20.3), -9.8)

    def test_subtraction_negative_numbers(self):
        """
        Test subtracting two negative numbers where the first is less than the second.
        """
        self.assertEqual(self.calc.subtract(-20.3, -10.5), -9.8)

    def test_subtraction_negative_numbers_swap_order(self):
        """
        Test subtracting two negative numbers where the second is less than the first.
        """
        self.assertEqual(self.calc.subtract(-10.5, -20.3), 9.8)

    def test_multiplication_positive_numbers(self):
        """
        Test multiplying two positive numbers.
        """
        self.assertEqual(self.calc.multiply(10.5, 20.3), 213.15)

    def test_multiplication_negative_numbers(self):
        """
        Test multiplying two negative numbers.
        """
        self.assertEqual(self.calc.multiply(-10.5, -20.3), 213.15)

    def test_multiplication_mixed_signs(self):
        """
        Test multiplying a positive and a negative number.
        """
        self.assertEqual(self.calc.multiply(10.5, -20.3), -213.15)

    def test_division_positive_numbers(self):
        """
        Test dividing two positive numbers where the first is larger.
        """
        self.assertAlmostEqual(self.calc.divide(20.3, 10.5), 1.9333333333333333, places=9)

    def test_division_positive_numbers_swap_order(self):
        """
        Test dividing two positive numbers where the second is larger.
        """
        self.assertAlmostEqual(self.calc.divide(10.5, 20.3), 0.5172413793103448, places=9)

    def test_division_negative_numbers(self):
        """
        Test dividing two negative numbers where the first is less than the second.
        """
        self.assertAlmostEqual(self.calc.divide(-20.3, -10.5), 1.9333333333333333, places=9)

    def test_division_negative_numbers_swap_order(self):
        """
        Test dividing two negative numbers where the second is less than the first.
        """
        self.assertAlmostEqual(self.calc.divide(-10.5, -20.3), 0.5172413793103448, places=9)

    def test_division_mixed_signs(self):
        """
        Test dividing a positive and a negative number.
        """
        self.assertAlmostEqual(self.calc.divide(10.5, -20.3), -0.5172413793103448, places=9)

    def test_division_by_zero(self):
        """
        Test dividing by zero raises a ValueError with an appropriate message.
        """
        with self.assertRaises(ValueError) as context:
            self.calc.divide(10.5, 0)
        self.assertEqual(str(context.exception), "Cannot divide by zero")

    @patch('calculator.logging')
    def test_division_by_zero_logs_error(self, mock_logging):
        """
        Test that dividing by zero logs an error.
        """
        with self.assertRaises(ValueError):
            try:
                self.calc.divide(10.5, 0)
            except ValueError:
                mock_logging.error.assert_called_once_with("Cannot divide by zero")
                raise

    def test_non_numeric_input_add(self):
        """
        Test that adding non-numeric inputs raises a TypeError.
        """
        with self.assertRaises(TypeError) as context:
            self.calc.add('ten', 20.3)
        self.assertEqual(str(context.exception), "'str' object cannot be interpreted as an integer")

    def test_non_numeric_input_subtract(self):
        """
        Test that subtracting non-numeric inputs raises a TypeError.
        """
        with self.assertRaises(TypeError) as context:
            self.calc.subtract('ten', 20.3)
        self.assertEqual(str(context.exception), "'str' object cannot be interpreted as an integer")

    def test_non_numeric_input_multiply(self):
        """
        Test that multiplying non-numeric inputs raises a TypeError.
        """
        with self.assertRaises(TypeError) as context:
            self.calc.multiply('ten', 20.3)
        self.assertEqual(str(context.exception), "'str' object cannot be interpreted as an integer")

    def test_non_numeric_input_divide(self):
        """
        Test that dividing non-numeric inputs raises a TypeError.
        """
        with self.assertRaises(TypeError) as context:
            self.calc.divide('ten', 20.3)
        self.assertEqual(str(context.exception), "'str' object cannot be interpreted as an integer")


if __name__ == '__main__':
    unittest.main()