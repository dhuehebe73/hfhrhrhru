#!/usr/bin/env python3
"""
Universal Python ZIP+Base64 Decoder
Desteklenen formatlar:
  - SOFİYAN Tool  (triple-quoted b64 string)
  - encoder.py ciktisi (_PAYLOAD = triple-quoted)
  - exec(compile(zlib.decompress(base64.b64decode(...))))
  - marshal + base64
  - base64 + zlib inline
  - tek satir b64 string assignment
"""

import sys, os, re, base64, zipfile, io, zlib, marshal, dis, ast

# ─────────────────────────────────────────────
# RENK
# ─────────────────────────────────────────────
R  = "\033[91m"
G  = "\033[92m"
Y  = "\033[93m"
B  = "\033[94m"
M  = "\033[95m"
C  = "\033[96m"
W  = "\033[97m"
DIM= "\033[2m"
RST= "\033[0m"
BOLD="\033[1m"

def ok(msg):  print(f"{G}[+]{RST} {msg}")
def inf(msg): print(f"{C}[*]{RST} {msg}")
def warn(msg):print(f"{Y}[!]{RST} {msg}")
def err(msg): print(f"{R}[X]{RST} {msg}")
def hdr(msg): print(f"\n{BOLD}{M}{'─'*50}{RST}\n{BOLD}    {msg}{RST}\n{M}{'─'*50}{RST}")

# ─────────────────────────────────────────────
# PAYLOAD ÇIKARICI — çoklu pattern
# ─────────────────────────────────────────────

PATTERNS = [
    # triple-quote assignments  →  VAR = """..."""
    (r'[A-Za-z_][A-Za-z0-9_]*\s*=\s*"""([\s\S]*?)"""',              "triple-quote b64"),
    # b64decode("""...""")
    (r'b64decode\s*\(\s*"""([\s\S]*?)"""\s*\)',                       "b64decode triple-quote"),
    # b64decode("...")  single line
    (r'b64decode\s*\(\s*["\']([A-Za-z0-9+/=\s]{40,}?)["\']\s*\)',   "b64decode single-quote"),
    # b64decode(b"...")
    (r'b64decode\s*\(\s*b["\']([A-Za-z0-9+/=\s]{40,}?)["\']\s*\)',  "b64decode bytes"),
    # bare long b64 string (>200 chars, no spaces inside)
    (r'["\']([A-Za-z0-9+/=]{200,})["\']',                            "bare b64 string"),
]

def find_payloads(source: str) -> list[tuple[str,str]]:
    """Kaynak koddan tüm olası b64 payload'ları bul."""
    results = []
    for pattern, label in PATTERNS:
        for m in re.finditer(pattern, source):
            raw = m.group(1).replace("\n","").replace(" ","").strip()
            if len(raw) < 40:
                continue
            # padding düzelt
            raw += "=" * (-len(raw) % 4)
            results.append((raw, label))
    # deduplicate by value
    seen = set()
    unique = []
    for r, l in results:
        if r not in seen:
            seen.add(r)
            unique.append((r, l))
    return unique

# ─────────────────────────────────────────────
# DECODE DENEMELERİ
# ─────────────────────────────────────────────

def try_decode(b64: str) -> tuple[bytes|None, str]:
    """b64 string'i decode et, sıkıştırma varsa aç."""
    try:
        raw = base64.b64decode(b64)
    except Exception as e:
        return None, f"base64 hatası: {e}"

    # ZIP?
    if raw[:2] == b"PK":
        return raw, "zip"
    # zlib?
    if raw[:2] in (b'\x78\x9c', b'\x78\xda', b'\x78\x01'):
        try:
            return zlib.decompress(raw), "zlib"
        except:
            pass
    # marshal (Python bytecode)?
    if raw[:4] in (b'\xe3\x00\x00\x00', b'\x63\x00\x00\x00'):
        return raw, "marshal"
    # gzip?
    if raw[:2] == b'\x1f\x8b':
        import gzip
        try:
            return gzip.decompress(raw), "gzip"
        except:
            pass
    # ELF binary?
    if raw[:4] == b'\x7fELF':
        return raw, "elf-binary"
    # düz metin?
    try:
        raw.decode("utf-8")
        return raw, "utf8-text"
    except:
        pass
    return raw, "unknown"

# ─────────────────────────────────────────────
# ZIP İŞLEYİCİ
# ─────────────────────────────────────────────

def process_zip(data: bytes, out_dir: str):
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        err("ZIP açılamadı.")
        return

    names = zf.namelist()
    inf(f"ZIP içeriği: {names}")

    for name in names:
        info = zf.getinfo(name)
        content = zf.read(name)
        magic = content[:4].hex() if content else "boş"
        size = info.file_size

        # Python dosyası
        if name.endswith(".py") or name == "__main__.py":
            out_path = os.path.join(out_dir, name.replace("/","_"))
            with open(out_path, "wb") as f:
                f.write(content)
            ok(f"Python kaynağı çıkarıldı → {out_path}  ({size:,} bytes)")

            # İçinde de encode var mı? recursive dene
            try:
                inner_src = content.decode("utf-8", errors="replace")
                inner_payloads = find_payloads(inner_src)
                if inner_payloads:
                    warn(f"  {name} içinde iç encode bulundu, recursive decode deneniyor...")
                    for pb64, plabel in inner_payloads:
                        inner_raw, inner_type = try_decode(pb64)
                        if inner_raw and inner_type == "zip":
                            inner_dir = os.path.join(out_dir, f"inner_{name.replace('.py','')}")
                            os.makedirs(inner_dir, exist_ok=True)
                            process_zip(inner_raw, inner_dir)
            except:
                pass

        # Native binary / diğer
        else:
            out_path = os.path.join(out_dir, os.path.basename(name) or name.replace("/","_"))
            with open(out_path, "wb") as f:
                f.write(content)
            if magic == "7f454c46":
                warn(f"ELF binary atlandı (compile edilmiş, decode edilemez) → {out_path}  ({size:,} bytes)")
            elif magic == "4d5a":
                warn(f"PE binary atlandı → {out_path}  ({size:,} bytes)")
            else:
                inf(f"Dosya çıkarıldı → {out_path}  ({size:,} bytes, magic={magic})")

# ─────────────────────────────────────────────
# ANA DECODE FONKSİYONU
# ─────────────────────────────────────────────

def decode_file(in_path: str, out_dir: str | None = None):
    hdr(f"DECODE: {os.path.basename(in_path)}")

    if not os.path.isfile(in_path):
        err(f"Dosya bulunamadı: {in_path}")
        sys.exit(1)

    with open(in_path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()

    inf(f"Dosya boyutu: {os.path.getsize(in_path):,} bytes")
    inf(f"Satır sayısı: {source.count(chr(10))}")

    if out_dir is None:
        base = os.path.splitext(in_path)[0]
        out_dir = base + "_decoded"
    os.makedirs(out_dir, exist_ok=True)
    inf(f"Çıktı dizini: {out_dir}")

    payloads = find_payloads(source)
    if not payloads:
        err("Encode edilmiş payload bulunamadı.")
        sys.exit(1)

    inf(f"{len(payloads)} payload bulundu.\n")
    found_any = False

    for i, (b64, label) in enumerate(payloads, 1):
        print(f"{DIM}[{i}/{len(payloads)}] Pattern: {label}  |  b64 uzunluğu: {len(b64)}{RST}")
        raw, dtype = try_decode(b64)
        if raw is None:
            warn(f"  Decode başarısız: {dtype}")
            continue

        inf(f"  Tip: {dtype}  |  Boyut: {len(raw):,} bytes")
        found_any = True

        if dtype == "zip":
            process_zip(raw, out_dir)

        elif dtype in ("zlib", "gzip"):
            # Sıkıştırılmış — Python kodu mu?
            try:
                text = raw.decode("utf-8")
                out_path = os.path.join(out_dir, f"payload_{i}.py")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(text)
                ok(f"Python kaynağı çıkarıldı → {out_path}")
            except:
                out_path = os.path.join(out_dir, f"payload_{i}.bin")
                with open(out_path, "wb") as f:
                    f.write(raw)
                inf(f"Binary çıkarıldı → {out_path}")

        elif dtype == "marshal":
            try:
                code = marshal.loads(raw)
                out_path = os.path.join(out_dir, f"payload_{i}_bytecode.txt")
                with open(out_path, "w") as f:
                    old_stdout = sys.stdout
                    sys.stdout = f
                    dis.dis(code)
                    sys.stdout = old_stdout
                ok(f"Marshal bytecode disassemble edildi → {out_path}")
            except Exception as e:
                warn(f"  Marshal decode hatası: {e}")

        elif dtype == "elf-binary":
            warn(f"  ELF binary — Cython/C ile compile edilmiş, Python kaynağı çıkarılamaz.")

        elif dtype == "utf8-text":
            out_path = os.path.join(out_dir, f"payload_{i}.py")
            with open(out_path, "wb") as f:
                f.write(raw)
            ok(f"Metin payload çıkarıldı → {out_path}")

        else:
            out_path = os.path.join(out_dir, f"payload_{i}.bin")
            with open(out_path, "wb") as f:
                f.write(raw)
            inf(f"Binary çıkarıldı → {out_path}")

    if not found_any:
        err("Hiçbir payload decode edilemedi.")
        sys.exit(1)

    # Çıkarılan Python dosyalarını göster
    py_files = [f for f in os.listdir(out_dir) if f.endswith(".py")]
    if py_files:
        print()
        hdr("ÇIKARILAN KAYNAK KODLARI")
        for fname in py_files:
            fpath = os.path.join(out_dir, fname)
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            lines = content.split("\n")
            print(f"\n{BOLD}{Y}── {fname} ({len(lines)} satır) ──{RST}")
            for j, line in enumerate(lines[:80], 1):
                print(f"{DIM}{j:4}│{RST} {line}")
            if len(lines) > 80:
                print(f"{DIM}     ... ({len(lines)-80} satır daha — tam dosya: {fpath}){RST}")

    print(f"\n{G}{BOLD}Tamamlandı.{RST} Çıktılar: {out_dir}/\n")

# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"{BOLD}Kullanım:{RST} python decoder.py <giris.py> [cikti_dizini]")
        print(f"\nDesteklenen formatlar:")
        print("  • SOFİYAN Tool  (SOFİYAN_VORTEX = \"\"\"...\"\"\")")
        print("  • encoder.py    (_PAYLOAD = \"\"\"...\"\"\")")
        print("  • zlib+b64      exec(compile(zlib.decompress(base64.b64decode(...))))")
        print("  • marshal+b64")
        print("  • bare b64 string assignment")
        sys.exit(0)
    decode_file(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
