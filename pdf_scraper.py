#!/usr/bin/env python3
"""
PDF Scraper — scan a website for .pdf links, list them, download selected ones.

Usage:
    python pdf_scraper.py <url>
    python pdf_scraper.py <url> --recursive --depth 2
    python pdf_scraper.py <url> --out ./downloads
    python pdf_scraper.py <url> --gui
    python pdf_scraper.py <url> --yes --out ./downloads
    python pdf_scraper.py <url> --select 1,3,5
    python pdf_scraper.py --loop     # or just: python pdf_scraper.py
        interactive terminal loop — type a URL, pick the destination folder
        via a GUI dialog, download, then get asked whether to scan another URL
"""

import argparse
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (PDF-Scraper/1.0)"}
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def pick_folder_gui(initial_dir):
    """Open a native folder-picker rooted at the script's location so the
    user can browse the full folder tree and choose a download destination."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("[gui] tkinter is not available in this Python install; falling back to --out.")
        return None

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    chosen = filedialog.askdirectory(
        title="Choose download folder",
        initialdir=initial_dir,
        mustexist=False,
    )
    root.destroy()
    return chosen or None


def same_domain(base, link):
    return urlparse(base).netloc == urlparse(link).netloc


DOWNLOADABLE_EXTS = (".pdf", ".zip")


def get_links(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  [skip] {url} -> {e}")
        return [], []
    soup = BeautifulSoup(r.text, "html.parser")
    hrefs = [urljoin(url, a["href"]) for a in soup.find_all("a", href=True)]
    files = [h for h in hrefs if h.lower().split("?")[0].endswith(DOWNLOADABLE_EXTS)]
    pages = [
        h for h in hrefs
        if not h.lower().split("?")[0].endswith(DOWNLOADABLE_EXTS)
        and (h.lower().split("?")[0].endswith((".html", "/", "")) or "." not in h.split("/")[-1])
    ]
    return files, pages


def scan(start_url, recursive=False, max_depth=1, workers=1, delay=0.0):
    """Breadth-first crawl, fetching every page within a depth level in
    parallel (up to `workers` at once), pausing `delay` seconds before each
    request to stay polite to the target site."""
    visited_pages = set()
    found_files = {}  # url -> found on page
    current_level = [start_url]
    depth = 0

    def fetch(url):
        if delay:
            time.sleep(delay)
        print(f"Scanning: {url}")
        return url, get_links(url)

    while current_level:
        todo = [u for u in current_level if u not in visited_pages]
        visited_pages.update(todo)
        if not todo:
            break

        next_level = []
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for url, (files, pages) in pool.map(fetch, todo):
                for f in files:
                    found_files.setdefault(f, url)
                if recursive and depth < max_depth:
                    for p in pages:
                        if p not in visited_pages and same_domain(start_url, p):
                            next_level.append(p)

        current_level = next_level
        depth += 1

    return found_files


def download(file_url, out_dir):
    fname = os.path.basename(urlparse(file_url).path) or "file"
    fpath = os.path.join(out_dir, fname)
    try:
        r = requests.get(file_url, headers=HEADERS, timeout=30, stream=True)
        r.raise_for_status()
        with open(fpath, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        print(f"  ✓ saved: {fpath}")
    except requests.RequestException as e:
        print(f"  ✗ failed: {file_url} -> {e}")


def parse_index_selection(choice, count):
    """Parse '1,3,5' / '1-10' / '1-3,7,9-10' style selections into a sorted,
    de-duplicated list of 1-based indices, clamped to [1, count]."""
    idxs = set()
    for part in choice.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = (p.strip() for p in part.split("-", 1))
            start, end = int(start), int(end)
            if start > end:
                start, end = end, start
            idxs.update(range(start, end + 1))
        else:
            idxs.add(int(part))
    return sorted(i for i in idxs if 1 <= i <= count)


def handle_url(url, out_dir, recursive=False, depth=1, yes=False, select=None, list_only=False,
               workers=1, delay=0.0):
    """Scan one URL, list PDFs/zips found, and download whichever the user selects."""
    os.makedirs(out_dir, exist_ok=True)

    files = scan(url, recursive=recursive, max_depth=depth, workers=workers, delay=delay)

    if not files:
        print("No PDFs or zips found.")
        return

    file_list = list(files.keys())
    print(f"\nFound {len(file_list)} file(s):")
    current_source = None
    for i, f in enumerate(file_list, 1):
        source = files[f]
        if source != current_source:
            print(f"\nFrom: {source}")
            current_source = source
        ext = os.path.splitext(urlparse(f).path)[1].lstrip(".").upper() or "?"
        print(f"  [{i}] [{ext}] {f}")

    if list_only:
        return

    if yes:
        choice = "all"
    elif select is not None:
        choice = select.strip().lower()
    else:
        print("\nDownload options:")
        print("  all       -> download everything")
        print("  1,3,5     -> download by number (comma separated)")
        print("  1-10      -> download a range")
        print("  1-3,7,9-10 -> ranges and numbers can be mixed")
        print("  none      -> exit without downloading")
        choice = input("\nYour choice: ").strip().lower()

    if choice == "none" or choice == "":
        print("Done. Nothing downloaded.")
        return

    if choice == "all":
        selected = file_list
    else:
        try:
            idxs = parse_index_selection(choice, len(file_list))
            selected = [file_list[i - 1] for i in idxs]
        except ValueError:
            print("Invalid input. Aborting.")
            return

    print(f"\nDownloading {len(selected)} file(s) to {out_dir}/ ...")
    for file_url in selected:
        download(file_url, out_dir)

    print("\nDone.")


def interactive_loop(args):
    """Terminal REPL: type a URL, pick a destination folder via a GUI dialog,
    scan/download, then ask whether to do another URL."""
    print("=== PDF Scraper — interactive mode ===")
    print("(leave the URL blank at any time to quit)\n")

    while True:
        url = input("URL to scan: ").strip()
        if not url:
            print("Bye.")
            break

        out_dir = pick_folder_gui(SCRIPT_DIR)
        if not out_dir:
            out_dir = input(
                f"No folder chosen. Enter a destination folder [{args.out}]: "
            ).strip() or args.out

        depth_raw = input("Recursive depth [Enter for 0 / single page]: ").strip()
        try:
            depth = int(depth_raw) if depth_raw else 0
        except ValueError:
            print(f"Invalid depth '{depth_raw}', using 0.")
            depth = 0

        workers_raw = input(f"Parallel workers [Enter for {args.workers}]: ").strip()
        try:
            workers = int(workers_raw) if workers_raw else args.workers
        except ValueError:
            print(f"Invalid worker count '{workers_raw}', using {args.workers}.")
            workers = args.workers

        delay_raw = input(f"Delay between requests in seconds [Enter for {args.delay}]: ").strip()
        try:
            delay = float(delay_raw) if delay_raw else args.delay
        except ValueError:
            print(f"Invalid delay '{delay_raw}', using {args.delay}.")
            delay = args.delay

        handle_url(
            url,
            out_dir,
            recursive=depth > 0,
            depth=depth,
            yes=args.yes,
            select=args.select,
            list_only=args.list_only,
            workers=workers,
            delay=delay,
        )

        again = input("\nScan another URL? [y/N]: ").strip().lower()
        if again not in ("y", "yes"):
            print("Bye.")
            break


def main():
    ap = argparse.ArgumentParser(description="Scan a site for PDFs and download selected ones.")
    ap.add_argument("url", nargs="?", default=None,
                     help="Website URL to scan (omit, or pass --loop, to enter interactive mode)")
    ap.add_argument("--recursive", action="store_true", help="Follow same-domain links to find more PDFs")
    ap.add_argument("--depth", type=int, default=1, help="Max recursion depth (default 1)")
    ap.add_argument("--out", default="./pdf_downloads", help="Download folder (default ./pdf_downloads)")
    ap.add_argument("--gui", action="store_true",
                     help="Open a folder-picker (browsing the full folder tree, starting next to this script) "
                          "to choose the download destination instead of --out")
    ap.add_argument("--loop", action="store_true",
                     help="Interactive terminal loop: prompts for a URL, opens a folder-picker for the "
                          "destination, downloads, then asks whether to scan another URL")
    ap.add_argument("--yes", "-y", action="store_true", help="Download all found PDFs without prompting")
    ap.add_argument("--select", metavar="LIST", default=None,
                     help="Non-interactively pick which PDFs to download: 'all', comma-separated "
                          "numbers like '1,3,5', a range like '1-10', or a mix like '1-3,7,9-10' "
                          "(skips the interactive prompt)")
    ap.add_argument("--list-only", action="store_true", help="Only list found PDFs; don't download anything")
    ap.add_argument("--workers", type=int, default=1,
                     help="Number of pages to scan in parallel per depth level (default 1 = sequential)")
    ap.add_argument("--delay", type=float, default=0.0,
                     help="Seconds to wait before each page request, per worker (default 0)")
    args = ap.parse_args()

    if args.loop or not args.url:
        interactive_loop(args)
        return

    out_dir = args.out
    if args.gui:
        picked = pick_folder_gui(SCRIPT_DIR)
        if picked:
            out_dir = picked
        else:
            print(f"[gui] No folder chosen; using --out ({out_dir}).")

    handle_url(
        args.url,
        out_dir,
        recursive=args.recursive,
        depth=args.depth,
        yes=args.yes,
        select=args.select,
        list_only=args.list_only,
        workers=args.workers,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
