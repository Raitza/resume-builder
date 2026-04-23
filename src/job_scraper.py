"""
Job description scraper.
Attempts to extract plain text from a job posting URL.
Returns (text, error_message). On success error_message is None.
"""

import re
import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Ordered list of CSS selectors to try, most specific first.
# The first selector that yields >= 100 chars of text wins.
_SELECTORS = [
    # Workday
    {"data-automation-id": "jobPostingDescription"},
    # Greenhouse
    {"id": "content"},
    # Lever
    {"class": "section-wrapper"},
    # LinkedIn
    {"class": "description__text"},
    {"class": "show-more-less-html__markup"},
    # Indeed
    {"id": "jobDescriptionText"},
    # Smart Recruiters
    {"class": "job-sections"},
    # Generic
    {"id": "job-description"},
    {"class": "job-description"},
    {"id": "jobDescription"},
    {"class": "jobDescription"},
    {"class": "job-details"},
    {"class": "posting-description"},
]

_MIN_CHARS = 100

# Patterns that indicate the page needs JavaScript to render
_JS_PLACEHOLDER_PATTERNS = [
    r'\{\{.*?\}\}',        # Angular/Vue/Handlebars: {{variable}}
    r'\[\[.*?\]\]',        # Some template engines: [[variable]]
    r'ng-bind',            # Angular directive
    r'data-reactroot',     # React
    r'__NEXT_DATA__',      # Next.js
]


def _clean(text: str) -> str:
    """Collapse excessive whitespace while keeping paragraph breaks."""
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Collapse runs of blank lines to a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _looks_like_js_rendered(html: str) -> bool:
    """True if the HTML appears to need JS rendering (has template placeholders or empty content)."""
    for pattern in _JS_PLACEHOLDER_PATTERNS:
        if re.search(pattern, html):
            return True
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body")
    if body:
        text_len = len(body.get_text(strip=True))
        script_count = len(soup.find_all("script"))
        if text_len < 200 and script_count > 5:
            return True
    return False


def _scrape_with_playwright(url: str) -> tuple[str, str | None]:
    """Fetch page content using Playwright for JS-rendered sites."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "", (
            "This page appears to require JavaScript rendering, but Playwright is not installed.\n"
            "Install it with: pip install playwright && playwright install chromium\n"
            "Or use Option B and paste the job description text directly."
        )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=20000, wait_until="networkidle")
            html = page.content()
            browser.close()
    except Exception as exc:
        return "", f"Playwright rendering failed: {exc}. Try Option B."

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "iframe"]):
        tag.decompose()

    # Try targeted selectors
    for selector in _SELECTORS:
        element = soup.find(attrs=selector)
        if element:
            text = _clean(element.get_text(separator="\n"))
            if len(text) >= _MIN_CHARS:
                return text, None

    # Fallbacks
    for tag_name in ("main", "body"):
        tag = soup.find(tag_name)
        if tag:
            text = _clean(tag.get_text(separator="\n"))
            if len(text) >= _MIN_CHARS:
                return text, None

    return "", "Could not extract job description even with JS rendering. Try Option B."


def scrape_job_description(url: str) -> tuple[str, str | None]:
    """Fetch and extract job description text from *url*.

    Returns:
        (text, None)        on success
        ("", error_message) on failure
    """
    if not url.startswith(("http://", "https://")):
        return "", "URL must start with http:// or https://"

    try:
        response = requests.get(url, headers=_HEADERS, timeout=12)
    except requests.exceptions.SSLError:
        return "", "SSL certificate error. Try Option B (paste text directly)."
    except requests.exceptions.ConnectionError:
        return "", "Could not connect to the URL. Check your internet connection or try Option B."
    except requests.exceptions.Timeout:
        return "", "Request timed out after 12 seconds. Try Option B."
    except requests.exceptions.RequestException as exc:
        return "", f"Request failed: {exc}. Try Option B."

    if response.status_code == 403:
        return "", (
            "Access denied (403). This site blocks automated requests. "
            "Please use Option B and paste the job description text directly."
        )
    if response.status_code == 429:
        return "", "Rate limited (429). Please use Option B."
    if response.status_code != 200:
        return "", f"Server returned HTTP {response.status_code}. Try Option B."

    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type and "text" not in content_type:
        return "", f"Unexpected content type ({content_type}). Only HTML pages are supported."

    soup = BeautifulSoup(response.text, "lxml")

    # Remove noise tags before extracting text
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "iframe"]):
        tag.decompose()

    # Try targeted selectors first
    for selector in _SELECTORS:
        element = soup.find(attrs=selector)
        if element:
            text = _clean(element.get_text(separator="\n"))
            if len(text) >= _MIN_CHARS:
                return text, None

    # Fallback: <main> tag
    main = soup.find("main")
    if main:
        text = _clean(main.get_text(separator="\n"))
        if len(text) >= _MIN_CHARS:
            return text, None

    # Last resort: full <body>
    body = soup.find("body")
    if body:
        text = _clean(body.get_text(separator="\n"))
        if len(text) >= _MIN_CHARS:
            return text, None

    # If extraction failed, check if the page needs JS rendering
    if _looks_like_js_rendered(response.text):
        return _scrape_with_playwright(url)

    return "", (
        "Could not extract job description from this page. "
        "The site may require login or use JavaScript rendering. "
        "Please use Option B and paste the text directly."
    )
