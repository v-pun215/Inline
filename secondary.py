# i accidentaly added this file to gitignore, here i was experimenting on techniques to convert program to a one-liner

import io
import os
import re
import sys
import zlib
import base64
import tokenize

inline_tag = "#Inlined;)"
target = "target_script.py"

def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def detect_file_encoding(raw):
    return tokenize.detect_encoding(io.BytesIO(raw).readline)[0]


def is_already_inlined(text):
    if inline_tag in text:
        return True
    return bool(re.search(r"base64\.b85decode\(.+?\).*exec\(\s*compile\(", text, re.DOTALL))


def build_one_liner(raw, enc):
    payload = base64.b85encode(zlib.compress(raw, 9)).decode("ascii")
    return (
        "import sys,base64,zlib;"
        f"exec(compile(zlib.decompress(base64.b85decode('{payload}')).decode('{enc}'),__file__,'exec'),"
        "sys.modules['__main__'].__dict__);" + inline_tag
    )


def write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.write("\n")
    os.replace(tmp, path)


def convert_in_place(path):
    if not os.path.isfile(path):
        print(f"[ERROR] not found: {path}", file=sys.stderr)
        return 2
    raw = read_bytes(path)
    try:
        enc = detect_file_encoding(raw)
    except Exception:
        enc = "utf-8"
    preview = ""
    try:
        preview = raw[:4096].decode(enc, errors="ignore")
    except Exception:
        preview = ""
    if is_already_inlined(preview):
        print("[ERROR] file already looks inlined; aborting", file=sys.stderr)
        return 1
    line = build_one_liner(raw, enc)
    write_atomic(path, line)
    print("[OK] converted to one-liner")
    return 0


if __name__ == "__main__":
    raise SystemExit(convert_in_place(target))