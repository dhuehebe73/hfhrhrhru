#!/usr/bin/env python3
"""
Python kaynak kodunu ZIP+Base64 ile paketler.
Kullanım: python encoder.py kaynak.py [cikti.py]
"""
import sys, os, zipfile, base64, io, textwrap

TEMPLATE = '''\
import os, sys, base64, subprocess, atexit

_HOME = os.path.expanduser("~")
_DIR  = os.path.join(_HOME, ".cache", "_pyx")
_ZIP  = os.path.join(_DIR, "_run.zip")

def _cleanup():
    try:
        import shutil
        if os.path.exists(_DIR):
            shutil.rmtree(_DIR, ignore_errors=True)
    except: pass

atexit.register(_cleanup)

_PAYLOAD = """{b64}"""

try:
    _data = base64.b64decode(_PAYLOAD)
except Exception:
    sys.exit("Payload bozuk.")

os.makedirs(_DIR, exist_ok=True)
with open(_ZIP, "wb") as _f:
    _f.write(_data)

try:
    subprocess.run(
        [sys.executable, _ZIP] + sys.argv[1:],
        check=True, timeout=300, env=os.environ.copy()
    )
except subprocess.CalledProcessError as e:
    sys.exit(e.returncode)
except subprocess.TimeoutExpired:
    sys.exit("Timeout")
except Exception as e:
    sys.exit(str(e))
'''

def encode(src_path: str, out_path: str | None = None):
    if not os.path.isfile(src_path):
        sys.exit(f"Dosya bulunamadı: {src_path}")

    with open(src_path, "rb") as f:
        src_bytes = f.read()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("__main__.py", src_bytes)
    zip_bytes = buf.getvalue()

    b64 = base64.b64encode(zip_bytes).decode()
    # wrap at 76 chars for readability
    b64_wrapped = "\n".join(textwrap.wrap(b64, 76))

    result = TEMPLATE.format(b64=b64_wrapped)

    if out_path is None:
        base = os.path.splitext(src_path)[0]
        out_path = base + "_enc.py"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Encoded: {src_path} → {out_path}")
    print(f"  Kaynak: {len(src_bytes):,} bytes")
    print(f"  ZIP:    {len(zip_bytes):,} bytes")
    print(f"  B64:    {len(b64):,} chars")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Kullanım: python encoder.py <kaynak.py> [cikti.py]")
        sys.exit(1)
    encode(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
