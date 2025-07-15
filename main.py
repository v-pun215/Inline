import customtkinter as ctk
import tkinter.filedialog as fd
import subprocess
import ast
import astor
import re
import platform
import CTkMessagebox
import json
import os
import logging

os_name = platform.system().lower()

# ==============================
#           SETTINGS
# ==============================
DEFAULT_SETTINGS = {
    "theme": "blue",
    "appearance": "dark",
    "warn_on_overwrite": True
}

def load_settings():
    if not os.path.exists("settings.json"):
        with open("settings.json", "w") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4)
        return DEFAULT_SETTINGS
    with open("settings.json", "r") as f:
        return json.load(f)

settings = load_settings()

# ==============================
#         LOGGING SETUP
# ==============================
logging.basicConfig(filename="inline_debug.log", level=logging.INFO)

def log(msg):
    logging.info(msg)

# ==============================
#         CORE CONVERTER
# ==============================
def extract_parts_ast(code):
    tree = ast.parse(code)
    imports = []
    class_def = None
    instances = []
    calls = []

    for node in tree.body:
        if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            imports.append(astor.to_source(node).strip())
        elif isinstance(node, ast.ClassDef):
            class_def = node
        elif isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                if class_def and node.value.func.id == class_def.name:
                    instances.append(node.targets[0].id)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                calls.append((func.value.id, func.attr))

    if class_def is None:
        return "\n".join(imports), None, None, {}, [], [], code

    class_name = class_def.name
    base_expr = class_def.bases[0] if class_def.bases else None
    if isinstance(base_expr, ast.Name):
        base_class = base_expr.id
    elif isinstance(base_expr, ast.Attribute):
        base_class = astor.to_source(base_expr).strip()
    else:
        base_class = "object"

    methods = {}
    for item in class_def.body:
        if isinstance(item, ast.FunctionDef):
            method_lines = []
            for stmt in item.body:
                raw = ast.get_source_segment(code, stmt)
                if raw:
                    method_lines.extend(raw.splitlines())
            method_lines = [line.strip() for line in method_lines if line.strip()]
            arg_names = [arg.arg for arg in item.args.args]
            methods[item.name] = (arg_names, method_lines)

    return "; ".join(imports), class_name, base_class, methods, instances, calls

def convert_init(lines):
    exec_lines = []
    for line in lines:
        stripped = line.strip()
        if 'collecting' in locals() and collecting:
            continue

        if any(stripped.endswith(c) for c in ['[', '(', '{']) and '=' in stripped:
            multiline = [stripped]
            collecting = True
            continue
        if 'collecting' in locals() and collecting:
            multiline.append(stripped)
            if any(stripped.endswith(c) for c in [']', ')', '}']):
                full = ' '.join(multiline)
                left, right = full.split('=', 1)
                attr = left.strip().split('.')[1]
                exec_lines.append(f"setattr(self, '{attr}', {right.strip()})")
                del collecting
            continue

        if stripped.startswith("super().__init__()"):
            exec_lines.append("super(type(self), self).__init__()")

        elif stripped.startswith("self.") and "=" in stripped:
            left, right = stripped.split("=", 1)

            if re.match(r"self\.\w+\.(pack|grid|place)\s*\(", stripped):
                exec_lines.append(stripped)
                continue

            if "(" in left:
                exec_lines.append(stripped)
                continue

            attr = left.strip().split(".")[1]
            exec_lines.append(f"setattr(self, '{attr}', {right.strip()})")

        else:
            exec_lines.append(stripped)

    for i, line in enumerate(exec_lines):
        exec_lines[i] = re.sub(
            r'command\\s*=\\s*lambda\\s*:\\s*self\\.(\w+)\\((.*?)\\)',
            r'command=lambda s=self: s.\\1(\\2)',
            line
        )

    exec_code = "\\n".join(exec_lines).replace('"', '\\"').replace("'", "\\'")
    return f'lambda self: exec("{exec_code}")'

def convert_method(lines, args):
    args_str = ", ".join(args)
    if len(lines) == 1:
        return f"lambda {args_str}: {lines[0]}"
    else:
        joined = "\\n".join(lines).replace('"', '\\"').replace("'", "\\'")
        return f'lambda {args_str}: exec("{joined}")'

def build_oneliner(imports, class_name, base_class, methods, instances, calls, raw_code=None):
    if class_name:
        method_lines = []
        for name, (args, body) in methods.items():
            if name == "__init__":
                method_lines.append(f"'__init__': {convert_init(body)}")
            else:
                method_lines.append(f"'{name}': {convert_method(body, args)}")
        method_str = ", ".join(method_lines)
        class_def = f"{class_name} = type('{class_name}', ({base_class},), {{{method_str}}})"
        instance_str = "; ".join(f"{i} = {class_name}()" for i in instances)
        call_str = "; ".join(f"{i}.{m}()" for i, m in calls)
        return f"{imports}; {class_def}; {instance_str}; {call_str}"
    else:
        code = raw_code.replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")
        return f"{imports}; exec(\"{code}\")"

def convert_file(path):
    with open(path) as f:
        code = f.read()

    if 'type(' in code and 'exec(' in code:
        raise Exception("This file already appears to be converted.")

    parts = extract_parts_ast(code)
    oneliner = build_oneliner(*parts)
    with open(path, "w") as f:
        f.write(oneliner)
    return oneliner

# ==============================
#            GUI
# ==============================
ctk.set_appearance_mode(settings["appearance"])
ctk.set_default_color_theme(settings["theme"])

class InlineGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Inline")
        self.geometry("640x420")
        self.resizable(False, False)

        self.file_path = ctk.StringVar(value="No file selected")

        ctk.CTkLabel(self, text="Target File:").pack(pady=(20, 5))
        self.path_label = ctk.CTkEntry(self, textvariable=self.file_path, width=400, placeholder_text="Select a Python file to convert")
        self.path_label.pack()

        browse = ctk.CTkButton(self, text="Browse", command=self.browse_file)
        browse.pack(pady=10)

        self.convert_button = ctk.CTkButton(self, text="Convert to One-Liner", command=self.convert)
        self.convert_button.pack(pady=5)

        self.run_button = ctk.CTkButton(self, text="Run Target Script", command=self.run_file)
        self.run_button.pack(pady=5)

        clear_button = ctk.CTkButton(self, text="Clear Output", command=lambda: self.output.delete("1.0", "end"))
        clear_button.pack(pady=5)

        self.output = ctk.CTkTextbox(self, width=560, height=130)
        self.output.pack(pady=10)

        self.status = ctk.CTkLabel(self, text="Ready.", anchor="w")
        self.status.place(relx=0.5, y=400, anchor="center")

    def browse_file(self):
        path = fd.askopenfilename(filetypes=[("Python Files", "*.py *.pyw")])
        if path:
            self.file_path.set(path)
            log(f"Selected file: {path}")

    def convert(self):
        try:
            if settings.get("warn_on_overwrite", True):
                msg = CTkMessagebox.CTkMessagebox(title="Are you sure?",
                    message="This process is NOT reversible. There is no guarantee that the target script will work. By clicking OK, you deem yourself liable for whatever you do.",
                    icon="cancel", option_2="Yes", option_1="No")
                if msg.get() == "No":
                    return
            self.status.configure(text="Converting...")
            result = convert_file(self.file_path.get())
            self.output.delete("1.0", "end")
            self.output.insert("end", "[SUCCESS] Conversion complete.\n")
            self.output.insert("end", result)
            self.status.configure(text="Conversion complete.")
            log("Conversion successful.")
        except SyntaxError as se:
            self.output.insert("end", f"[SYNTAX ERROR] {se}\n")
            self.status.configure(text="Syntax error.")
            log(f"Syntax error: {se}")
        except Exception as e:
            self.output.insert("end", f"[ERROR] {e}\n")
            self.status.configure(text="Error during conversion.")
            log(f"Error: {e}")

    def run_file(self):
        try:
            self.status.configure(text="Running script...")
            cmd = ["python", self.file_path.get()] if os_name == "windows" else ["python3", self.file_path.get()]
            subprocess.run(cmd, check=False)
            self.status.configure(text="Script execution finished.")
            log("Script executed.")
        except Exception as e:
            self.output.insert("end", f"[ERROR] Failed to run script: {e}\n")
            self.status.configure(text="Execution failed.")
            log(f"Execution failed: {e}")

if __name__ == "__main__":
    app = InlineGUI()
    app.mainloop()