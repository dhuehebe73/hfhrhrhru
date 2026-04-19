#!/usr/bin/env python3
"""
dl.py — Universal Media Downloader
Supports 1000+ sites via yt-dlp (YouTube, TikTok, Instagram, Twitter,
SoundCloud, Twitch, Reddit, Dailymotion, Vimeo, Facebook, and more)

Usage:
    python dl.py                  # interactive
    python dl.py <URL>            # direct
    python dl.py <URL> -a         # audio only
    python dl.py <URL> -v         # best video
    python dl.py <URL> -o ~/Downloads
"""

import sys, os, re, time, shutil, argparse
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    print("yt-dlp not installed. Run: pip install yt-dlp")
    sys.exit(1)

# ── ANSI ─────────────────────────────────────────────────────────────────────
R  = "\033[0m"
B  = "\033[1m"
D  = "\033[2m"
GR = "\033[92m"
CY = "\033[96m"
YE = "\033[93m"
RE = "\033[91m"
BL = "\033[94m"
MA = "\033[95m"

def c(text, color): return f"{color}{text}{R}"
def bold(t):        return f"{B}{t}{R}"
def dim(t):         return f"{D}{t}{R}"

# ── Formatting helpers ────────────────────────────────────────────────────────
def fmt_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

def fmt_speed(n: float) -> str:
    return fmt_bytes(n) + "/s"

def fmt_time(s) -> str:
    if s is None or s < 0: return "--:--"
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def bar(pct: float, width: int = 35) -> str:
    filled = int(width * pct / 100)
    return "█" * filled + "░" * (width - filled)

def sep(width: int = 60) -> str:
    return dim("─" * width)

# ── State for progress hook ───────────────────────────────────────────────────
_state = {
    "last_print": 0.0,
    "start": 0.0,
    "done": False,
    "postprocess": False,
}

def _hook(d: dict):
    status = d.get("status")

    if status == "downloading":
        now = time.time()
        if now - _state["last_print"] < 0.08:   # ~12 fps
            return
        _state["last_print"] = now

        total    = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        downloaded = d.get("downloaded_bytes", 0)
        speed    = d.get("speed") or 0
        eta      = d.get("eta")
        elapsed  = now - _state["start"]

        if total:
            pct      = min(downloaded / total * 100, 100)
            dl_s     = fmt_bytes(downloaded)
            tot_s    = fmt_bytes(total)
            spd_s    = c(fmt_speed(speed), MA) if speed else c("-- B/s", MA)
            eta_s    = c(fmt_time(eta), BL)
            ela_s    = c(fmt_time(elapsed), D)
            bar_s    = c(f"[{bar(pct)}]", CY)
            pct_s    = c(f"{pct:5.1f}%", GR)
            size_s   = f"{c(dl_s, YE)}/{c(tot_s, YE)}"

            line = (f"\r  {bar_s} {pct_s} │ {size_s} │ {spd_s} │ "
                    f"ETA {eta_s} │ {ela_s}  ")
        else:
            spd_s    = c(fmt_speed(speed), MA) if speed else c("-- B/s", MA)
            dl_s     = c(fmt_bytes(downloaded), YE)
            ela_s    = c(fmt_time(elapsed), D)
            line = f"\r  ⟳ {dl_s} downloaded │ {spd_s} │ {ela_s}    "

        sys.stdout.write(line)
        sys.stdout.flush()

    elif status == "finished":
        _clear()
        _state["done"] = True
        total = d.get("total_bytes", 0) or 0
        fname = os.path.basename(d.get("filename", ""))
        elapsed = time.time() - _state["start"]
        if total:
            print(f"  {c('✓', GR)} {bold(fname)} "
                  f"({c(fmt_bytes(total), YE)}) "
                  f"in {c(fmt_time(elapsed), BL)}")
        else:
            print(f"  {c('✓', GR)} {bold(fname)} downloaded in {c(fmt_time(elapsed), BL)}")

    elif status == "error":
        _clear()
        print(f"  {c('✗ Download error', RE)}")


def _postprocess_hook(d: dict):
    if d.get("status") == "started" and not _state.get("postprocess"):
        _state["postprocess"] = True
        pp = d.get("postprocessor", "")
        label = "Converting…" if "Audio" in pp or "FFmpeg" in pp else "Processing…"
        sys.stdout.write(f"\r  {c('⚙', YE)} {label}                            ")
        sys.stdout.flush()
    elif d.get("status") == "finished":
        _clear()


def _clear():
    sys.stdout.write("\r" + " " * 90 + "\r")
    sys.stdout.flush()


# ── Info fetching ─────────────────────────────────────────────────────────────
def fetch_info(url: str) -> dict | None:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "ignoreerrors": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def print_info(info: dict):
    title     = info.get("title", "Unknown")
    uploader  = info.get("uploader") or info.get("channel") or info.get("creator") or ""
    duration  = info.get("duration")
    extractor = info.get("extractor_key", "")
    is_playlist = info.get("_type") == "playlist"
    count     = len(info.get("entries", [])) if is_playlist else None

    dur_s = fmt_time(duration) if duration else ""

    print()
    if is_playlist:
        print(f"  {c('Playlist :', D)} {bold(title)} ({c(str(count), YE)} items)")
    else:
        print(f"  {c('Title    :', D)} {bold(title[:72])}")
    if uploader:
        print(f"  {c('Uploader :', D)} {uploader}")
    if dur_s:
        print(f"  {c('Duration :', D)} {dur_s}")
    if extractor:
        print(f"  {c('Source   :', D)} {extractor}")
    print()


# ── Format chooser ────────────────────────────────────────────────────────────
def best_video_formats(info: dict) -> list[dict]:
    """Return unique video formats sorted by quality."""
    fmts = info.get("formats") or []
    seen, out = set(), []
    # Prefer combined formats first
    for f in reversed(fmts):
        h   = f.get("height") or 0
        ext = f.get("ext", "")
        vc  = f.get("vcodec", "none")
        ac  = f.get("acodec", "none")
        if vc == "none" or h == 0:
            continue
        key = h
        if key not in seen:
            seen.add(key)
            out.append(f)
    out.sort(key=lambda f: f.get("height") or 0, reverse=True)
    return out[:12]


def show_video_menu(info: dict) -> str:
    """Show quality selector; return yt-dlp format string."""
    fmts = best_video_formats(info)
    has_ffmpeg = shutil.which("ffmpeg") is not None

    print(f"  {c('Available qualities:', D)}\n")
    for i, f in enumerate(fmts, 1):
        h     = f.get("height", "?")
        ext   = f.get("ext", "?")
        fps   = f.get("fps")
        vbr   = f.get("vbr") or f.get("tbr")
        sz    = f.get("filesize") or f.get("filesize_approx")
        fps_s = f" {int(fps)}fps" if fps else ""
        vbr_s = f" ~{int(vbr)}kbps" if vbr else ""
        sz_s  = f"  {c(fmt_bytes(sz), D)}" if sz else ""
        print(f"    {c(f'[{i}]', CY)} {c(f'{h}p', B)}{fps_s}{vbr_s}  {ext}{sz_s}")

    print(f"\n    {c('[0]', CY)} Best quality (auto-select)")
    print()

    while True:
        raw = input(f"  {c('→', GR)} Quality [0-{len(fmts)}]: ").strip()
        if raw == "0":
            if has_ffmpeg:
                return "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
            else:
                return "best[ext=mp4]/best"
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(fmts):
                fid = fmts[idx]["format_id"]
                # Merge with best audio if ffmpeg available
                if has_ffmpeg and fmts[idx].get("acodec") in ("none", None):
                    return f"{fid}+bestaudio/best"
                return fid
        except ValueError:
            pass
        print(f"  {c('Invalid.', RE)}")


# ── Download ──────────────────────────────────────────────────────────────────
def download(url: str, fmt: str, audio_only: bool, outdir: str, playlist: bool):
    has_ffmpeg = shutil.which("ffmpeg") is not None

    outtmpl = os.path.join(outdir, "%(title).80s.%(ext)s")
    if playlist:
        outtmpl = os.path.join(outdir, "%(playlist_index)02d. %(title).70s.%(ext)s")

    _state["start"]       = time.time()
    _state["done"]        = False
    _state["postprocess"] = False
    _state["last_print"]  = 0.0

    if audio_only:
        if has_ffmpeg:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                }],
                "progress_hooks":        [_hook],
                "postprocessor_hooks":   [_postprocess_hook],
                "quiet": True, "no_warnings": True,
                "ignoreerrors": playlist,
            }
        else:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": outtmpl,
                "progress_hooks":      [_hook],
                "postprocessor_hooks": [_postprocess_hook],
                "quiet": True, "no_warnings": True,
                "ignoreerrors": playlist,
            }
    else:
        if has_ffmpeg:
            merge_fmt = "mp4"
            post = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]
        else:
            merge_fmt = None
            post      = []
        ydl_opts = {
            "format": fmt,
            "outtmpl": outtmpl,
            "merge_output_format": merge_fmt,
            "postprocessors":      post,
            "progress_hooks":        [_hook],
            "postprocessor_hooks":   [_postprocess_hook],
            "quiet": True, "no_warnings": True,
            "ignoreerrors": playlist,
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="Universal media downloader powered by yt-dlp",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("url", nargs="?", help="Video/audio URL")
    p.add_argument("-a", "--audio",  action="store_true", help="Download audio only (MP3)")
    p.add_argument("-v", "--video",  action="store_true", help="Download best video")
    p.add_argument("-o", "--output", default=".", help="Output directory (default: current)")
    p.add_argument("--playlist",     action="store_true", help="Download entire playlist")
    args = p.parse_args()

    # ── Banner ────────────────────────────────────────────────────────────────
    tw = min(shutil.get_terminal_size().columns, 70)
    print()
    print(sep(tw))
    print(f"  {bold('📥 Universal Media Downloader')}  {dim('powered by yt-dlp')}")
    print(sep(tw))

    has_ffmpeg = shutil.which("ffmpeg") is not None
    if not has_ffmpeg:
        print(f"  {c('⚠', YE)}  ffmpeg not found — audio extraction & format merging disabled")

    # ── URL ───────────────────────────────────────────────────────────────────
    url = args.url
    if not url:
        print()
        url = input(f"  {c('URL', CY)}: ").strip()
        if not url:
            print(f"  {c('No URL provided.', RE)}"); sys.exit(1)

    outdir = os.path.expanduser(args.output)
    os.makedirs(outdir, exist_ok=True)

    # ── Fetch info ────────────────────────────────────────────────────────────
    print()
    sys.stdout.write(f"  {c('⟳', CY)} Fetching info…")
    sys.stdout.flush()
    try:
        info = fetch_info(url)
    except yt_dlp.utils.DownloadError as e:
        _clear()
        print(f"\n  {c('✗', RE)} {str(e)[:120]}")
        sys.exit(1)
    except Exception as e:
        _clear()
        print(f"\n  {c('✗', RE)} {e}")
        sys.exit(1)

    _clear()

    if not info:
        print(f"  {c('✗ Could not fetch info for this URL.', RE)}"); sys.exit(1)

    is_playlist = info.get("_type") == "playlist"
    print_info(info)

    # ── Playlist handling ─────────────────────────────────────────────────────
    dl_playlist = False
    if is_playlist and not args.playlist:
        count = len(info.get("entries") or [])
        ans   = input(f"  {c('Playlist detected', YE)} ({count} items). "
                      f"Download all? [y/N]: ").strip().lower()
        dl_playlist = ans in ("y", "yes")
        if not dl_playlist:
            # Just take first entry
            entries = info.get("entries") or []
            if entries:
                info = entries[0]
                url  = info.get("webpage_url") or url
                is_playlist = False
                print_info(info)

    # ── Mode selection ────────────────────────────────────────────────────────
    audio_only = args.audio
    fmt        = "best[ext=mp4]/best"
    skip_menu  = args.audio or args.video

    if not skip_menu:
        print(sep(tw))
        print(f"\n  {c('[1]', CY)} {bold('Video')}  — best quality")
        print(f"  {c('[2]', CY)} {bold('Audio')}  — MP3 320kbps" +
              ("" if has_ffmpeg else f"  {c('(ffmpeg needed for MP3)', D)}"))
        print(f"  {c('[3]', CY)} {bold('Choose quality')}")
        print()
        while True:
            ch = input(f"  {c('→', GR)} Select [1/2/3]: ").strip()
            if ch in ("1", "2", "3"): break
            print(f"  {c('Invalid.', RE)}")

        if ch == "2":
            audio_only = True
        elif ch == "3" and not is_playlist:
            print()
            fmt = show_video_menu(info)

    if args.video and not args.audio:
        if has_ffmpeg:
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
        else:
            fmt = "best[ext=mp4]/best"

    # ── Download ──────────────────────────────────────────────────────────────
    print()
    print(sep(tw))
    kind = "audio" if audio_only else "video"
    dest = os.path.abspath(outdir)
    print(f"  {c('Downloading', BL)} {kind}  →  {dim(dest)}\n")

    try:
        download(url, fmt, audio_only, outdir, dl_playlist or args.playlist)
    except KeyboardInterrupt:
        _clear()
        print(f"\n  {c('↩ Cancelled.', YE)}")
        sys.exit(0)
    except yt_dlp.utils.DownloadError as e:
        _clear()
        print(f"\n  {c('✗', RE)} {str(e)[:200]}")
        sys.exit(1)

    print()
    print(sep(tw))
    print(f"  {dim('Saved to:')} {outdir}")
    print(sep(tw))
    print()


if __name__ == "__main__":
    main()
