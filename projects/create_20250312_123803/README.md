# Simple Calculator in Python with Tkinter

[![PyPI version](https://badge.fury.io/py/simple-calculator.svg)](https://pypi.org/project/simple-calculator/)
[![CI status](https://github.com/yourusername/simple-calculator/actions/workflows/python-app.yml/badge.svg)](https://github.com/yourusername/simple-calculator/actions)

## Detailed Project Description

This is a simple calculator application built using Python and the Tkinter library. The application provides a graphical user interface (GUI) for performing basic arithmetic operations such as addition, subtraction, multiplication, and division.

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

## API Reference

### Classes

#### Calculator
The `Calculator` class provides methods to perform arithmetic operations:

- **add(a, b)**: Returns the sum of `a` and `b`.
- **subtract(a, b)**: Returns the difference between `a` and `b`.
- **multiply(a, b)**: Returns the product of `a` and `b`.
- **divide(a, b)**: Returns the quotient of `a` divided by `b`.

### Functions

#### main()
The entry point for the application.

## Contributing Guidelines

Contributions to this project are welcome. Please follow these guidelines:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them with descriptive messages.
4. Push your branch to the forked repository.
5. Open a pull request on the original repository.

## License Information

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

Feel free to reach out if you have any questions or need further assistance!