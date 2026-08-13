# manual_page_downloader.py
# Interactive Playwright downloader: you manually browse in the opened Playwright browser;
# press Enter in the terminal to capture PDF links from the current page and download them.
# Requirements:
# pip install playwright requests beautifulsoup4 tqdm
# python -m playwright install

import os, time, json, hashlib
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from playwright.sync_api import sync_playwright

OUT_DIR = r"D:/Nova Legal/Indian Legal/raw"
META_FILE = r"D:/Nova Legal/Indian Legal/download_metadata.jsonl"
WAIT_AFTER_ACTION = 1.0
REQUEST_TIMEOUT = 120

os.makedirs(OUT_DIR, exist_ok=True)

def unique_path_from_url(url):
    parsed = urlparse(url)
    candidate = os.path.basename(parsed.path) or parsed.netloc
    safe = "".join(c for c in candidate if c.isalnum() or c in " .-_()[]{}")
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    outpath = os.path.join(OUT_DIR, safe[:200])
    if os.path.exists(outpath):
        outpath = outpath.replace(".pdf", "_" + hashlib.sha1(url.encode('utf8')).hexdigest()[:8] + ".pdf")
    return outpath

def download_with_cookies(url, cookies, user_agent):
    s = requests.Session()
    for c in cookies:
        s.cookies.set(c.get("name"), c.get("value"), domain=c.get("domain", ""), path=c.get("path","/"))
    headers = {"User-Agent": user_agent}
    with s.get(url, headers=headers, stream=True, timeout=REQUEST_TIMEOUT) as r:
        r.raise_for_status()
        outpath = unique_path_from_url(url)
        with open(outpath, "wb") as fh:
            for chunk in r.iter_content(1024*64):
                if chunk:
                    fh.write(chunk)
    return outpath

def scan_json_for_pdfs(obj, found):
    if isinstance(obj, str):
        if obj.lower().endswith(".pdf") and obj.startswith("http"):
            found.add(obj)
    elif isinstance(obj, dict):
        for v in obj.values(): scan_json_for_pdfs(v, found)
    elif isinstance(obj, list):
        for v in obj: scan_json_for_pdfs(v, found)

def find_pdf_links_in_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    pdfs = set()
    # anchor tags
    for a in soup.find_all("a", href=True):
        href = a['href']
        if ".pdf" in href.lower():
            pdfs.add(urljoin(base_url, href))
    # iframes
    for ifr in soup.find_all("iframe", src=True):
        src = ifr['src']
        if ".pdf" in src.lower():
            pdfs.add(urljoin(base_url, src))
    # embed and object (PDF viewers often use these)
    for emb in soup.find_all("embed", src=True):
        src = emb['src']
        if ".pdf" in src.lower():
            pdfs.add(urljoin(base_url, src))
    for obj in soup.find_all("object", data=True):
        data = obj['data']
        if ".pdf" in data.lower():
            pdfs.add(urljoin(base_url, data))
    return pdfs

def save_meta(seed, pdf_url, saved_path):
    rec = {"seed": seed, "pdf_url": pdf_url, "saved_path": saved_path, "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with open(META_FILE, "a", encoding="utf8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

def main():
    print("Starting interactive downloader. A Playwright browser window will open.")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # store PDF links found from JSON/network responses
        network_pdf_candidates = set()

        def on_response(response):
            try:
                # capture PDF responses by Content-Type, and also direct PDF URLs
                ct = (response.headers.get("content-type") or "").lower()
                if "application/pdf" in ct:
                    network_pdf_candidates.add(response.url)
                elif response.url.lower().endswith(".pdf"):
                    network_pdf_candidates.add(response.url)
                elif "application/json" in ct:
                    # also scan JSON for embedded pdf links
                    try:
                        body = response.json()
                        scan_json_for_pdfs(body, network_pdf_candidates)
                    except Exception:
                        try:
                            txt = response.text()
                            body = json.loads(txt)
                            scan_json_for_pdfs(body, network_pdf_candidates)
                        except Exception:
                            pass
            except Exception:
                pass

        page.on("response", on_response)

        # get user agent
        page.goto("about:blank")
        user_agent = page.evaluate("() => navigator.userAgent")

        print("Navigate manually in the opened browser to any page with PDFs (use the Playwright browser window).")
        print("When ready, switch back here and press Enter to download PDFs from the current page.")
        print("Type q and press Enter to quit.")

        while True:
            cmd = input("Press Enter to capture current page (or 'q' to quit): ").strip()
            if cmd.lower() == "q":
                break

            time.sleep(WAIT_AFTER_ACTION)

            # 1) If current page URL is a PDF, include it
            candidates = set()
            try:
                current_url = page.url
                if current_url and ".pdf" in current_url.lower():
                    candidates.add(current_url)
            except Exception:
                current_url = None

            # 2) HTML anchors/iframes/embed/object
            try:
                html = page.content()
                candidates.update(find_pdf_links_in_html(html, page.url))
            except Exception:
                pass

            # 3) network-captured candidates (from responses while you were browsing)
            candidates.update(network_pdf_candidates)

            if not candidates:
                print("No PDF links found on this page (HTML or recent network responses).")
                continue

            print(f"Found {len(candidates)} PDF link(s). Downloading...")

            cookies = context.cookies()
            for url in sorted(candidates):
                # Some captured URLs might be blob: or data: — skip those (we can't request them directly)
                if url.startswith("blob:") or url.startswith("data:"):
                    print("Skipping blob/data URL (open it in browser and Save As manually):", url)
                    continue
                try:
                    print("Downloading:", url)
                    saved = download_with_cookies(url, cookies, user_agent)
                    print("Saved:", saved)
                    save_meta(page.url or current_url or "manual", url, saved)
                    time.sleep(0.8)
                except Exception as e:
                    print("Failed to download", url, e)

            # Clear network-captured candidates so next capture only gets new responses
            network_pdf_candidates.clear()

        print("Quitting and closing browser.")
        browser.close()

if __name__ == "__main__":
    main()