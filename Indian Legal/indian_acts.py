# mha_selenium.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests, time, os, json, hashlib

SEED = "https://judgments.ecourts.gov.in/pdfsearch/?p=pdf_search/home&text=tribunal&captcha=1eGRuh&search_opt=PHRASE&fcourt_type=2&escr_flag=&proximity=&sel_lang=&app_token=8102842c46eadb10d084a38e42c0bdf840e454471566c8612ff94a86adcd2c0f"
OUT_DIR = r"D:/Nova Legal/Indian Legal/raw"
META = r"D:/Nova Legal/Indian Legal/download_metadata.jsonl"
DELAY = 2.0
os.makedirs(OUT_DIR, exist_ok=True)

def make_driver():
    opts = Options()
    # headless=False so you can watch first; change to True later
    opts.headless = False
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def find_pdfs(html, base):
    soup = BeautifulSoup(html, "html.parser")
    pdfs = set()
    for a in soup.find_all("a", href=True):
        href = a['href']
        if ".pdf" in href.lower():
            pdfs.add(urljoin(base, href))
    for ifr in soup.find_all("iframe", src=True):
        src = ifr['src']
        if ".pdf" in src.lower():
            pdfs.add(urljoin(base, src))
    return list(pdfs)

def unique_path(url):
    name = os.path.basename(url.split("?")[0]) or hashlib.sha1(url.encode()).hexdigest()[:8]
    safe = "".join(c for c in name if c.isalnum() or c in " .-_()[]{}")
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    path = os.path.join(OUT_DIR, safe)
    if os.path.exists(path):
        path = path.replace(".pdf", "_" + hashlib.sha1(url.encode()).hexdigest()[:8] + ".pdf")
    return path

def download_with_cookies(url, driver):
    import requests
    s = requests.Session()
    for c in driver.get_cookies():
        s.cookies.set(c['name'], c['value'], domain=c.get('domain'), path=c.get('path'))
    headers = {"User-Agent": driver.execute_script("return navigator.userAgent;")}
    try:
        r = s.get(url, headers=headers, stream=True, timeout=60)
        r.raise_for_status()
        path = unique_path(url)
        with open(path, "wb") as fh:
            for chunk in r.iter_content(1024*64):
                if chunk:
                    fh.write(chunk)
        return path
    except Exception as e:
        print("download failed", e)
        return None

def main():
    d = make_driver()
    try:
        d.get(SEED)
        time.sleep(DELAY + 1.0)
        html = d.page_source
        pdfs = find_pdfs(html, SEED)
        print("Found", len(pdfs), "pdfs on seed page")
        # follow internal links to find PDFs as well
        if not pdfs:
            soup = BeautifulSoup(html, "html.parser")
            links = [urljoin(SEED, a['href']) for a in soup.find_all("a", href=True)]
            for link in links[:50]:
                d.get(link); time.sleep(1.5)
                html2 = d.page_source
                found = find_pdfs(html2, link)
                for f in found:
                    if f not in pdfs: pdfs.append(f)
        print("Total candidate PDFs:", len(pdfs))
        for p in pdfs:
            saved = download_with_cookies(p, d)
            if saved:
                with open(META, "a", encoding="utf8") as fh:
                    fh.write(json.dumps({"seed": SEED, "pdf_url": p, "saved_path": saved}) + "\n")
                print("Saved", saved)
                time.sleep(1.0)
    finally:
        d.quit()

if __name__ == "__main__":
    main()