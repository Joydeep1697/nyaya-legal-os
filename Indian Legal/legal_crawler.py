# legal_crawler.py
"""
legal_crawler.py

Crawl configured seed pages (IndiaCode, Supreme Court, High Courts...) and download discovered PDF files
to a local folder (Windows example target: D:/Nova Legal/Indian Legal/raw).

Usage:
  1) Create a venv and install dependencies:
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1   (PowerShell) or .\.venv\Scripts\activate.bat (cmd)
     pip install requests beautifulsoup4 tqdm

  2) Run:
     python "D:/Nova Legal/Indian Legal/legal_crawler.py"

Notes:
- This script checks robots.txt and sleeps between requests.
- Configure SEEDS below to add/remove sites.
- Adjust MAX_PAGES_PER_DOMAIN and CRAWL_DEPTH to control scope.
"""

import os
import time
import json
import logging
import hashlib
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import urllib.robotparser
from pathlib import Path
from tqdm import tqdm

# ------------------- CONFIG -------------------
OUT_ROOT = r"D:/Nova Legal/Indian Legal"            # top-level output directory
RAW_DIR = os.path.join(OUT_ROOT, "raw")            # where PDFs will be saved
META_FILE = os.path.join(OUT_ROOT, "download_metadata.jsonl")  # metadata log
LOG_FILE = os.path.join(OUT_ROOT, "crawler.log")

# Crawl politeness and limits
RATE_DELAY = 2.0               # seconds between requests to same host (politeness)
MAX_PAGES_PER_DOMAIN = 3     # limit pages crawled per domain (avoid huge crawls)
CRAWL_DEPTH = 0                # depth of crawl (0 = only seeds, 1 = follow links once, ...)
TIMEOUT = 30                   # requests timeout (s)

# Seeds - landing pages to start crawling. Add more official landing pages as needed.
SEEDS = [
    {"name": "IndiaCode", "url": "https://www.indiacode.nic.in/"},
    {"name": "SupremeCourt_Judgments", "url": "https://main.sci.gov.in/judgments"},
    {"name": "Delhi_High_Court", "url": "https://delhihighcourt.nic.in/"},
    {"name": "Bombay_High_Court", "url": "https://bombayhighcourt.nic.in/"},
    {"name": "Kerala_High_Court", "url": "https://highcourtofkerala.nic.in/"},
    # Add other High/District court roots here
]

USER_AGENT = "NovaLegalCrawler/1.0 (+your-email@example.com)"  # set your contact email
# ------------------------------------------------

# Setup directories & logging
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(OUT_ROOT, exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

# Helper: robots.txt check per domain
_robot_parsers = {}

def can_fetch_url(url):
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robot_parsers.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        robots_url = urljoin(base, "/robots.txt")
        try:
            rp.set_url(robots_url)
            rp.read()
        except Exception as e:
            logging.warning(f"Could not fetch robots.txt for {base}: {e}")
            rp = None
        _robot_parsers[base] = rp
    if rp:
        return rp.can_fetch(USER_AGENT, url)
    return True  # fallback allow

def safe_get(url):
    """GET with timeout and polite sleep; returns Response or None"""
    try:
        if not can_fetch_url(url):
            logging.info(f"Blocked by robots.txt: {url}")
            return None
        resp = session.get(url, timeout=TIMEOUT, stream=False)
        time.sleep(RATE_DELAY)
        if resp.status_code == 200:
            return resp
        else:
            logging.info(f"Non-200 {resp.status_code} for {url}")
            return None
    except Exception as e:
        logging.warning(f"Request failed {url}: {e}")
        return None

def normalize_url(base, link):
    return urljoin(base, link)

def is_pdf_link(href):
    if not href:
        return False
    href_l = href.lower()
    return ".pdf" in href_l

def sanitize_filename(name):
    safe = "".join(c for c in name if c.isalnum() or c in " .-_()[]{}").strip()
    return safe[:200] or "download"

def unique_filename_from_url(url, dest_dir):
    parsed = urlparse(url)
    candidate = os.path.basename(parsed.path) or parsed.netloc
    candidate = sanitize_filename(candidate)
    if not candidate.lower().endswith(".pdf"):
        candidate = candidate + ".pdf"
    path = os.path.join(dest_dir, candidate)
    if os.path.exists(path):
        h = hashlib.sha1(url.encode('utf8')).hexdigest()[:8]
        name, ext = os.path.splitext(candidate)
        path = os.path.join(dest_dir, f"{name}_{h}{ext}")
    return path

def download_file(url, out_dir):
    resp = safe_get(url)
    if not resp:
        return None
    cd = resp.headers.get("content-disposition")
    if cd and "filename=" in cd:
        fname = cd.split("filename=")[-1].strip().strip('"\'')
        fname = sanitize_filename(fname)
        if not fname.lower().endswith(".pdf"):
            fname += ".pdf"
        outpath = os.path.join(out_dir, fname)
    else:
        outpath = unique_filename_from_url(url, out_dir)

    try:
        with session.get(url, timeout=TIMEOUT, stream=True) as r:
            r.raise_for_status()
            with open(outpath, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024*64):
                    if chunk:
                        f.write(chunk)
        logging.info(f"Saved {url} -> {outpath}")
        return outpath
    except Exception as e:
        logging.warning(f"Failed download {url}: {e}")
        if os.path.exists(outpath):
            try:
                os.remove(outpath)
            except: pass
        return None

def extract_links_from_html(content, base_url):
    soup = BeautifulSoup(content, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        full = normalize_url(base_url, href)
        links.append(full)
    return links

def find_pdf_links_in_html(content, base_url):
    soup = BeautifulSoup(content, "html.parser")
    pdfs = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        if href and ".pdf" in href.lower():
            full = normalize_url(base_url, href)
            pdfs.add(full)
    for iframe in soup.find_all("iframe", src=True):
        src = iframe.get("src")
        if src and ".pdf" in src.lower():
            pdfs.add(normalize_url(base_url, src))
    return list(pdfs)

def same_domain(url, base_domain):
    return urlparse(url).netloc == urlparse(base_domain).netloc

def crawl_seed(seed_url, max_pages=MAX_PAGES_PER_DOMAIN, depth=CRAWL_DEPTH):
    host = urlparse(seed_url).netloc
    logging.info(f"Starting crawl for {seed_url} (domain={host})")
    visited = set()
    to_visit = [(seed_url, 0)]
    pages_crawled = 0
    discovered_pdfs = set()

    while to_visit:
        url, d = to_visit.pop(0)
        if url in visited:
            continue
        if pages_crawled >= max_pages:
            logging.info(f"Reached max pages {max_pages} for domain {host}")
            break
        if not same_domain(url, seed_url):
            continue
        visited.add(url)
        resp = safe_get(url)
        pages_crawled += 1
        if not resp:
            continue
        content_type = resp.headers.get("content-type", "").lower()
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            discovered_pdfs.add(url)
            continue
        text = resp.text
        pdfs = find_pdf_links_in_html(text, url)
        for p in pdfs:
            discovered_pdfs.add(p)
        if d < depth:
            links = extract_links_from_html(text, url)
            for l in links:
                if same_domain(l, seed_url) and l not in visited:
                    to_visit.append((l, d+1))
    logging.info(f"Finished crawl for {seed_url}. Pages crawled: {pages_crawled}, PDFs found: {len(discovered_pdfs)}")
    return list(discovered_pdfs)

def save_metadata_record(record):
    with open(META_FILE, "a", encoding="utf8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

def main():
    logging.info("=== Starting legal crawler ===")
    total_downloaded = 0
    for seed in SEEDS:
        name = seed.get("name")
        url = seed.get("url")
        if not url:
            continue
        pdf_links = crawl_seed(url)
        logging.info(f"Seed {name} found {len(pdf_links)} PDF links (first 5): {pdf_links[:5]}")
        for link in tqdm(pdf_links, desc=f"Downloading PDFs from {name}"):
            try:
                outpath = download_file(link, RAW_DIR)
                if not outpath:
                    continue
                record = {
                    "seed": name,
                    "source_url": link,
                    "saved_path": outpath,
                    "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }
                save_metadata_record(record)
                total_downloaded += 1
            except Exception as e:
                logging.warning(f"Error handling {link}: {e}")
    logging.info(f"Done. Total files downloaded: {total_downloaded}. Metadata saved to {META_FILE}")

if __name__ == "__main__":
    main()