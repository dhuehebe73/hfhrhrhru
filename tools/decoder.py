#!/usr/bin/env python3
"""
ZIP+Base64 ile paketlenmiş Python dosyasından kaynak kodu çıkarır.
Hem encoder.py çıktısını hem SOFİYAN formatını destekler.

Kullanım: python decoder.py giris.py [cikti.py]
"""
import sys, os, base64, zipfile, io, ast, re

def find_b64_payload(source: str) -> str | None:
    """Kaynak koddan base64 payload stringini bul."""
    # Pattern 1: _PAYLOAD = """..."""  (encoder.py formatı)
    m = re.search(r'_PAYLOAD\s*=\s*"""([\s\S]*?)"""', source)
    if m:
        return m.group(1).replace("\n", "")

    # Pattern 2: SOFİYAN_VORTEX = """..."""
    m = re.search(r'SOFİYAN_VORTEX\s*=\s*"""([\s\S]*?)"""', source)
    if m:
        return m.group(1).replace("\n", "")

    # Pattern 3: genel b64decode("""...""") çağrısı
    m = re.search(r'b64decode\s*\(\s*"""([\s\S]*?)"""\s*\)', source)
    if m:
        return m.group(1).replace("\n", "")

    return None

def decode(in_path: str, out_path: str | None = None):
    if not os.path.isfile(in_path):
        sys.exit(f"Dosya bulunamadı: {in_path}")

    with open(in_path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()

    b64 = find_b64_payload(source)
    if not b64:
        sys.exit("Base64 payload bulunamadı. Desteklenmeyen format.")

    try:
        raw = base64.b64decode(b64.strip())
    except Exception as e:
        sys.exit(f"Base64 decode hatası: {e}")

    if raw[:2] != b"PK":
        sys.exit(f"ZIP sihirli baytları bulunamadı (got: {raw[:4].hex()})")

    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as e:
        sys.exit(f"ZIP açılamadı: {e}")

    names = zf.namelist()
    print(f"ZIP içeriği: {names}")

    # __main__.py'yi çıkar
    if "__main__.py" not in names:
        sys.exit("ZIP içinde __main__.py bulunamadı.")

    src = zf.read("__main__.py")

    # binary dosyaları listele ama çıkarma
    for name in names:
        if name != "__main__.py":
            info = zf.getinfo(name)
            data = zf.read(name)
            magic = data[:4].hex() if data else "boş"
            print(f"  [ATLAND] {name}: {info.file_size:,} bytes, magic={magic}")

    if out_path is None:
        base = os.path.splitext(in_path)[0]
        out_path = base + "_decoded.py"

    with open(out_path, "wb") as f:
        f.write(src)

    print(f"\nDecode edildi: {in_path} → {out_path}")
    print(f"  Kaynak boyutu: {len(src):,} bytes")
    print(f"\n=== İlk 50 satır ===")
    lines = src.decode("utf-8", errors="replace").split("\n")
    for i, line in enumerate(lines[:50], 1):
        print(f"{i:4}: {line}")
    if len(lines) > 50:
        print(f"... ({len(lines)-50} satır daha)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Kullanım: python decoder.py <giris.py> [cikti.py]")
        sys.exit(1)
    decode(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
