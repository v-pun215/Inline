import tkinter

app = tkinter.Tk()
app.title("Simple Tkinter App")
app.geometry("300x200")
def on_button_click():
    print("Button clicked!")
button = tkinter.Button(app, text="Click Me", command=on_button_click)
button.pack(pady=20)
app.mainloop()