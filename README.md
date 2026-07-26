# PDF Scraper

Scan a website for `.pdf` and `.zip` links, list what it finds, and download the ones you pick —
either straight from the command line with flags, or through an interactive terminal loop that
prompts you for each choice and opens a GUI dialog to pick the destination folder.

## Requirements

```
pip install requests beautifulsoup4
```

`tkinter` is required for the folder-picker (`--gui`, and the interactive loop). It ships with most
standard Python installs on Windows/macOS; on Linux you may need `sudo apt install python3-tk`
(or your distro's equivalent). If it's unavailable, the picker just falls back to typing a path.

## Usage

```
python pdf_scraper.py <url> [options]
python pdf_scraper.py                  # no url -> interactive loop
python pdf_scraper.py --loop           # force interactive loop even with a url
```

### Interactive loop mode

```
python pdf_scraper.py
```

Prompts you for a URL, opens a native folder-picker for the download destination, then asks for a
recursion depth, worker count, and request delay (press Enter on any of them to accept the
default). After downloading, it asks whether to scan another URL — say no (or leave it blank) to
quit.

### Basic scan and interactive download

```
python pdf_scraper.py https://example.com/papers
```

Lists every PDF/zip found, then prompts you to choose `all`, specific numbers (`1,3,5`), a range
(`1-10`), a mix of both (`1-3,7,9-10`), or `none`.

### Recursive crawl

```
python pdf_scraper.py https://example.com --recursive --depth 2
```

Follows same-domain page links up to `--depth` levels deep, collecting PDFs/zips along the way.
Each depth level is scanned in parallel — see `--workers`/`--delay` below.

### Faster / more polite crawling

```
python pdf_scraper.py <url> --recursive --depth 3 --workers 8 --delay 0.5
```

`--workers` controls how many pages within the same depth level are fetched concurrently
(default `1` = sequential). `--delay` adds a pause (in seconds) before each request, useful for
not hammering the target site when running with more workers.

### Choosing where downloads go

```
python pdf_scraper.py <url> --out ./my-downloads
```

```
python pdf_scraper.py <url> --gui
```

`--gui` opens a folder-picker dialog rooted at the folder the script lives in, so you can browse
the surrounding folder structure and pick exactly where downloads should land. If you cancel the
dialog, it falls back to `--out` (default `./pdf_downloads`).

### Non-interactive / scripted runs

```
python pdf_scraper.py <url> --yes                 # download everything, no prompt
python pdf_scraper.py <url> --select 1,3,5         # download specific items, no prompt
python pdf_scraper.py <url> --select 1-10          # download a range, no prompt
python pdf_scraper.py <url> --list-only            # just print what was found, download nothing
```

## CLI flags

| Flag | Description |
|---|---|
| `url` | Website URL to scan (optional — omit it, or pass `--loop`, to enter interactive mode) |
| `--recursive` | Follow same-domain links to discover more PDFs/zips |
| `--depth N` | Max recursion depth when `--recursive` is set (default `1`) |
| `--out PATH` | Download folder (default `./pdf_downloads`) |
| `--gui` | Open a folder-picker dialog (starting next to the script) to choose the download folder, instead of `--out` |
| `--loop` | Enter the interactive terminal loop (prompts for URL, folder, depth, workers, delay; repeats until you stop) |
| `--yes`, `-y` | Download all found files without prompting |
| `--select LIST` | Non-interactively select files: `all`, comma-separated numbers (`1,3,5`), a range (`1-10`), or a mix (`1-3,7,9-10`) |
| `--list-only` | Only list found files; skip downloading entirely |
| `--workers N` | Pages to scan in parallel per depth level (default `1` = sequential) |
| `--delay S` | Seconds to pause before each page request (default `0`) |

## Notes

- Both `.pdf` and `.zip` links are detected and downloadable; zip files are listed but never opened
  or crawled into — their contents aren't inspected.
- Only same-domain page links are followed during a recursive crawl.
- Each depth level of a recursive crawl is fetched concurrently (`--workers`), not one page at a
  time — more workers means faster crawls but heavier, less polite load on the target site; pair
  with `--delay` if that matters.
- Downloads are streamed to disk in chunks, so large files won't be loaded fully into memory.
- Failed downloads/requests are logged and skipped rather than stopping the whole run.
