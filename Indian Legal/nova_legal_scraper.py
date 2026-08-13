"""
Nova Legal Automatic Web Scraper
================================

Features:
- Automatically crawls websites recursively.
- Handles JavaScript-rendered websites using Playwright.
- Finds PDFs from:
  - Anchor links
  - Buttons
  - Iframes
  - Embed tags
  - Object tags
  - Network responses
  - JSON/API responses
  - JavaScript source text
- Downloads PDF, DOC, DOCX, RTF and TXT files.
- Detects CAPTCHA and pauses for manual completion.
- Saves login/CAPTCHA session state.
- Resumes interrupted crawls using SQLite.
- Prevents duplicate documents using SHA-256 hashes.
- Records source page, document URL, filename and timestamp.
- Respects robots.txt by default.
- Limits crawl depth, pages and file size.
- Retries failed downloads.
- Uses conservative request delays.

This scraper does not bypass CAPTCHA, login restrictions,
access controls, rate limits or website protections.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import re
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import (
    parse_qsl,
    unquote,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Response,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)


# ============================================================
# CONFIGURATION
# ============================================================

# Add the websites that you are permitted to crawl.
SEED_URLS = ["https://www.indiacode.nic.in/"]

# Where downloaded legal documents will be saved.
OUTPUT_DIR = Path(r"D:\Nova Legal\Indian Legal\raw")

# SQLite database used for resumable crawling.
DATABASE_PATH = Path(
    r"D:\Nova Legal\Indian Legal\nova_legal_crawler.db"
)

# Human-readable document metadata.
METADATA_FILE = Path(
    r"D:\Nova Legal\Indian Legal\download_metadata.jsonl"
)

# Saved Playwright cookies and browser authentication state.
SESSION_STATE_FILE = Path(
    r"D:\Nova Legal\Indian Legal\browser_session.json"
)

# False means the browser window will be visible.
# Keep it False when websites use CAPTCHA.
HEADLESS = False

# Maximum number of links away from the starting page.
MAX_DEPTH = 5

# Maximum number of HTML pages processed in one run.
MAX_PAGES = 10_000

# Number of pages crawled simultaneously.
# Keep this low for court and government websites.
MAX_CONCURRENT_PAGES = 2

# Number of documents downloaded simultaneously.
MAX_CONCURRENT_DOWNLOADS = 3

# Delay between page requests.
REQUEST_DELAY_SECONDS = 1.5

# Delay between document downloads.
DOWNLOAD_DELAY_SECONDS = 1.0

# Browser navigation timeout.
PAGE_TIMEOUT_MS = 60_000

# Direct document download timeout.
DOWNLOAD_TIMEOUT_SECONDS = 180

# Maximum document size: 250 MB.
MAX_FILE_SIZE_BYTES = 250 * 1024 * 1024

# Retry count for failed pages and documents.
MAX_RETRIES = 3

# Restrict crawling to the websites in SEED_URLS.
FOLLOW_EXTERNAL_DOMAINS = False

# Check robots.txt before crawling a page.
RESPECT_ROBOTS_TXT = True

# Save browser cookies after CAPTCHA or login.
SAVE_SESSION_AFTER_EACH_PAGE = True

USER_AGENT = (
    "NovaLegalResearchBot/1.0 "
    "(Public legal-document indexing; "
    "contact: replace-with-your-email@example.com)"
)

TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "_ga",
    "_gl",
}

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".rtf",
    ".txt",
    ".odt",
}

DOWNLOADABLE_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/rtf",
    "application/octet-stream",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[title*='challenge']",
    ".g-recaptcha",
    ".h-captcha",
    "#captcha",
    "[id*='captcha']",
    "[class*='captcha']",
    "input[name*='captcha']",
    "input[id*='captcha']",
    "img[src*='captcha']",
]

CAPTCHA_TEXT_INDICATORS = [
    "verify you are human",
    "verify that you are human",
    "i am not a robot",
    "i'm not a robot",
    "enter captcha",
    "enter the captcha",
    "complete the captcha",
    "security verification",
    "human verification",
    "prove you are human",
    "checking your browser",
    "attention required",
    "cloudflare ray id",
]


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("nova-legal-scraper")


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class CrawlJob:
    url: str
    source_url: Optional[str]
    depth: int


@dataclass
class DownloadRecord:
    document_url: str
    source_page: str
    local_path: str
    filename: str
    sha256: str
    content_type: str
    file_size: int
    status_code: int
    downloaded_at: str
    title: Optional[str] = None


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonicalize_url(url: str) -> str:
    """Remove URL fragments and common tracking parameters."""

    try:
        parsed = urlparse(url)
    except Exception:
        return url

    if parsed.scheme not in {"http", "https"}:
        return url

    clean_query = [
        (key, value)
        for key, value in parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
        if key.lower() not in TRACKING_PARAMETERS
    ]

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()

    if not hostname:
        return url

    port = parsed.port

    if port and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    path = re.sub(r"/{2,}", "/", parsed.path or "/")

    return urlunparse(
        (
            scheme,
            netloc,
            path,
            "",
            urlencode(clean_query, doseq=True),
            "",
        )
    )


def is_http_url(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def is_ignored_url(url: str) -> bool:
    lowered = url.lower().strip()

    return lowered.startswith(
        (
            "javascript:",
            "mailto:",
            "tel:",
            "data:",
            "blob:",
            "#",
        )
    )


def is_probable_document_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    query = parsed.query.lower()

    if any(path.endswith(extension) for extension in DOCUMENT_EXTENSIONS):
        return True

    document_query_indicators = [
        "file=",
        "pdf=",
        "download=",
        "attachment=",
        "document=",
        "filename=",
        "doc=",
    ]

    return any(
        indicator in query
        for indicator in document_query_indicators
    )


def is_html_content_type(content_type: str) -> bool:
    lowered = content_type.lower()

    return (
        "text/html" in lowered
        or "application/xhtml+xml" in lowered
    )


def is_downloadable_content_type(content_type: str) -> bool:
    clean_type = content_type.split(";")[0].strip().lower()
    return clean_type in DOWNLOADABLE_CONTENT_TYPES


def sanitize_filename(filename: str) -> str:
    filename = unquote(filename)
    filename = re.sub(
        r'[<>:"/\\|?*\x00-\x1f]',
        "_",
        filename,
    )
    filename = re.sub(r"\s+", " ", filename)
    filename = filename.strip(" .")

    return filename[:180] or "document"


def extension_from_content_type(content_type: str) -> str:
    clean_type = content_type.split(";")[0].strip().lower()

    mapping = {
        "application/pdf": ".pdf",
        "application/msword": ".doc",
        "application/rtf": ".rtf",
        "text/plain": ".txt",
        "application/vnd.oasis.opendocument.text": ".odt",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    }

    if clean_type in mapping:
        return mapping[clean_type]

    guessed = mimetypes.guess_extension(clean_type)
    return guessed or ".bin"


def filename_from_response(
    url: str,
    content_disposition: str,
    content_type: str,
) -> str:
    filename = ""

    utf8_match = re.search(
        r"filename\*=UTF-8''([^;]+)",
        content_disposition,
        flags=re.IGNORECASE,
    )

    normal_match = re.search(
        r'filename=["\']?([^;"\']+)',
        content_disposition,
        flags=re.IGNORECASE,
    )

    if utf8_match:
        filename = utf8_match.group(1)
    elif normal_match:
        filename = normal_match.group(1)
    else:
        filename = Path(urlparse(url).path).name

    filename = sanitize_filename(filename)

    if not Path(filename).suffix:
        filename += extension_from_content_type(content_type)

    return filename


def calculate_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file_handle:
        while True:
            chunk = file_handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def create_output_path(
    filename: str,
    sha256: str,
) -> Path:
    safe_filename = sanitize_filename(filename)

    stem = Path(safe_filename).stem
    extension = Path(safe_filename).suffix

    if not extension:
        extension = ".bin"

    final_filename = (
        f"{stem}_{sha256[:12]}{extension}"
    )

    return OUTPUT_DIR / final_filename


def append_metadata(record: DownloadRecord) -> None:
    with METADATA_FILE.open(
        "a",
        encoding="utf-8",
    ) as file_handle:
        file_handle.write(
            json.dumps(
                asdict(record),
                ensure_ascii=False,
            )
            + "\n"
        )


# ============================================================
# SQLITE CRAWL DATABASE
# ============================================================

class CrawlDatabase:
    def __init__(self, database_path: Path) -> None:
        self.connection = sqlite3.connect(
            database_path,
            check_same_thread=False,
        )

        self.connection.row_factory = sqlite3.Row
        self.create_tables()

    def create_tables(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS crawl_queue (
                url TEXT PRIMARY KEY,
                source_url TEXT,
                depth INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pages (
                url TEXT PRIMARY KEY,
                final_url TEXT,
                title TEXT,
                status_code INTEGER,
                content_type TEXT,
                depth INTEGER,
                crawled_at TEXT,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS documents (
                sha256 TEXT PRIMARY KEY,
                document_url TEXT,
                source_page TEXT,
                local_path TEXT,
                filename TEXT,
                content_type TEXT,
                file_size INTEGER,
                status_code INTEGER,
                downloaded_at TEXT,
                title TEXT
            );

            CREATE TABLE IF NOT EXISTS document_urls (
                document_url TEXT PRIMARY KEY,
                sha256 TEXT,
                source_page TEXT,
                discovered_at TEXT
            );

            CREATE TABLE IF NOT EXISTS captcha_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                detected_at TEXT,
                resolved INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_queue_status
            ON crawl_queue(status);

            CREATE INDEX IF NOT EXISTS idx_document_urls_sha
            ON document_urls(sha256);
            """
        )

        self.connection.commit()

    def get_job_status(self, url: str) -> Optional[str]:
        row = self.connection.execute(
            """
            SELECT status
            FROM crawl_queue
            WHERE url = ?
            """,
            (url,),
        ).fetchone()

        return row["status"] if row else None

    def add_job(self, job: CrawlJob) -> bool:
        now = utc_now()

        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO crawl_queue
            (
                url,
                source_url,
                depth,
                status,
                attempts,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'pending', 0, ?, ?)
            """,
            (
                job.url,
                job.source_url,
                job.depth,
                now,
                now,
            ),
        )

        self.connection.commit()
        return cursor.rowcount > 0

    def reset_interrupted_jobs(self) -> None:
        self.connection.execute(
            """
            UPDATE crawl_queue
            SET status = 'pending',
                updated_at = ?
            WHERE status = 'processing'
            """,
            (utc_now(),),
        )

        self.connection.commit()

    def get_pending_jobs(self) -> list[CrawlJob]:
        rows = self.connection.execute(
            """
            SELECT url, source_url, depth
            FROM crawl_queue
            WHERE status IN ('pending', 'retry')
            ORDER BY depth ASC, created_at ASC
            """
        ).fetchall()

        return [
            CrawlJob(
                url=row["url"],
                source_url=row["source_url"],
                depth=row["depth"],
            )
            for row in rows
        ]

    def mark_processing(self, url: str) -> None:
        self.connection.execute(
            """
            UPDATE crawl_queue
            SET status = 'processing',
                attempts = attempts + 1,
                updated_at = ?
            WHERE url = ?
            """,
            (utc_now(), url),
        )

        self.connection.commit()

    def mark_completed(self, url: str) -> None:
        self.connection.execute(
            """
            UPDATE crawl_queue
            SET status = 'completed',
                last_error = NULL,
                updated_at = ?
            WHERE url = ?
            """,
            (utc_now(), url),
        )

        self.connection.commit()

    def mark_failed(self, url: str, error: str) -> None:
        row = self.connection.execute(
            """
            SELECT attempts
            FROM crawl_queue
            WHERE url = ?
            """,
            (url,),
        ).fetchone()

        attempts = row["attempts"] if row else MAX_RETRIES

        new_status = (
            "retry"
            if attempts < MAX_RETRIES
            else "failed"
        )

        self.connection.execute(
            """
            UPDATE crawl_queue
            SET status = ?,
                last_error = ?,
                updated_at = ?
            WHERE url = ?
            """,
            (
                new_status,
                error[:2000],
                utc_now(),
                url,
            ),
        )

        self.connection.commit()

    def save_page(
        self,
        *,
        url: str,
        final_url: str,
        title: Optional[str],
        status_code: Optional[int],
        content_type: Optional[str],
        depth: int,
        error: Optional[str] = None,
    ) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO pages
            (
                url,
                final_url,
                title,
                status_code,
                content_type,
                depth,
                crawled_at,
                error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                url,
                final_url,
                title,
                status_code,
                content_type,
                depth,
                utc_now(),
                error,
            ),
        )

        self.connection.commit()

    def document_url_exists(self, url: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1
            FROM document_urls
            WHERE document_url = ?
            LIMIT 1
            """,
            (url,),
        ).fetchone()

        return row is not None

    def find_document_by_hash(
        self,
        sha256: str,
    ) -> Optional[str]:
        row = self.connection.execute(
            """
            SELECT local_path
            FROM documents
            WHERE sha256 = ?
            LIMIT 1
            """,
            (sha256,),
        ).fetchone()

        return row["local_path"] if row else None

    def save_document(
        self,
        record: DownloadRecord,
    ) -> None:
        self.connection.execute(
            """
            INSERT OR IGNORE INTO documents
            (
                sha256,
                document_url,
                source_page,
                local_path,
                filename,
                content_type,
                file_size,
                status_code,
                downloaded_at,
                title
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.sha256,
                record.document_url,
                record.source_page,
                record.local_path,
                record.filename,
                record.content_type,
                record.file_size,
                record.status_code,
                record.downloaded_at,
                record.title,
            ),
        )

        self.save_document_url(
            document_url=record.document_url,
            sha256=record.sha256,
            source_page=record.source_page,
            commit=False,
        )

        self.connection.commit()

    def save_document_url(
        self,
        *,
        document_url: str,
        sha256: str,
        source_page: str,
        commit: bool = True,
    ) -> None:
        self.connection.execute(
            """
            INSERT OR REPLACE INTO document_urls
            (
                document_url,
                sha256,
                source_page,
                discovered_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                document_url,
                sha256,
                source_page,
                utc_now(),
            ),
        )

        if commit:
            self.connection.commit()

    def record_captcha(
        self,
        url: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO captcha_events
            (
                url,
                detected_at,
                resolved
            )
            VALUES (?, ?, 0)
            """,
            (url, utc_now()),
        )

        self.connection.commit()
        return int(cursor.lastrowid)

    def resolve_captcha(
        self,
        captcha_event_id: int,
    ) -> None:
        self.connection.execute(
            """
            UPDATE captcha_events
            SET resolved = 1
            WHERE id = ?
            """,
            (captcha_event_id,),
        )

        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


# ============================================================
# ROBOTS.TXT
# ============================================================

class RobotsCache:
    def __init__(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        self.client = client
        self.cache: dict[str, RobotFileParser] = {}

    async def is_allowed(self, url: str) -> bool:
        if not RESPECT_ROBOTS_TXT:
            return True

        parsed = urlparse(url)
        root_url = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = urljoin(root_url, "/robots.txt")

        if root_url not in self.cache:
            parser = RobotFileParser()
            parser.set_url(robots_url)

            try:
                response = await self.client.get(
                    robots_url,
                    timeout=30,
                )

                if response.status_code < 400:
                    parser.parse(
                        response.text.splitlines()
                    )
                else:
                    parser.parse([])

            except httpx.HTTPError:
                parser.parse([])

            self.cache[root_url] = parser

        return self.cache[root_url].can_fetch(
            USER_AGENT,
            url,
        )


# ============================================================
# CAPTCHA HANDLING
# ============================================================

async def detect_captcha(page: Page) -> bool:
    """Detect common CAPTCHA pages without solving them."""

    for selector in CAPTCHA_SELECTORS:
        try:
            locator = page.locator(selector)

            if await locator.count() > 0:
                if await locator.first.is_visible():
                    return True

        except Exception:
            continue

    try:
        body_text = await page.locator("body").inner_text(
            timeout=5_000
        )

        body_text = body_text.lower()

        if any(
            indicator in body_text
            for indicator in CAPTCHA_TEXT_INDICATORS
        ):
            return True

    except Exception:
        pass

    return False


async def wait_for_manual_captcha(
    *,
    page: Page,
    context: BrowserContext,
    database: CrawlDatabase,
) -> None:
    """
    Pause the crawler so the user can manually complete CAPTCHA.

    This function does not automate or bypass CAPTCHA.
    """

    if not await detect_captcha(page):
        return

    captcha_event_id = database.record_captcha(page.url)

    print("\n" + "=" * 65)
    print("CAPTCHA OR HUMAN VERIFICATION DETECTED")
    print("=" * 65)
    print("Page:", page.url)
    print()
    print("Complete the CAPTCHA manually in the browser window.")
    print("Do not close the Playwright browser.")
    print()
    print(
        "After the protected page opens successfully, "
        "return to this terminal."
    )
    print("=" * 65)

    await asyncio.to_thread(
        input,
        "Press Enter after completing the CAPTCHA: ",
    )

    await page.wait_for_timeout(2_000)

    if SESSION_STATE_FILE.parent.exists():
        await context.storage_state(
            path=str(SESSION_STATE_FILE)
        )

    if await detect_captcha(page):
        print(
            "\nThe CAPTCHA still appears to be present."
        )

        answer = await asyncio.to_thread(
            input,
            "Press Enter to check again, or type 'skip': ",
        )

        if answer.strip().lower() == "skip":
            raise RuntimeError(
                "CAPTCHA was not completed."
            )

        await page.wait_for_timeout(2_000)

        if await detect_captcha(page):
            raise RuntimeError(
                "CAPTCHA is still active."
            )

    database.resolve_captcha(captcha_event_id)

    await context.storage_state(
        path=str(SESSION_STATE_FILE)
    )

    logger.info(
        "CAPTCHA completed manually. Session saved."
    )


# ============================================================
# LINK AND JSON EXTRACTION
# ============================================================

def scan_json_for_documents(
    value: object,
    base_url: str,
    found: set[str],
) -> None:
    if isinstance(value, str):
        possible_url = canonicalize_url(
            urljoin(base_url, value)
        )

        if (
            is_http_url(possible_url)
            and is_probable_document_url(possible_url)
        ):
            found.add(possible_url)

    elif isinstance(value, dict):
        for nested_value in value.values():
            scan_json_for_documents(
                nested_value,
                base_url,
                found,
            )

    elif isinstance(value, list):
        for nested_value in value:
            scan_json_for_documents(
                nested_value,
                base_url,
                found,
            )


def extract_links_from_html(
    html: str,
    base_url: str,
) -> tuple[set[str], set[str]]:
    soup = BeautifulSoup(html, "html.parser")

    page_links: set[str] = set()
    document_links: set[str] = set()

    attributes = [
        ("a", "href"),
        ("iframe", "src"),
        ("embed", "src"),
        ("object", "data"),
        ("source", "src"),
    ]

    for tag_name, attribute_name in attributes:
        elements = soup.find_all(
            tag_name,
            attrs={attribute_name: True},
        )

        for element in elements:
            raw_url = str(
                element.get(attribute_name, "")
            ).strip()

            if not raw_url or is_ignored_url(raw_url):
                continue

            absolute_url = canonicalize_url(
                urljoin(base_url, raw_url)
            )

            if not is_http_url(absolute_url):
                continue

            if is_probable_document_url(absolute_url):
                document_links.add(absolute_url)
            else:
                page_links.add(absolute_url)

    # Search JavaScript and inline JSON for absolute URLs.
    absolute_url_pattern = re.compile(
        r"""https?://[^\s"'<>\\]+""",
        flags=re.IGNORECASE,
    )

    for match in absolute_url_pattern.findall(html):
        cleaned_url = match.rstrip(
            ".,;:)]}'\""
        )

        cleaned_url = canonicalize_url(cleaned_url)

        if is_probable_document_url(cleaned_url):
            document_links.add(cleaned_url)

    # Search for relative PDF/document paths in scripts.
    relative_document_pattern = re.compile(
        r"""["']([^"']+\.(?:pdf|docx?|rtf|txt|odt)(?:\?[^"']*)?)["']""",
        flags=re.IGNORECASE,
    )

    for match in relative_document_pattern.findall(html):
        absolute_url = canonicalize_url(
            urljoin(base_url, match)
        )

        if is_http_url(absolute_url):
            document_links.add(absolute_url)

    return page_links, document_links


# ============================================================
# DOCUMENT DOWNLOADER
# ============================================================

class DocumentDownloader:
    def __init__(
        self,
        *,
        database: CrawlDatabase,
        client: httpx.AsyncClient,
        context: BrowserContext,
        semaphore: asyncio.Semaphore,
    ) -> None:
        self.database = database
        self.client = client
        self.context = context
        self.semaphore = semaphore

    async def get_authenticated_cookies(
        self,
        url: str,
    ) -> dict[str, str]:
        browser_cookies = await self.context.cookies([url])

        return {
            cookie["name"]: cookie["value"]
            for cookie in browser_cookies
        }

    async def download(
        self,
        *,
        url: str,
        source_page: str,
        title: Optional[str] = None,
    ) -> Optional[DownloadRecord]:
        url = canonicalize_url(url)

        if not is_http_url(url):
            return None

        if self.database.document_url_exists(url):
            logger.debug(
                "Already processed document URL: %s",
                url,
            )
            return None

        async with self.semaphore:
            for attempt in range(1, MAX_RETRIES + 1):
                temporary_path: Optional[Path] = None

                try:
                    cookies = (
                        await self.get_authenticated_cookies(url)
                    )

                    headers = {
                        "User-Agent": USER_AGENT,
                        "Referer": source_page,
                        "Accept": (
                            "application/pdf,"
                            "application/msword,"
                            "application/vnd.openxmlformats-"
                            "officedocument.wordprocessingml.document,"
                            "application/octet-stream,*/*"
                        ),
                    }

                    logger.info(
                        "Downloading: %s",
                        url,
                    )

                    async with self.client.stream(
                        "GET",
                        url,
                        headers=headers,
                        cookies=cookies,
                        follow_redirects=True,
                    ) as response:
                        response.raise_for_status()

                        content_type = (
                            response.headers.get(
                                "content-type",
                                "",
                            )
                            .split(";")[0]
                            .strip()
                            .lower()
                        )

                        content_disposition = (
                            response.headers.get(
                                "content-disposition",
                                "",
                            )
                        )

                        filename = filename_from_response(
                            str(response.url),
                            content_disposition,
                            content_type,
                        )

                        temporary_path = (
                            OUTPUT_DIR
                            / f".download_{time.time_ns()}.part"
                        )

                        file_size = 0
                        first_bytes = b""

                        with temporary_path.open("wb") as file_handle:
                            async for chunk in response.aiter_bytes(
                                chunk_size=128 * 1024
                            ):
                                if not chunk:
                                    continue

                                if not first_bytes:
                                    first_bytes = chunk[:20]

                                file_size += len(chunk)

                                if file_size > MAX_FILE_SIZE_BYTES:
                                    raise ValueError(
                                        "Document exceeded the "
                                        "maximum allowed size."
                                    )

                                file_handle.write(chunk)

                    if file_size == 0:
                        raise ValueError(
                            "Downloaded document was empty."
                        )

                    # Prevent HTML error pages being saved as PDFs.
                    beginning = first_bytes.lstrip().lower()

                    if (
                        beginning.startswith(b"<!doctype html")
                        or beginning.startswith(b"<html")
                    ):
                        temporary_path.unlink(missing_ok=True)

                        raise ValueError(
                            "Server returned an HTML page instead "
                            "of a document. Login or CAPTCHA may "
                            "be required."
                        )

                    # Correct content type using PDF signature.
                    if first_bytes.startswith(b"%PDF-"):
                        content_type = "application/pdf"

                        if Path(filename).suffix.lower() != ".pdf":
                            filename = (
                                Path(filename).stem + ".pdf"
                            )

                    sha256 = calculate_sha256(
                        temporary_path
                    )

                    existing_path = (
                        self.database.find_document_by_hash(
                            sha256
                        )
                    )

                    if existing_path:
                        temporary_path.unlink(missing_ok=True)

                        self.database.save_document_url(
                            document_url=url,
                            sha256=sha256,
                            source_page=source_page,
                        )

                        logger.info(
                            "Duplicate document skipped: %s",
                            url,
                        )

                        return None

                    final_path = create_output_path(
                        filename,
                        sha256,
                    )

                    temporary_path.replace(final_path)

                    record = DownloadRecord(
                        document_url=url,
                        source_page=source_page,
                        local_path=str(final_path),
                        filename=final_path.name,
                        sha256=sha256,
                        content_type=content_type,
                        file_size=file_size,
                        status_code=response.status_code,
                        downloaded_at=utc_now(),
                        title=title,
                    )

                    self.database.save_document(record)
                    append_metadata(record)

                    logger.info(
                        "Saved: %s",
                        final_path,
                    )

                    await asyncio.sleep(
                        DOWNLOAD_DELAY_SECONDS
                    )

                    return record

                except Exception as error:
                    if temporary_path:
                        temporary_path.unlink(
                            missing_ok=True
                        )

                    logger.warning(
                        "Download attempt %s/%s failed for %s: %s",
                        attempt,
                        MAX_RETRIES,
                        url,
                        error,
                    )

                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(2 ** attempt)

            logger.error(
                "Document download permanently failed: %s",
                url,
            )

            return None


# ============================================================
# MAIN AUTOMATIC CRAWLER
# ============================================================

class NovaLegalCrawler:
    def __init__(self) -> None:
        self.database = CrawlDatabase(DATABASE_PATH)

        self.queue: asyncio.Queue[CrawlJob] = (
            asyncio.Queue()
        )

        self.queued_urls: set[str] = set()
        self.network_documents: dict[int, set[str]] = {}

        self.processed_pages = 0
        self.stop_requested = False

        self.seed_hosts = {
            (urlparse(url).hostname or "").lower()
            for url in SEED_URLS
        }

    def is_allowed_domain(self, url: str) -> bool:
        if FOLLOW_EXTERNAL_DOMAINS:
            return True

        hostname = (
            urlparse(url).hostname or ""
        ).lower()

        for seed_host in self.seed_hosts:
            if (
                hostname == seed_host
                or hostname.endswith("." + seed_host)
            ):
                return True

        return False

    async def enqueue(
        self,
        job: CrawlJob,
    ) -> None:
        normalized_url = canonicalize_url(job.url)

        if not is_http_url(normalized_url):
            return

        if job.depth > MAX_DEPTH:
            return

        if not self.is_allowed_domain(normalized_url):
            return

        if normalized_url in self.queued_urls:
            return

        existing_status = self.database.get_job_status(
            normalized_url
        )

        if existing_status in {
            "completed",
            "processing",
            "failed",
        }:
            return

        normalized_job = CrawlJob(
            url=normalized_url,
            source_url=job.source_url,
            depth=job.depth,
        )

        self.queued_urls.add(normalized_url)
        self.database.add_job(normalized_job)

        await self.queue.put(normalized_job)

    async def inspect_network_response(
        self,
        response: Response,
        page: Page,
    ) -> None:
        try:
            response_url = canonicalize_url(
                response.url
            )

            content_type = (
                response.headers.get(
                    "content-type",
                    "",
                )
                .split(";")[0]
                .strip()
                .lower()
            )

            page_id = id(page)

            candidates = self.network_documents.setdefault(
                page_id,
                set(),
            )

            if (
                is_downloadable_content_type(content_type)
                or is_probable_document_url(response_url)
            ):
                if is_http_url(response_url):
                    candidates.add(response_url)

                return

            if content_type == "application/json":
                try:
                    json_data = await response.json()

                    scan_json_for_documents(
                        json_data,
                        response.url,
                        candidates,
                    )

                except Exception:
                    pass

        except Exception:
            logger.debug(
                "Unable to inspect browser response.",
                exc_info=True,
            )

    async def crawl_page(
        self,
        *,
        job: CrawlJob,
        context: BrowserContext,
        downloader: DocumentDownloader,
        robots: RobotsCache,
    ) -> None:
        if self.processed_pages >= MAX_PAGES:
            self.stop_requested = True
            return

        if not await robots.is_allowed(job.url):
            logger.warning(
                "Blocked by robots.txt: %s",
                job.url,
            )

            self.database.mark_completed(job.url)
            return

        self.database.mark_processing(job.url)

        page = await context.new_page()
        page_id = id(page)

        self.network_documents[page_id] = set()

        response_status: Optional[int] = None
        content_type = ""
        title: Optional[str] = None
        final_url = job.url

        try:
            page.on(
                "response",
                lambda response: asyncio.create_task(
                    self.inspect_network_response(
                        response,
                        page,
                    )
                ),
            )

            response = None

            for attempt in range(
                1,
                MAX_RETRIES + 1,
            ):
                try:
                    response = await page.goto(
                        job.url,
                        wait_until="domcontentloaded",
                        timeout=PAGE_TIMEOUT_MS,
                    )

                    break

                except PlaywrightTimeoutError:
                    if attempt == MAX_RETRIES:
                        raise

                    logger.warning(
                        "Navigation timeout %s/%s: %s",
                        attempt,
                        MAX_RETRIES,
                        job.url,
                    )

                    await asyncio.sleep(2 ** attempt)

            await page.wait_for_timeout(1_500)

            final_url = canonicalize_url(page.url)

            await wait_for_manual_captcha(
                page=page,
                context=context,
                database=self.database,
            )

            if response:
                response_status = response.status

                content_type = (
                    response.headers.get(
                        "content-type",
                        "",
                    )
                    .split(";")[0]
                    .strip()
                    .lower()
                )

            # Current page itself is a document.
            if (
                is_downloadable_content_type(content_type)
                or is_probable_document_url(final_url)
            ):
                await downloader.download(
                    url=final_url,
                    source_page=job.source_url or job.url,
                )

                self.database.save_page(
                    url=job.url,
                    final_url=final_url,
                    title=None,
                    status_code=response_status,
                    content_type=content_type,
                    depth=job.depth,
                )

                self.database.mark_completed(job.url)
                self.processed_pages += 1
                return

            title = await page.title()
            html = await page.content()

            page_links, document_links = (
                extract_links_from_html(
                    html,
                    final_url,
                )
            )

            document_links.update(
                self.network_documents.get(
                    page_id,
                    set(),
                )
            )

            if document_links:
                logger.info(
                    "Found %s document link(s) on %s",
                    len(document_links),
                    final_url,
                )

            download_tasks = [
                downloader.download(
                    url=document_url,
                    source_page=final_url,
                    title=title,
                )
                for document_url in sorted(
                    document_links
                )
                if is_http_url(document_url)
            ]

            if download_tasks:
                await asyncio.gather(
                    *download_tasks,
                    return_exceptions=True,
                )

            for discovered_url in sorted(page_links):
                await self.enqueue(
                    CrawlJob(
                        url=discovered_url,
                        source_url=final_url,
                        depth=job.depth + 1,
                    )
                )

            self.database.save_page(
                url=job.url,
                final_url=final_url,
                title=title,
                status_code=response_status,
                content_type=content_type,
                depth=job.depth,
            )

            self.database.mark_completed(job.url)
            self.processed_pages += 1

            logger.info(
                "Crawled page %s/%s | Depth %s | "
                "Documents %s | Page links %s | %s",
                self.processed_pages,
                MAX_PAGES,
                job.depth,
                len(document_links),
                len(page_links),
                final_url,
            )

            if SAVE_SESSION_AFTER_EACH_PAGE:
                await context.storage_state(
                    path=str(SESSION_STATE_FILE)
                )

            await asyncio.sleep(
                REQUEST_DELAY_SECONDS
            )

        except Exception as error:
            logger.exception(
                "Failed to crawl page: %s",
                job.url,
            )

            self.database.save_page(
                url=job.url,
                final_url=final_url,
                title=title,
                status_code=response_status,
                content_type=content_type,
                depth=job.depth,
                error=str(error),
            )

            self.database.mark_failed(
                job.url,
                str(error),
            )

        finally:
            self.network_documents.pop(
                page_id,
                None,
            )

            await page.close()

    async def worker(
        self,
        *,
        worker_number: int,
        context: BrowserContext,
        downloader: DocumentDownloader,
        robots: RobotsCache,
    ) -> None:
        while not self.stop_requested:
            try:
                job = await asyncio.wait_for(
                    self.queue.get(),
                    timeout=5,
                )

            except asyncio.TimeoutError:
                if self.queue.empty():
                    return

                continue

            try:
                logger.info(
                    "Worker %s | Depth %s | %s",
                    worker_number,
                    job.depth,
                    job.url,
                )

                await self.crawl_page(
                    job=job,
                    context=context,
                    downloader=downloader,
                    robots=robots,
                )

            finally:
                self.queue.task_done()

    async def create_browser_context(
        self,
        browser: Browser,
    ) -> BrowserContext:
        context_options = {
            "user_agent": USER_AGENT,
            "accept_downloads": True,
            "java_script_enabled": True,
            "viewport": {
                "width": 1440,
                "height": 1000,
            },
        }

        if SESSION_STATE_FILE.exists():
            logger.info(
                "Loading saved browser session: %s",
                SESSION_STATE_FILE,
            )

            context_options["storage_state"] = str(
                SESSION_STATE_FILE
            )

        return await browser.new_context(
            **context_options
        )

    async def run(self) -> None:
        if not SEED_URLS:
            raise RuntimeError(
                "SEED_URLS is empty. Add at least one "
                "permitted website before running."
            )

        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        DATABASE_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        METADATA_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        SESSION_STATE_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.database.reset_interrupted_jobs()

        pending_jobs = (
            self.database.get_pending_jobs()
        )

        if pending_jobs:
            logger.info(
                "Resuming %s unfinished crawl job(s).",
                len(pending_jobs),
            )

            for job in pending_jobs:
                self.queued_urls.add(job.url)
                await self.queue.put(job)

        else:
            for seed_url in SEED_URLS:
                await self.enqueue(
                    CrawlJob(
                        url=seed_url,
                        source_url=None,
                        depth=0,
                    )
                )

        client_limits = httpx.Limits(
            max_connections=10,
            max_keepalive_connections=5,
        )

        client_timeout = httpx.Timeout(
            DOWNLOAD_TIMEOUT_SECONDS
        )

        async with httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
            },
            timeout=client_timeout,
            limits=client_limits,
            follow_redirects=True,
        ) as client:
            robots = RobotsCache(client)

            download_semaphore = asyncio.Semaphore(
                MAX_CONCURRENT_DOWNLOADS
            )

            async with async_playwright() as playwright:
                browser = (
                    await playwright.chromium.launch(
                        headless=HEADLESS,
                    )
                )

                context = await self.create_browser_context(
                    browser
                )

                downloader = DocumentDownloader(
                    database=self.database,
                    client=client,
                    context=context,
                    semaphore=download_semaphore,
                )

                workers = [
                    asyncio.create_task(
                        self.worker(
                            worker_number=worker_number,
                            context=context,
                            downloader=downloader,
                            robots=robots,
                        )
                    )
                    for worker_number in range(
                        1,
                        MAX_CONCURRENT_PAGES + 1,
                    )
                ]

                await asyncio.gather(*workers)

                await context.storage_state(
                    path=str(SESSION_STATE_FILE)
                )

                await context.close()
                await browser.close()

        logger.info(
            "Crawl finished. Pages processed this run: %s",
            self.processed_pages,
        )

        self.database.close()


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

async def main() -> None:
    crawler = NovaLegalCrawler()

    try:
        await crawler.run()

    except KeyboardInterrupt:
        logger.warning(
            "Crawler stopped by user. Progress is saved."
        )

    except Exception:
        logger.exception(
            "Crawler stopped because of an error."
        )


if __name__ == "__main__":
    asyncio.run(main())