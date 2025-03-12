# Simple Calculator in Python with Tkinter

## Detailed Project Description

This is a simple calculator application built using Python and the Tkinter library. The application provides a graphical user interface (GUI) for performing basic arithmetic operations such as addition, subtraction, multiplication, and division.

## API Documentation

### Modules

#### `main.py`

- **Functions**
  - `main()`: Entry point for the application.

#### `utils.py`

- **Functions**
  - `add(a, b)`: Returns the sum of `a` and `b`.
  - `subtract(a, b)`: Returns the difference between `a` and `b`.
  - `multiply(a, b)`: Returns the product of `a` and `b`.
  - `divide(a, b)`: Returns the quotient of `a` divided by `b`.

#### `calculator.py`

- **Classes**
  - `Calculator`
    - **Methods**
      - `add(a, b)`: Returns the sum of `a` and `b`.
      - `subtract(a, b)`: Returns the difference between `a` and `b`.
      - `multiply(a, b)`: Returns the product of `a` and `b`.
      - `divide(a, b)`: Returns the quotient of `a` divided by `b`.

#### `ui.py`

- **Classes**
  - `CalculatorApp`
    - **Methods**
      - `__init__(self, master)`: Initializes the application.
      - `create_widgets(self)`: Creates the UI widgets.
      - `on_button_click(self, value)`: Handles button click events.
      - `calculate_result(self)`: Calculates and displays the result.

#### `test_ui.py`

- **Classes**
  - `TestCalculatorApp`
    - **Methods**
      - `setUp(self)`: Sets up the test environment.
      - `tearDown(self)`: Tears down the test environment.
      - `test_button_clicks(self)`: Tests button click functionality.
      - `test_calculate_result(self)`: Tests result calculation.

#### `test_calculator.py`

- **Classes**
  - `TestCalculator`
    - **Methods**
      - `setUp(self)`: Sets up the test environment.
      - `test_addition(self)`: Tests addition operation.
      - `test_subtraction(self)`: Tests subtraction operation.
      - `test_multiplication(self)`: Tests multiplication operation.
      - `test_division(self)`: Tests division operation.

#### `example.py`

- **Functions**
  - `main()`: Example usage of the calculator.

## Installation Instructions

To install the Simple Calculator, you can use pip:

```bash
pip install simple-calculator
```

Alternatively, if you want to run the source code directly, clone the repository:

```bash
git clone https://github.com/yourusername/simple-calculator.git
cd simple-calculator
```

## Usage Examples

To run the calculator application, execute the `main.py` script:

```bash
python main.py
```

This will launch a window with a simple calculator interface where you can perform arithmetic operations.

## Features List

- Basic arithmetic operations (Addition, Subtraction, Multiplication, Division)
- User-friendly graphical interface using Tkinter
- Clear and equals buttons for convenience
- Error handling for invalid inputs

## Test Instructions

To run the tests, make sure you have pytest installed. If not, install it using pip:

```bash
pip install pytest
```

Then, navigate to the project directory and run the tests:

```bash
pytest
```

This will execute the unit tests in `test_ui.py` and `test_calculator.py`.

## Project Structure

The project structure is as follows:

```
simple-calculator/
├── main.py
├── utils.py
├── calculator.py
├── test_ui.py
├── test_calculator.py
├── ui.py
└── example.py
```

- **main.py**: Entry point for the application.
- **utils.py**: Utility functions (if any).
- **calculator.py**: Contains the Calculator class with arithmetic methods.
- **test_ui.py**: Unit tests for the UI components.
- **test_calculator.py**: Unit tests for the Calculator logic.
- **ui.py**: Contains the Tkinter application logic.
- **example.py**: Example usage of the calculator.

## Contributing Guidelines

Contributions to this project are welcome. Please follow these guidelines:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them with descriptive messages.
4. Push your branch to the forked repository.
5. Open a pull request on the original repository.

## License Information

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.