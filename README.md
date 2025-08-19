# Inline
Turn your Python scripts into outrageous single-line monstrosities.

Because code can be both horrifying and beautiful.

### Planned Features
- More compatibility
- Less bugs

## What is Inline?
Inline is a Python converter that takes multi-line Python scripts and transforms them into tightly packed, functional one-liners. Ideal for fun, code golfing, or just confusing your future self.

It supports:
- Class-based GUI apps (like customtkinter/tkinter)
- Inline lambdas and exec-based method handling
- Variable assignments, setattr, even super() calls — all crunched into one line

## Quickstart
- Run main.py using ```python3 main.py```
- Select target script using the GUI.

## Example
### Input (target_script.py)
```
import customtkinter

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.geometry("400x150")
        self.button = customtkinter.CTkButton(self, text="Click Me", command=self.say_hi)
        self.button.pack(pady=20)

    def say_hi(self):
        print("Hi there!")

app = App()
app.mainloop()
```

### Output (after running main.py)
```
import customtkinter; App = type('App', (customtkinter.CTk,), {'__init__': lambda self: exec("super(type(self), self).__init__()\nself.geometry(\"400x150\")\nsetattr(self, 'button', customtkinter.CTkButton(self, text=\"Click Me\", command=self.say_hi))\nself.button.pack(pady=20)"), 'say_hi': lambda self: print("Hi there!")}); app = App(); app.mainloop()
```

## How It Works
- Uses ast to parse and extract class definitions, methods, and function calls.
- Wraps method bodies in lambda self: exec(...) style lambdas.
- Converts assignments to setattr(...) for better flexibility.
- Falls back to exec(...) for non-class scripts.

## ⚠️ Warning
This is for fun. Don’t use Inline in production unless you enjoy debugging soul-crushing one-liners.
