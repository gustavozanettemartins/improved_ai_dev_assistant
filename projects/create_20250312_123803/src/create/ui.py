import tkinter as tk

class CalculatorUI:
    """Class to create a simple calculator GUI using Tkinter."""
    
    def __init__(self, master):
        self.master = master
        self.master.title("Simple Calculator")
        
        # Create an entry widget for displaying expressions and results
        self.display = tk.Entry(master, width=40, borderwidth=5, font=("Arial", 16))
        self.display.grid(row=0, column=0, columnspan=4, padx=20, pady=20)
        
        # Define buttons with updated layout
        buttons = [
            ('7', 1, 0), ('8', 1, 1), ('9', 1, 2), ('/', 1, 3),
            ('4', 2, 0), ('5', 2, 1), ('6', 2, 2), ('*', 2, 3),
            ('1', 3, 0), ('2', 3, 1), ('3', 3, 2), ('-', 3, 3),
            ('0', 4, 0), ('.', 4, 1), ('=', 4, 2), ('+', 4, 3),
            ('C', 5, 0)
        ]
        
        # Create and place buttons on the grid with updated padding
        for (text, row, col) in buttons:
            button = tk.Button(master, text=text, width=10, height=2,
                               command=lambda t=text: self.on_button_click(t),
                               font=("Arial", 14))
            button.grid(row=row, column=col, padx=10, pady=10)
    
    def on_button_click(self, char):
        """Handle button click events."""
        if char == 'C':
            # Clear the display
            self.display.delete(0, tk.END)
        elif char == '=':
            try:
                # Evaluate the expression and update the display
                result = str(eval(self.display.get()))
                self.display.delete(0, tk.END)
                self.display.insert(0, result)
            except Exception as e:
                # Handle errors (e.g., division by zero)
                self.display.delete(0, tk.END)
                self.display.insert(0, "Error")
        else:
            # Append the character to the display
            current = self.display.get()
            self.display.delete(0, tk.END)
            self.display.insert(0, current + char)

if __name__ == "__main__":
    root = tk.Tk()
    app = CalculatorUI(root)
    root.mainloop()