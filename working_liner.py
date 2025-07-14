import ast
import astor
import re

TARGET_FILE = "target_script.py"

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
        # Fallback: treat as non-class script
        return "\n".join(imports), None, None, {}, [], [], code  # last item is full raw code

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
'''
def convert_init(lines):
    exec_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("super().__init__()"):
            exec_lines.append("super(type(self), self).__init__()")
        elif stripped.startswith("self.") and "=" in stripped:
            left, right = stripped.split("=", 1)
            if "(" in left:
                exec_lines.append(stripped)
                continue
            attr = left.strip().split(".")[1]
            exec_lines.append(f"setattr(self, '{attr}', {right.strip()})")
        else:
            exec_lines.append(stripped)

    # PATCH: Fix lambda self usage
    for i, line in enumerate(exec_lines):
        exec_lines[i] = re.sub(
            r'command\s*=\s*lambda\s*:\s*self\.(\w+)\((.*?)\)',
            r'command=lambda s=self: s.\1(\2)',
            line
        )

    exec_code = "\\n".join(exec_lines).replace('"', '\\"').replace("'", "\\'")
    return f'lambda self: exec("{exec_code}")'
'''

def convert_init(lines):
    exec_lines = []
    for line in lines:
        stripped = line.strip()
        if 'collecting' in locals() and collecting:
            continue
        
        # Handle multi-line value (e.g., lists, dicts)
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

            # Keep layout assignment lines (like self.button.pack(...))
            if re.match(r"self\.\w+\.(pack|grid|place)\s*\(", stripped):
                exec_lines.append(stripped)
                continue

            # If LHS is a method call, keep as-is
            if "(" in left:
                exec_lines.append(stripped)
                continue

            attr = left.strip().split(".")[1]
            exec_lines.append(f"setattr(self, '{attr}', {right.strip()})")

        else:
            exec_lines.append(stripped)

    # PATCH: Fix lambda self usage for inline callbacks
    for i, line in enumerate(exec_lines):
        exec_lines[i] = re.sub(
            r'command\\s*=\\s*lambda\\s*:\\s*self\\.(\w+)\((.*?)\)',
            r'command=lambda s=self: s.\1(\2)',
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
        # CLASS-BASED LOGIC
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
        # NON-CLASS SCRIPT
        code = raw_code.replace('"', '\\"').replace("'", "\\'").replace("\n", "\\n")
        return f"{imports}; exec(\"{code}\")"

def convert_file(path):
    with open(path) as f:
        code = f.read()
    parts = extract_parts_ast(code)
    oneliner = build_oneliner(*parts)
    with open(path, "w") as f:
        f.write(oneliner)
    return oneliner

if __name__ == "__main__":
    print(convert_file(TARGET_FILE))