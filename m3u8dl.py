#!/usr/bin/env python3
"""
m3u8dl.py — HLS Stream Finder & Downloader
Scrapes any webpage for .m3u8 links, lists them, lets you pick,
merges video+audio if needed, downloads with real-time progress.

Usage:
    python m3u8dl.py                         # prompt for URL
    python m3u8dl.py <page-or-m3u8-url>
    python m3u8dl.py <url> -o ~/Downloads

Requirements:
    pip install requests
    ffmpeg + ffprobe in PATH  (https://ffmpeg.org)
"""

import sys, os, re, time, shutil, argparse, subprocess, base64, json
from urllib.parse import urljoin, urlparse
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests not installed. Run: pip install requests")
    sys.exit(1)

# ── ANSI ──────────────────────────────────────────────────────────────────────
R  = "\033[0m";  B  = "\033[1m";  D  = "\033[2m"
GR = "\033[92m"; CY = "\033[96m"; YE = "\033[93m"
RE = "\033[91m"; BL = "\033[94m"; MA = "\033[95m"

def c(t, col): return f"{col}{t}{R}"
def bold(t):   return f"{B}{t}{R}"
def dim(t):    return f"{D}{t}{R}"

def sep(w=65): return dim("─" * w)

# ── Format helpers ─────────────────────────────────────────────────────────────
def fmt_bytes(n: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

def fmt_time(s) -> str:
    if s is None or s < 0: return "--:--"
    s = int(s); h, r = divmod(s, 3600); m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def bar(pct: float, w=35) -> str:
    f = int(w * pct / 100)
    return "█" * f + "░" * (w - f)

def _clear(): sys.stdout.write("\r" + " " * 100 + "\r"); sys.stdout.flush()

# ── Stream labeller ────────────────────────────────────────────────────────────
def label(url: str) -> str:
    part = url.split("?")[0].rstrip("/")
    seg  = part.split("/")[-1].lower()   # e.g. "1080.m3u8", "audio-tur-1.m3u8"
    name = seg.replace(".m3u8", "")

    if "audio" in name:
        lang = (re.search(r'audio[_-]?([a-z]{2,4})', name) or
                re.search(r'[_-]([a-z]{2,4})\d*$', name))
        lang = lang.group(1).upper() if lang else "?"
        return f"🔊  Audio  [{lang}]"

    for q in ("4320","2160","1440","1080","720","480","360","240","144"):
        if q in name or q in url:
            return f"🎬  {q}p Video"

    if "master" in name or "index" in name or "playlist" in name:
        return f"📋  Master playlist"

    return f"📺  {name or 'stream'}"


# ── M3U8 finder ────────────────────────────────────────────────────────────────
_M3U8_RE = re.compile(r'https?://[^\s\'"<>\)\]\\]+\.m3u8(?:[^\s\'"<>\)\]\\]*)?', re.I)
_REL_RE  = re.compile(r'''['"](/[^'"<>\s]+\.m3u8[^'"<>\s]*)''', re.I)

def _extract(text: str, base: str = "") -> set[str]:
    found = set(_M3U8_RE.findall(text))

    # Relative paths
    if base:
        for m in _REL_RE.finditer(text):
            found.add(urljoin(base, m.group(1)))

    # base64-encoded blobs (common in film sites)
    for m in re.finditer(r'''["']([A-Za-z0-9+/]{60,}={0,2})["']''', text):
        try:
            dec = base64.b64decode(m.group(1)).decode("utf-8", errors="ignore")
            found.update(_M3U8_RE.findall(dec))
        except Exception:
            pass

    # JSON-embedded links  {file:"..."} / {src:"..."}
    for m in re.finditer(r'''(?:file|src|url|stream|hls)\s*[=:]\s*["']([^"']+\.m3u8[^"']*)''', text, re.I):
        u = m.group(1)
        found.add(urljoin(base, u) if u.startswith("/") else u)

    return found


_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
}


def scrape(page_url: str) -> list[str]:
    """Fetch a webpage and hunt for every .m3u8 URL inside it."""
    sess = requests.Session()
    sess.headers.update(_HEADERS)

    resp = sess.get(page_url, timeout=25, allow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    base = resp.url

    found = _extract(html, base)

    # Recurse into <iframe> src (max 6)
    for m in re.finditer(r'''<iframe[^>]+src=["']([^"']+)["']''', html, re.I):
        iframe_url = urljoin(base, m.group(1))
        if iframe_url == base:
            continue
        try:
            ir = sess.get(iframe_url, timeout=15,
                          headers={**_HEADERS, "Referer": base})
            found.update(_extract(ir.text, iframe_url))
        except Exception:
            pass
        if len(found) >= 30:
            break

    # Some sites embed a separate JS file that has the stream URL
    js_urls = re.findall(r'''<script[^>]+src=["']([^"']+\.js[^"']*)["']''', html, re.I)
    for js_rel in js_urls[:8]:
        js_url = urljoin(base, js_rel)
        try:
            jr = sess.get(js_url, timeout=10, headers={**_HEADERS, "Referer": base})
            found.update(_extract(jr.text, js_url))
        except Exception:
            pass
        if len(found) >= 30:
            break

    return list(found)


# ── Master M3U8 parser ─────────────────────────────────────────────────────────
def parse_master(url: str, referer: str = "") -> list[dict]:
    """
    If the m3u8 is a master playlist, return all variant streams.
    Returns list of {url, bandwidth, resolution, name}.
    """
    hdrs = {**_HEADERS}
    if referer:
        hdrs["Referer"] = referer

    try:
        r = requests.get(url, headers=hdrs, timeout=15)
        r.raise_for_status()
        text = r.text
    except Exception:
        return []

    if "#EXTM3U" not in text:
        return []

    variants = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXT-X-STREAM-INF"):
            bw  = re.search(r'BANDWIDTH=(\d+)', line)
            res = re.search(r'RESOLUTION=(\d+x\d+)', line)
            nm  = re.search(r'NAME="([^"]+)"', line)
            bw  = int(bw.group(1)) if bw else 0
            res = res.group(1) if res else ""
            nm  = nm.group(1) if nm else ""
            if i + 1 < len(lines):
                seg = lines[i + 1].strip()
                full_url = urljoin(url, seg) if not seg.startswith("http") else seg
                variants.append({"url": full_url, "bandwidth": bw,
                                 "resolution": res, "name": nm})
            i += 2
        elif line.startswith("#EXT-X-MEDIA") and 'TYPE=AUDIO' in line:
            uri = re.search(r'URI="([^"]+)"', line)
            lang = re.search(r'LANGUAGE="([^"]+)"', line)
            nm   = re.search(r'NAME="([^"]+)"', line)
            if uri:
                au = urljoin(url, uri.group(1)) if not uri.group(1).startswith("http") else uri.group(1)
                lang_s = lang.group(1).upper() if lang else "?"
                nm_s   = nm.group(1) if nm else lang_s
                variants.append({"url": au, "bandwidth": 0,
                                 "resolution": "", "name": f"audio-{lang_s.lower()}", "is_audio": True})
            i += 1
        else:
            i += 1

    return sorted(variants, key=lambda v: v["bandwidth"], reverse=True)


# ── ffprobe duration ───────────────────────────────────────────────────────────
def probe_duration(url: str, referer: str = "") -> float | None:
    if not shutil.which("ffprobe"):
        return None
    env_hdrs = f"referer: {referer}" if referer else ""
    cmd = [
        "ffprobe", "-v", "error",
        "-protocol_whitelist", "https,http,tls,tcp,crypto,file,m3u8,hls",
    ]
    if env_hdrs:
        cmd += ["-headers", f"Referer: {referer}\r\n"]
    cmd += [
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return float(r.stdout.strip())
    except Exception:
        return None


# ── HLS download via ffmpeg ────────────────────────────────────────────────────
def download_hls(video_url: str, audio_url: str | None,
                 output: str, referer: str = "") -> bool:
    if not shutil.which("ffmpeg"):
        print(f"\n  {c('✗ ffmpeg not found in PATH', RE)}")
        print(f"  Install from https://ffmpeg.org/download.html")
        return False

    hdrs = f"Referer: {referer}\r\nUser-Agent: {_HEADERS['User-Agent']}\r\n"

    # Probe duration for progress
    sys.stdout.write(f"  {c('⟳', CY)} Probing stream duration…")
    sys.stdout.flush()
    duration = probe_duration(video_url, referer)
    _clear()

    inputs = []
    if referer:
        inputs += ["-headers", hdrs]
    inputs += ["-i", video_url]
    if audio_url:
        if referer:
            inputs += ["-headers", hdrs]
        inputs += ["-i", audio_url]

    cmd = (["ffmpeg", "-y",
            "-protocol_whitelist", "https,http,tls,tcp,crypto,file,m3u8,hls"] +
           inputs +
           (["-map", "0:v", "-map", "1:a"] if audio_url else []) +
           ["-c", "copy", "-progress", "pipe:1", "-nostats", output])

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True,
                                bufsize=1, universal_newlines=True)
    except FileNotFoundError:
        print(f"  {c('✗ ffmpeg not found', RE)}")
        return False

    start      = time.time()
    last_print = 0.0
    cur_time   = 0.0
    cur_size   = 0
    speed_x    = 0.0

    for raw in proc.stdout:
        line = raw.strip()
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip(); v = v.strip()

        if k == "out_time_ms":
            try: cur_time = int(v) / 1_000_000
            except: pass
        elif k == "total_size":
            try: cur_size = int(v)
            except: pass
        elif k == "speed":
            try: speed_x = float(v.replace("x", ""))
            except: pass

        if k == "progress":
            now = time.time()
            if now - last_print < 0.1:
                continue
            last_print = now
            elapsed = now - start

            if duration and duration > 0:
                pct     = min(cur_time / duration * 100, 100)
                eta     = ((duration - cur_time) / speed_x) if speed_x > 0 else None
                pct_s   = c(f"{pct:5.1f}%", GR)
                bar_s   = c(f"[{bar(pct)}]", CY)
                size_s  = c(fmt_bytes(cur_size), YE)
                eta_s   = c(fmt_time(eta), BL)
                ela_s   = c(fmt_time(elapsed), D)
                spd_s   = c(f"{speed_x:.2f}x", MA) if speed_x else dim("--x")
                line_s  = (f"\r  {bar_s} {pct_s} │ {size_s} │ "
                           f"{spd_s} │ ETA {eta_s} │ {ela_s}  ")
            else:
                pos_s  = c(fmt_time(cur_time), BL)
                size_s = c(fmt_bytes(cur_size), YE)
                ela_s  = c(fmt_time(elapsed), D)
                spd_s  = c(f"{speed_x:.2f}x", MA) if speed_x else dim("--x")
                line_s = (f"\r  ⟳ {pos_s} processed │ {size_s} │ {spd_s} │ {ela_s}  ")

            sys.stdout.write(line_s)
            sys.stdout.flush()

    proc.wait()
    _clear()

    if proc.returncode == 0:
        elapsed = time.time() - start
        size = os.path.getsize(output) if os.path.exists(output) else cur_size
        print(f"  {c('✓', GR)} {bold(os.path.basename(output))} "
              f"({c(fmt_bytes(size), YE)}) "
              f"in {c(fmt_time(elapsed), BL)}")
        return True
    else:
        print(f"  {c('✗ ffmpeg exited with error', RE)}")
        return False


# ── Menu helpers ───────────────────────────────────────────────────────────────
def pick_streams(streams: list[str], referer: str) -> tuple[str | None, str | None]:
    """
    Show numbered list of found streams.
    Returns (video_url, audio_url).  audio_url may be None.
    """
    # Expand master playlists
    expanded = []
    for url in streams:
        variants = parse_master(url, referer)
        if variants:
            expanded.extend(v["url"] for v in variants)
        else:
            expanded.append(url)

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for u in expanded:
        if u not in seen:
            seen.add(u)
            unique.append(u)

    if not unique:
        return None, None

    videos = [u for u in unique if "audio" not in u.split("?")[0].split("/")[-1].lower()]
    audios = [u for u in unique if "audio" in u.split("?")[0].split("/")[-1].lower()]

    print()
    print(f"  {bold('Found streams:')}\n")
    all_streams = unique
    for i, u in enumerate(all_streams, 1):
        print(f"    {c(f'[{i}]', CY)} {c(label(u), B)}  {dim(u[:80])}")
    print()

    # Video selection
    video_url = None
    if videos:
        # Pre-select best video quality (largest number in name)
        def _quality(u):
            m = re.search(r'(\d+)', u.split("/")[-1].split("?")[0])
            return int(m.group(1)) if m else 0
        best_idx = all_streams.index(max(videos, key=_quality)) + 1
        while True:
            raw = input(f"  {c('→', GR)} Select VIDEO stream [1-{len(all_streams)}]"
                        f" (default {best_idx}): ").strip()
            if not raw:
                raw = str(best_idx)
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(all_streams):
                    video_url = all_streams[idx]
                    break
            except ValueError:
                pass
            print(f"  {c('Invalid.', RE)}")
    elif unique:
        video_url = unique[0]

    # Audio selection (optional)
    audio_url = None
    if audios and shutil.which("ffmpeg"):
        print()
        print(f"  {c('Audio tracks found:', D)}\n")
        for i, u in enumerate(audios, 1):
            print(f"    {c(f'[{i}]', CY)} {c(label(u), B)}  {dim(u[:80])}")
        print(f"    {c('[0]', CY)} Skip / no separate audio")
        print()
        while True:
            raw = input(f"  {c('→', GR)} Select AUDIO track [0-{len(audios)}]: ").strip() or "0"
            if raw == "0":
                break
            try:
                idx = int(raw) - 1
                if 0 <= idx < len(audios):
                    audio_url = audios[idx]
                    break
            except ValueError:
                pass
            print(f"  {c('Invalid.', RE)}")

    return video_url, audio_url


def safe_filename(title: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", title).strip()[:100]


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="HLS Stream Finder & Downloader")
    p.add_argument("url",    nargs="?", help="Page URL or direct .m3u8 URL")
    p.add_argument("-o", "--output", default=".", help="Output directory")
    args = p.parse_args()

    tw = min(shutil.get_terminal_size().columns, 68)
    print()
    print(sep(tw))
    print(f"  {bold('🔍 M3U8 Stream Finder & Downloader')}")
    print(sep(tw))

    if not shutil.which("ffmpeg"):
        print(f"  {c('⚠  ffmpeg not found — download will fail', YE)}")
        print(f"  Get it from: https://ffmpeg.org/download.html")
        print()

    # ── URL input ──────────────────────────────────────────────────────────────
    url = args.url
    if not url:
        print()
        url = input(f"  {c('Page URL', CY)}: ").strip()
    if not url:
        print(f"  {c('No URL.', RE)}"); sys.exit(1)

    outdir = os.path.expanduser(args.output)
    os.makedirs(outdir, exist_ok=True)

    # ── Direct m3u8 ───────────────────────────────────────────────────────────
    if ".m3u8" in url.lower():
        streams  = [url]
        referer  = ""
        page_url = url
    else:
        # ── Scrape page ───────────────────────────────────────────────────────
        print()
        sys.stdout.write(f"  {c('⟳', CY)} Scraping page for stream links…")
        sys.stdout.flush()
        try:
            streams = scrape(url)
        except requests.exceptions.HTTPError as e:
            _clear()
            print(f"\n  {c(f'✗ HTTP {e.response.status_code}', RE)} — {url}")
            sys.exit(1)
        except Exception as e:
            _clear()
            print(f"\n  {c('✗', RE)} {e}")
            sys.exit(1)

        _clear()
        referer  = url
        page_url = url

        if not streams:
            print(f"\n  {c('✗ No .m3u8 streams found on this page.', RE)}")
            print(f"  {dim('The site may use encryption or JavaScript-only rendering.')}")
            sys.exit(1)

        print(f"  {c(f'✓ Found {len(streams)} stream(s)', GR)}")

    # ── Stream selection ───────────────────────────────────────────────────────
    video_url, audio_url = pick_streams(streams, referer)
    if not video_url:
        print(f"\n  {c('✗ No stream selected.', RE)}"); sys.exit(1)

    # ── Output filename ────────────────────────────────────────────────────────
    seg      = video_url.split("?")[0].rstrip("/").split("/")[-2]  # folder before file
    default  = safe_filename(seg) or "output"
    print()
    fname = input(f"  {c('Output filename', CY)} (no ext, default: {bold(default)}): ").strip()
    if not fname:
        fname = default
    output = os.path.join(outdir, fname + ".mp4")

    # ── Download ───────────────────────────────────────────────────────────────
    print()
    print(sep(tw))
    kind = "video + audio" if audio_url else "stream"
    print(f"  {c('Downloading', BL)} {kind}  →  {dim(output)}\n")

    try:
        ok = download_hls(video_url, audio_url, output, referer)
    except KeyboardInterrupt:
        _clear()
        print(f"\n  {c('↩ Cancelled.', YE)}")
        sys.exit(0)

    print()
    print(sep(tw))
    if ok:
        print(f"  {c('Saved:', D)} {output}")
    print(sep(tw))
    print()


if __name__ == "__main__":
    main()
