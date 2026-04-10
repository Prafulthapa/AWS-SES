"""
Carpentry Lead Scraper - CANADA EDITION
Scrapes Google Maps for carpentry businesses in Canada
WITH AUTO-SAVE EVERY 500 LEADS + SEARCH PROGRESS TRACKING
UPDATED: Uses ONLY requests for email scraping (fast, no Selenium fallback)

FIXES:
  - Bug 1: Image filenames (e.g. cropped-sk@5x-270x270.png) no longer match as emails
  - Bug 2: URL-encoded prefixes (e.g. %20) are stripped before validation
"""

import logging
import time
import random
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, unquote
import json
import requests
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Force English locale to prevent Nepali/Devanagari text
import os
os.environ['LANG'] = 'en_US.UTF-8'
os.environ['LANGUAGE'] = 'en_US'
os.environ['LC_ALL'] = 'en_US.UTF-8'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# FIX 1: File extensions that are NEVER valid email TLDs.
# Catches image filenames like "cropped-sk@5x-270x270.png" that slip past
# the normal email regex because .png looks like a TLD.
# ─────────────────────────────────────────────────────────────────────────────
INVALID_EMAIL_EXTENSIONS = {
    # Images
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'ico', 'bmp', 'tiff', 'tif',
    'avif', 'heic', 'heif',
    # Documents
    'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv',
    # Code / web assets
    'js', 'jsx', 'ts', 'tsx', 'css', 'scss', 'less', 'html', 'htm', 'xml',
    'json', 'yaml', 'yml', 'map', 'min',
    # Archives
    'zip', 'tar', 'gz', 'rar', '7z',
    # Media
    'mp4', 'mp3', 'wav', 'avi', 'mov', 'mkv', 'webm',
    # Fonts
    'woff', 'woff2', 'ttf', 'eot', 'otf',
}


class CarpentryLeadScraper:
    """Scrape carpentry leads from Google Maps - Canada Edition."""

    def __init__(self):
        self.all_leads = []
        self.seen_emails = set()  # Track emails instead of company names!
        self.seen_websites = set()  # Track websites to avoid scraping duplicates!
        self.driver = None

        # NEW: Progress tracking file (persistent across restarts)
        self.progress_file = "data/scraper_progress.json"
        self.completed_searches = set()
        self.current_search_index = 0
        self.total_searches_count = 0

        # NEW: Save every 500 leads
        self.save_milestone = 500
        self.last_save_count = 0

        # NEW: Email scraping session for finding real emails
        self.email_session = requests.Session()
        self.email_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        # NEW: Email statistics
        self.email_stats = {
            'verified': 0,      # Found on website
            'unverified': 0,    # Generated guess
            'none': 0           # No email at all
        }

        # Load previous progress (must do this FIRST)
        self.load_progress()

        # NEW: Session file - reuse existing or create new
        self.session_file = self.get_or_create_session_file()

        # Load previously scraped emails to avoid duplicates
        self.load_previous_scrapes()

        self.setup_selenium()

    def get_or_create_session_file(self):
        """Get existing session file or create new one."""
        try:
            if Path(self.progress_file).exists():
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)

                existing_session = progress_data.get('active_session_file')

                if existing_session and Path(existing_session).exists():
                    logger.info(f"📂 Continuing with existing session: {existing_session}")

                    with open(existing_session, 'r', encoding='utf-8') as f:
                        self.all_leads = json.load(f)

                    self.last_save_count = len(self.all_leads)
                    logger.info(f"✅ Loaded {len(self.all_leads)} leads from previous session")

                    return existing_session

            session_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_session = f"data/session_{session_timestamp}.json"
            logger.info(f"📂 Creating new session file: {new_session}")

            return new_session

        except Exception as e:
            logger.warning(f"⚠️  Error checking session file: {e}")
            session_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            return f"data/session_{session_timestamp}.json"

    def load_progress(self):
        """Load search progress from previous runs."""
        try:
            if Path(self.progress_file).exists():
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    progress_data = json.load(f)

                self.completed_searches = set(progress_data.get('completed_searches', []))
                self.current_search_index = progress_data.get('current_search_index', 0)
                self.total_searches_count = progress_data.get('total_searches', 0)

                logger.info("📋 Loading previous search progress...")
                logger.info(f"  ✅ {len(self.completed_searches)} searches already completed")
                logger.info(f"  ➡️  Will resume from search #{self.current_search_index + 1}")
            else:
                logger.info("  ℹ️  No previous progress found (first run)")
        except Exception as e:
            logger.warning(f"  ⚠️  Could not load progress: {e}")
            self.completed_searches = set()
            self.total_searches_count = 0
            self.current_search_index = 0

    def save_progress_state(self):
        """Save current search progress."""
        try:
            progress_data = {
                'completed_searches': list(self.completed_searches),
                'current_search_index': self.current_search_index,
                'total_searches': self.total_searches_count,
                'last_updated': datetime.now().isoformat(),
                'total_leads_collected': len(self.all_leads),
                'active_session_file': self.session_file,
                'email_stats': self.email_stats
            }

            Path(self.progress_file).parent.mkdir(parents=True, exist_ok=True)

            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2)

            logger.debug(f"💾 Progress state saved (search #{self.current_search_index})")
        except Exception as e:
            logger.error(f"❌ Failed to save progress state: {e}")

    def setup_selenium(self):
        """Configure Selenium with Chrome."""
        logger.info("🌐 Initializing Chrome browser...")

        chrome_options = Options()

        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        import os
        if os.path.exists('/usr/bin/chromium'):
            chrome_options.binary_location = '/usr/bin/chromium'
        elif os.path.exists('/usr/bin/chromium-browser'):
            chrome_options.binary_location = '/usr/bin/chromium-browser'

        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')

        chrome_options.add_argument('--lang=en-US')
        chrome_options.add_argument('--accept-lang=en-US,en')
        chrome_options.add_experimental_option('prefs', {
            'intl.accept_languages': 'en-US,en;q=0.9',
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.geolocation': 2
        })

        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            self.driver = webdriver.Chrome(options=chrome_options)

            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'language', {
                        get: () => 'en-US'
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                '''
            })

            logger.info("✅ Chrome browser ready")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Chrome: {e}")
            raise

    def load_previous_scrapes(self):
        """Load all previously scraped EMAILS and WEBSITES to avoid duplicates."""
        logger.info("📂 Loading previous scrapes to avoid duplicates...")

        try:
            data_dir = Path("data")

            if not data_dir.exists():
                logger.info("  ℹ️  No previous data found (first run)")
                return

            json_files = list(data_dir.glob("raw_leads_*.json")) + list(data_dir.glob("session_*.json"))

            if not json_files:
                logger.info("  ℹ️  No previous scrapes found (first run)")
                return

            logger.info(f"  🔄 Found {len(json_files)} previous scrape files")

            total_loaded_emails = 0
            total_loaded_websites = 0
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        leads = json.load(f)

                    for lead in leads:
                        email = lead.get('email', '')
                        website = lead.get('website', '')

                        if email:
                            self.seen_emails.add(email.lower())
                            total_loaded_emails += 1

                        if website:
                            website_clean = website.lower().strip().rstrip('/')
                            self.seen_websites.add(website_clean)
                            total_loaded_websites += 1

                except Exception as e:
                    logger.debug(f"  ⚠️  Error loading {json_file.name}: {e}")
                    continue

            logger.info(f"  ✅ Loaded {total_loaded_emails} previously scraped emails")
            logger.info(f"  ✅ Loaded {total_loaded_websites} previously scraped websites")
            logger.info(f"  🛡️  Duplicate emails and websites will be skipped")

        except Exception as e:
            logger.error(f"  ❌ Error loading previous scrapes: {e}")

    def save_progress(self, force=False, after_each_search=False):
        """Save current progress to file."""
        current_count = len(self.all_leads)

        current_milestone = (current_count // self.save_milestone) * self.save_milestone
        last_milestone = (self.last_save_count // self.save_milestone) * self.save_milestone

        should_save_milestone = current_milestone > last_milestone and current_count >= self.save_milestone
        should_save = force or should_save_milestone or after_each_search

        if not should_save:
            return

        if not self.all_leads:
            return

        try:
            Path(self.session_file).parent.mkdir(parents=True, exist_ok=True)

            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.all_leads, f, indent=2, ensure_ascii=False)

            if should_save_milestone or force:
                logger.info("")
                logger.info("=" * 70)
                logger.info(f"💾 MILESTONE REACHED: {current_count} leads collected!")
                logger.info(f"💾 Progress saved → {self.session_file}")
                logger.info(f"📊 Email stats:")
                logger.info(f"   ✅ Verified (scraped): {self.email_stats['verified']}")
                logger.info(f"   ⚠️  Unverified (guessed): {self.email_stats['unverified']}")
                logger.info(f"   ❌ No email: {self.email_stats['none']}")
                logger.info(f"📊 Next save at: {current_milestone + self.save_milestone} leads")
                logger.info("=" * 70)
                logger.info("")
                self.last_save_count = current_count
            elif after_each_search:
                logger.debug(f"💾 Auto-saved {current_count} leads to session file")

        except Exception as e:
            logger.error(f"❌ Failed to save progress: {e}")

    def find_emails_from_website(self, website_url):
        """
        Scrape a website to find real email addresses.

        Strategy:
        1. Try homepage with requests (fast)
        2. Try expanded list of contact page URLs with requests
        3. If still nothing, use Selenium on homepage + contact page
           (catches JS-rendered footers like Squarespace/Wix/Webflow)
        """
        if not website_url:
            return []

        from urllib.parse import urljoin

        try:
            if not website_url.startswith(('http://', 'https://')):
                website_url = 'https://' + website_url

            # ── PHASE 1: requests on homepage ────────────────────────────────
            logger.debug(f"  🏠 Checking homepage (requests)...")
            emails = self._try_scrape_url_requests_only(website_url)
            if emails:
                logger.info(f"  ✅ Found {len(emails)} emails on homepage")
                return self._rank_emails(list(emails))

            # ── PHASE 2: requests on common contact page paths ───────────────
            # Expanded list — many Canadian SMB sites use non-standard paths
            contact_paths = [
                '/contact',
                '/contact.html',
                '/contact-us',
                '/contact-us.html',
                '/contactus',
                '/contactus.html',
                '/about',
                '/about-us',
                '/about.html',
                '/about-us.html',
                '/reach-us',
                '/get-in-touch',
                '/info',
                '/pages/contact',        # Shopify
                '/pages/contact-us',     # Shopify
                '/pages/about',          # Shopify
            ]

            for path in contact_paths:
                contact_url = urljoin(website_url, path)
                logger.debug(f"  🔄 Trying {path}...")
                emails = self._try_scrape_url_requests_only(contact_url)
                if emails:
                    logger.info(f"  ✅ Found {len(emails)} emails on {path}")
                    return self._rank_emails(list(emails))

            # ── PHASE 3: Selenium fallback for JS-rendered sites ─────────────
            # Squarespace, Wix, Webflow, Shopify all render content via JS.
            # requests only gets the bare HTML shell — the footer with the
            # email address is injected by JS after page load.
            # We reuse the existing Selenium driver (already open).
            logger.debug(f"  🤖 Trying Selenium fallback (JS-rendered site)...")
            emails = self._try_scrape_url_selenium(website_url)
            if emails:
                logger.info(f"  ✅ Found {len(emails)} emails via Selenium on homepage")
                return self._rank_emails(list(emails))

            # Also try /contact with Selenium
            contact_url = urljoin(website_url, '/contact')
            emails = self._try_scrape_url_selenium(contact_url)
            if emails:
                logger.info(f"  ✅ Found {len(emails)} emails via Selenium on /contact")
                return self._rank_emails(list(emails))

            logger.debug(f"  ❌ No emails found after all methods")
            return []

        except Exception as e:
            logger.error(f"  ❌ Error: {type(e).__name__} - {str(e)}")
            return []

    def _try_scrape_url_selenium(self, url):
        """
        Scrape a URL using the existing Selenium driver.
        Used as fallback for JS-rendered sites where requests gets empty HTML.
        Reuses self.driver — no new browser opened.
        """
        emails = set()
        try:
            # Save current URL so we can go back to Google Maps after
            current_url = self.driver.current_url

            logger.debug(f"    🤖 Selenium loading: {url}")
            self.driver.get(url)
            time.sleep(3)  # Wait for JS to render

            page_source = self.driver.page_source
            emails = self._extract_emails_from_html(page_source)

            # Go back to Google Maps
            self.driver.get(current_url)
            time.sleep(1)

        except Exception as e:
            logger.debug(f"    ❌ Selenium fallback error: {type(e).__name__}")
            # Try to return to Google Maps even on error
            try:
                self.driver.back()
            except:
                pass

        return emails

    def _try_scrape_url_requests_only(self, url):
        """Try to scrape a URL for emails using ONLY requests."""
        emails = set()

        try:
            response = self.email_session.get(url, timeout=10)
            response.raise_for_status()
            logger.debug(f"    ⚡ Requests OK (HTTP {response.status_code})")

            emails = self._extract_emails_from_html(response.text)
            if emails:
                return emails

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.debug(f"    ❌ 403 Forbidden - skipping")
            elif e.response.status_code == 404:
                logger.debug(f"    ❌ 404 Not Found")
            else:
                logger.debug(f"    ❌ HTTP {e.response.status_code}")
            return emails

        except requests.exceptions.Timeout:
            logger.debug(f"    ❌ Timeout")
            return emails

        except Exception as e:
            logger.debug(f"    ❌ Request error: {type(e).__name__}")
            return emails

        return emails

    def _extract_emails_from_html(self, raw_html):
        """
        Extract emails from HTML content.

        FIX 1: img/script/style tags are removed BEFORE text extraction so
                image filenames like "cropped-sk@5x-270x270.png" are never
                seen by the email regex.
        FIX 2: All candidates pass through _clean_email which now URL-decodes
                and strips %20 and similar prefixes.
        """
        emails = set()

        try:
            # Pre-filter Wix junk
            raw_html = re.sub(r'[a-f0-9]{32}@sentry[^"\s<>]*\.wixpress\.com', '', raw_html, flags=re.I)
            raw_html = re.sub(r'[a-f0-9]{20,}@[^"\s<>]*wixpress\.com', '', raw_html, flags=re.I)

            soup = BeautifulSoup(raw_html, 'html.parser')

            # ─────────────────────────────────────────────────────────────────
            # FIX 1: Strip ALL tags whose content is never a real email address.
            # This removes src/href/data-src attributes that contain filenames
            # with @ characters (e.g. thumbnails, CDN paths, tracking pixels).
            # ─────────────────────────────────────────────────────────────────
            for tag in soup(["script", "style", "noscript", "img", "source",
                             "video", "audio", "canvas", "svg", "picture"]):
                tag.decompose()

            # STEP 1: Look for mailto: links (most reliable)
            mailto_links = soup.find_all('a', href=re.compile(r'^mailto:', re.I))

            for link in mailto_links:
                email_raw = link.get('href', '').replace('mailto:', '').split('?')[0].strip()
                email = self._clean_email(email_raw)

                if email and self._is_valid_email(email):
                    if 'wixpress' not in email.lower():
                        emails.add(email.lower())
                        logger.debug(f"    ✅ mailto: {email}")

            if emails:
                return emails

            # STEP 2: Search visible text (img/script already removed above)
            visible_text = soup.get_text(separator=' ', strip=True)
            text_emails = self._extract_emails_from_text(visible_text)

            for email in text_emails:
                cleaned = self._clean_email(email)
                if cleaned and self._is_valid_email(cleaned):
                    if 'wixpress' not in cleaned.lower() and 'sentry' not in cleaned.lower():
                        emails.add(cleaned.lower())
                        logger.debug(f"    ✅ text: {cleaned}")

            if emails:
                return emails

            # STEP 3: Search remaining HTML (last resort — img tags already gone)
            remaining_html = str(soup)
            all_text_emails = self._extract_emails_from_text(remaining_html)

            for email in all_text_emails:
                cleaned = self._clean_email(email)
                if cleaned and self._is_valid_email(cleaned):
                    if 'wixpress' not in cleaned.lower() and 'sentry' not in cleaned.lower():
                        emails.add(cleaned.lower())
                        logger.debug(f"    ✅ html: {cleaned}")

        except Exception as e:
            logger.error(f"    ❌ Extract error: {type(e).__name__}")

        return emails

    def _rank_emails(self, emails):
        """Rank emails by quality - prefer real people over generic addresses."""
        if not emails:
            return []

        def email_score(email):
            score = 0
            local = email.split('@')[0].lower()

            if '.' in local and len(local) > 5:
                score += 100

            name_patterns = ['john', 'mike', 'david', 'chris', 'sarah', 'joe', 'tom', 'steve']
            if any(name in local for name in name_patterns):
                score += 50

            generic = ['info', 'contact', 'hello', 'sales', 'support', 'office', 'admin']
            if local in generic:
                score -= 30

            if len(local) < 15:
                score += 20

            domain = email.split('@')[1]
            if domain.count('.') == 1:
                score += 10

            return score

        ranked = sorted(emails, key=email_score, reverse=True)

        if len(ranked) > 1:
            logger.debug(f"  📊 Ranked {len(ranked)} emails:")
            for i, email in enumerate(ranked[:3]):
                logger.debug(f"     {i+1}. {email} (score: {email_score(email)})")

        return ranked

    def _clean_email(self, email):
        """
        Clean extracted email address from common contamination.

        FIX 2: URL-decode the entire string first so %20, %40, etc. are
                resolved before stripping. This catches:
                  "%20613carpentry.contracting@gmail.com"
                  → "613carpentry.contracting@gmail.com"
                  → "carpentry.contracting@gmail.com"  (leading digits stripped)
        """
        if not email:
            return None

        # Strip whitespace
        email = email.strip()

        # ─────────────────────────────────────────────────────────────────────
        # FIX 2: URL-decode first. This handles %20 (space), %40 (@), etc.
        # that get picked up from href attributes or encoded page content.
        # ─────────────────────────────────────────────────────────────────────
        email = unquote(email).strip()

        if '@' not in email:
            return None

        local_part = email.split('@')[0]
        domain = email.split('@')[1].split()[0].strip()

        # Remove leading numbers (zip codes, street numbers, etc.)
        local_part = re.sub(r'^[0-9]+', '', local_part)

        # Remove trailing numbers
        local_part = re.sub(r'[0-9]+$', '', local_part)

        # Remove special characters at start/end
        local_part = local_part.strip('.,;:!?()[]{}"\' ')
        domain = domain.rstrip('.,;:!?()[]{}"\' ')

        if not local_part or not domain:
            return None

        email = f"{local_part}@{domain}"
        return email

    def _extract_emails_from_text(self, text):
        """
        Extract email addresses from text using regex.

        Handles:
        - Plain emails:          contact@company.com
        - Labelled emails:       E: contact@company.com
                                 Email: contact@company.com
                                 email – contact@company.com
        - Mixed case:            Gandfcustoms@gmail.com
        """
        emails = set()

        # ── Pattern 1: standard email anywhere in text ───────────────────────
        # Requires first char to be a letter (blocks "5x@..." filenames).
        pattern = r'\b([A-Za-z][A-Za-z0-9._%-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b'
        for match in re.findall(pattern, text, re.IGNORECASE):
            cleaned = self._clean_email(match.lower())
            if cleaned and self._is_valid_email(cleaned):
                emails.add(cleaned)

        # ── Pattern 2: labelled emails — "E:", "Email:", "E –", etc. ─────────
        # Catches "E: Gandfcustoms@gmail.com" where the label sits right before
        # the address and might confuse word-boundary detection.
        label_pattern = r'(?:e-?mail\s*[:\-–—]?\s*|e\s*[:\-–—]\s*)([A-Za-z0-9][A-Za-z0-9._%-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,})'
        for match in re.findall(label_pattern, text, re.IGNORECASE):
            cleaned = self._clean_email(match.lower())
            if cleaned and self._is_valid_email(cleaned):
                emails.add(cleaned)

        return emails

    def _is_valid_email(self, email):
        """
        Validate email address and filter out junk.

        FIX 1 (secondary guard): Reject any email whose TLD is a known file
        extension. This is a belt-and-suspenders check — the primary fix is
        removing <img> tags before extraction, but this catches any edge cases
        that slip through (e.g. inline base64 data URIs with filenames).
        """
        if not email or '@' not in email:
            return False

        email_lower = email.lower()

        # ─────────────────────────────────────────────────────────────────────
        # FIX 1 (guard): Reject if the TLD is a file extension, not a real TLD.
        # e.g. "cropped-sk@5x-270x270.png" → TLD is "png" → rejected.
        # ─────────────────────────────────────────────────────────────────────
        tld = email_lower.rsplit('.', 1)[-1]  # everything after last dot
        if tld in INVALID_EMAIL_EXTENSIONS:
            logger.debug(f"  ❌ Filtered file-extension TLD: {email} (.{tld})")
            return False

        # Filter out Wix/template/system emails
        junk_domains = [
            'wixpress.com',
            'sentry.io',
            'wix.com',
            'weebly.com',
            'squarespace.com',
            'wordpress.com',
            'example.com',
            'email.com',
            'domain.com',
            'test.com',
            'yourcompany.com',
            'company.com',
            'sample.com',
            'placeholder',
            'localhost',
        ]

        for junk in junk_domains:
            if junk in email_lower:
                logger.debug(f"  ❌ Filtered junk domain: {email} ({junk})")
                return False

        junk_prefixes = [
            'noreply@', 'no-reply@', 'donotreply@', 'do-not-reply@',
            'mailer@', 'postmaster@', 'webmaster@', 'admin@localhost',
            'test@', 'privacy@', 'legal@', 'dmca@', 'abuse@', 'spam@',
            'image@', 'icon@', 'logo@', 'bounce@', 'return@',
        ]

        for prefix in junk_prefixes:
            if email_lower.startswith(prefix):
                return False

        local_part = email_lower.split('@')[0]

        # Filter hex-string local parts (Wix/Sentry tracking IDs)
        if len(local_part) > 20:
            hex_chars = sum(1 for c in local_part if c in '0123456789abcdef')
            if hex_chars / len(local_part) > 0.8:
                logger.debug(f"  ❌ Filtered hex string email: {email}")
                return False

        if len(local_part) > 30:
            logger.debug(f"  ❌ Filtered long local part: {email}")
            return False

        if not re.search(r'\.[a-z]{2,}$', email_lower):
            return False

        domain = email_lower.split('@')[1]
        if domain.replace('.', '').replace('-', '').isdigit():
            return False

        if email.count('@') != 1:
            return False

        return True

    def search_google_maps(self, query, location, max_results=60):
        """Search Google Maps for businesses - TWO PHASE PROCESSING."""
        logger.info(f"🔍 Google Maps: {query} in {location}")
        leads = []

        try:
            search_query = f"{query} in {location}"
            url = f"https://www.google.com/maps/search/{quote_plus(search_query)}?hl=en"

            logger.info(f"  🌐 Loading Google Maps...")
            self.driver.get(url)

            time.sleep(5)

            logger.info(f"  📜 Scrolling to load results...")
            self.scroll_results_panel(max_results)

            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            business_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")

            logger.info(f"  📋 Found {len(business_elements)} business listings")

            business_data = []
            seen_websites_this_search = set()

            logger.info(f"")
            logger.info(f"  🔍 Listing all businesses and checking for duplicates...")
            for idx in range(min(len(business_elements), max_results)):
                try:
                    current_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")
                    if idx >= len(current_elements):
                        break

                    element = current_elements[idx]

                    element.click()
                    time.sleep(0.5)

                    try:
                        name_elem = self.driver.find_element(By.CSS_SELECTOR, "h1.DUwDvf")
                        name = name_elem.text.strip()
                    except:
                        try:
                            name_elem = self.driver.find_element(By.CSS_SELECTOR, "h2.bwoZTb")
                            name = name_elem.text.strip()
                        except:
                            name = f"Unknown Business #{idx + 1}"

                    website = ""
                    try:
                        website_elem = self.driver.find_element(By.CSS_SELECTOR, "a[data-item-id*='authority']")
                        website = website_elem.get_attribute('href')
                    except:
                        try:
                            website_elem = self.driver.find_element(By.XPATH, "//a[contains(@aria-label, 'Website') or contains(., 'Website')]")
                            website = website_elem.get_attribute('href')
                        except:
                            try:
                                links = self.driver.find_elements(By.CSS_SELECTOR, "div.m6QErb a[href^='http']")
                                for link in links:
                                    href = link.get_attribute('href')
                                    if href and not any(x in href.lower() for x in ['google.com', 'facebook.com', 'instagram.com', 'youtube.com']):
                                        website = href
                                        break
                            except:
                                pass

                    website_clean = website.lower().strip().rstrip('/') if website else None

                    is_duplicate = False
                    if website_clean:
                        if website_clean in self.seen_websites or website_clean in seen_websites_this_search:
                            is_duplicate = True
                            logger.info(f"    [{idx + 1}/{min(len(business_elements), max_results)}] {name} - ⭕ DUPLICATE (same website)")
                        else:
                            seen_websites_this_search.add(website_clean)
                            logger.info(f"    [{idx + 1}/{min(len(business_elements), max_results)}] {name}")
                    else:
                        logger.info(f"    [{idx + 1}/{min(len(business_elements), max_results)}] {name} - ⚠️  No website")

                    business_data.append({
                        'name': name,
                        'website': website,
                        'is_duplicate': is_duplicate,
                        'index': idx
                    })

                except Exception as e:
                    logger.debug(f"    [{idx + 1}] Error reading: {e}")
                    business_data.append({
                        'name': f"Error #{idx + 1}",
                        'website': None,
                        'is_duplicate': False,
                        'index': idx
                    })

            unique_businesses = [b for b in business_data if not b['is_duplicate']]

            logger.info(f"")
            logger.info(f"  ✅ Listed {len(business_data)} total businesses")
            logger.info(f"  ✅ Found {len(unique_businesses)} unique businesses (skipping {len(business_data) - len(unique_businesses)} duplicates)")
            logger.info(f"  🔄 Now processing {len(unique_businesses)} unique businesses...")
            logger.info(f"")

            processed = 0
            total_unique = len(unique_businesses)

            for business_info in business_data:
                if business_info['is_duplicate']:
                    continue

                try:
                    idx = business_info['index']
                    business_name = business_info['name']

                    current_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")

                    if idx >= len(current_elements):
                        logger.warning(f"  ⚠️  Business #{idx + 1} not found in list, skipping")
                        continue

                    element = current_elements[idx]

                    logger.info(f"  ▶️  Processing unique business #{processed + 1}/{total_unique}: {business_name}...")

                    element.click()
                    time.sleep(random.uniform(1, 2))

                    lead = self.extract_business_details()

                    if not lead:
                        logger.warning(f"    ⚠️  Could not extract details, skipping")
                        continue

                    email_verified = lead.get('email_verified', False)
                    if not email_verified:
                        logger.info(f"    ⭕ Unverified email - skipping (only saving verified emails)")
                        continue

                    email = lead.get('email', '').lower()
                    if email and email in self.seen_emails:
                        logger.info(f"    ⭕ Duplicate email: {email} - skipping")
                        continue

                    if email:
                        self.seen_emails.add(email)

                    leads.append(lead)
                    processed += 1

                    logger.info(f"    ✅ Saved verified lead #{processed}")

                    time.sleep(random.uniform(0.5, 1.5))

                except Exception as e:
                    logger.error(f"    ❌ Error processing business #{idx + 1}: {e}")
                    continue

            logger.info(f"")

        except Exception as e:
            logger.error(f"  ❌ Search error: {e}")

        logger.info(f"✅ Google Maps {location}: {len(leads)} leads collected")
        return leads

    def scroll_results_panel(self, target_count=20):
        """Scroll the results panel to load more businesses."""
        try:
            scrollable = self.driver.find_element(By.CSS_SELECTOR, "div[role='feed']")

            last_height = 0
            attempts = 0
            max_attempts = 10

            while attempts < max_attempts:
                self.driver.execute_script(
                    'arguments[0].scrollTo(0, arguments[0].scrollHeight);',
                    scrollable
                )

                time.sleep(2)

                results = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/maps/place/']")
                if len(results) >= target_count:
                    break

                new_height = self.driver.execute_script('return arguments[0].scrollHeight', scrollable)
                if new_height == last_height:
                    attempts += 1
                else:
                    attempts = 0

                last_height = new_height

        except Exception as e:
            logger.debug(f"Scroll error: {e}")

    def extract_business_details(self):
        """Extract details from currently selected business."""
        try:
            time.sleep(1)

            name = ""
            try:
                name_elem = self.driver.find_element(By.CSS_SELECTOR, "h1.DUwDvf")
                name = name_elem.text.strip()
            except:
                try:
                    name_elem = self.driver.find_element(By.CSS_SELECTOR, "h2.bwoZTb")
                    name = name_elem.text.strip()
                except:
                    return None

            if not name:
                return None

            rating = ""
            try:
                rating_elem = self.driver.find_element(By.CSS_SELECTOR, "div.F7nice span[aria-label*='stars']")
                rating = rating_elem.get_attribute('aria-label')
            except:
                pass

            address = ""
            try:
                address_elem = self.driver.find_element(By.CSS_SELECTOR, "button[data-item-id*='address']")
                address = address_elem.get_attribute('aria-label')
                if address and 'Address:' in address:
                    address = address.replace('Address:', '').strip()
            except:
                try:
                    address_elem = self.driver.find_element(By.CSS_SELECTOR, "div.rogA2c div.Io6YTe")
                    address = address_elem.text.strip()
                except:
                    pass

            phone = ""
            try:
                phone_elem = self.driver.find_element(By.CSS_SELECTOR, "button[data-item-id*='phone']")
                phone_text = phone_elem.get_attribute('aria-label')
                if phone_text and 'Phone:' in phone_text:
                    phone = phone_text.replace('Phone:', '').strip()
            except:
                pass

            website = ""
            try:
                website_elem = self.driver.find_element(By.CSS_SELECTOR, "a[data-item-id*='authority']")
                website = website_elem.get_attribute('href')
            except:
                try:
                    website_elem = self.driver.find_element(By.XPATH, "//a[contains(@aria-label, 'Website') or contains(., 'Website')]")
                    website = website_elem.get_attribute('href')
                except:
                    try:
                        links = self.driver.find_elements(By.CSS_SELECTOR, "div.m6QErb a[href^='http']")
                        for link in links:
                            href = link.get_attribute('href')
                            if href and not any(x in href.lower() for x in ['google.com', 'facebook.com', 'instagram.com', 'youtube.com']):
                                website = href
                                break
                    except:
                        pass

            province = self.extract_province(address)

            if website:
                website_clean = website.lower().strip().rstrip('/')

                if website_clean in self.seen_websites:
                    logger.info(f"  ⭕ Duplicate website: {website} - skipping scrape")
                    return None

                self.seen_websites.add(website_clean)

            email = ""
            email_verified = False

            if website:
                try:
                    logger.info(f"  🌐 Attempting to scrape: {website}")
                    found_emails = self.find_emails_from_website(website)

                    if found_emails:
                        email = found_emails[0]
                        email_verified = True
                        self.email_stats['verified'] += 1
                        logger.info(f"  ✅ SUCCESS! Found: {email}")
                    else:
                        logger.warning(f"  ❌ NO EMAILS FOUND on {website} - using fallback")
                        email = self.generate_email(name, website)
                        email_verified = False
                        self.email_stats['unverified'] += 1

                except Exception as e:
                    logger.error(f"  ❌ SCRAPING FAILED for {website}: {str(e)}")
                    email = self.generate_email(name, website)
                    email_verified = False
                    self.email_stats['unverified'] += 1
            else:
                logger.debug(f"  ⚠️  No website URL - generating fallback")
                email = self.generate_email(name)
                email_verified = False
                if email:
                    self.email_stats['unverified'] += 1
                else:
                    self.email_stats['none'] += 1

            return {
                'company_name': name,
                'executive_name': '',
                'email': email,
                'email_verified': email_verified,
                'phone': phone,
                'website': website,
                'address': address,
                'province': province,
                'rating': rating,
                'source': 'Google Maps',
                'scraped_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

        except Exception as e:
            logger.debug(f"Extract details error: {e}")
            return None

    def extract_province(self, address):
        """Extract Canadian province from address string."""
        provinces = [
            'ON', 'QC', 'BC', 'AB', 'MB', 'SK', 'NS', 'NB', 'NL', 'PE', 'NT', 'YT', 'NU'
        ]

        for province in provinces:
            if re.search(r'\b' + province + r'\b', address.upper()):
                return province

        return ""

    def generate_email(self, business_name, website=None):
        """Generate fallback email when scraping fails. Marked as UNVERIFIED."""
        if website:
            try:
                domain = re.search(r'https?://(?:www\.)?([^/]+)', website)
                if domain:
                    domain = domain.group(1)
                    return f"info@{domain}"
            except:
                pass

        clean = business_name.lower()
        clean = re.sub(r'\b(inc|llc|ltd|corp|carpentry|construction)\b', '', clean)
        clean = re.sub(r'[^a-z0-9]', '', clean)

        if clean:
            return f"info@{clean}.com"

        return ""

    def run_full_scrape(self, locations=None):
        """Run full scraping process for all search terms and locations."""
        logger.info("=" * 70)
        logger.info("🚀 CARPENTRY LEAD SCRAPER STARTING (GOOGLE MAPS)")
        logger.info("🇨🇦 CANADA TOTAL MARKET SATURATION")
        logger.info("🎯 TARGET: 9,000-12,000 LEADS")
        logger.info("⚡ EMAIL SCRAPING: REQUESTS ONLY (FAST)")
        logger.info("✅ QUALITY FILTER: ONLY VERIFIED EMAILS SAVED")
        logger.info("=" * 70)

        search_terms = [
            "carpentry", "carpenter", "carpentry services", "carpentry contractor",
            "cabinet maker", "cabinetmaker", "custom cabinets", "kitchen cabinets",
            "woodworking", "custom woodworking", "wood shop",
            "finish carpentry", "trim carpentry", "framing contractor", "millwork",
            "kitchen remodeling", "bathroom remodeling", "home remodeling",
            "renovation contractor"
        ]

        if locations is None:
            master_file = Path("data/scraper_locations.json")
            if master_file.exists():
                try:
                    with open(master_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    if not isinstance(data, list):
                        raise ValueError(f"Master file {master_file} must contain a JSON list")

                    if not all(isinstance(x, str) for x in data):
                        raise ValueError(f"Master file {master_file} must contain only strings")

                    locations = data
                    if locations:
                        logger.info(f"📂 Validated and loaded {len(locations)} locations from master file: {master_file}")
                except Exception as e:
                    logger.error(f"❌ Error loading master locations: {e}")

        if locations is None:
            locations = [
                "Toronto ON", "Ottawa ON", "Mississauga ON", "Brampton ON", "Hamilton ON",
                "London ON", "Markham ON", "Vaughan ON", "Kitchener ON", "Windsor ON",
                "Montreal QC", "Quebec City QC", "Laval QC", "Gatineau QC", "Longueuil QC",
                "Vancouver BC", "Surrey BC", "Burnaby BC", "Richmond BC", "Abbotsford BC",
                "Calgary AB", "Edmonton AB", "Red Deer AB", "Lethbridge AB", "St. Albert AB",
                "Winnipeg MB", "Brandon MB", "Saskatoon SK", "Regina SK",
                "Halifax NS", "Moncton NB", "Saint John NB", "St. John's NL",
                "Charlottetown PE", "Yellowknife NT", "Whitehorse YT",
            ]

        all_searches = [(term, loc) for loc in locations for term in search_terms]
        self.total_searches_count = len(all_searches)
        total_searches = self.total_searches_count

        logger.info(f"📊 MARKET SATURATION STRATEGY:")
        logger.info(f"   - {len(search_terms)} search terms")
        logger.info(f"   - {len(locations)} Canadian locations")
        logger.info(f"   - Total searches: {total_searches}")
        logger.info(f"   - 💾 AUTO-SAVE: Every {self.save_milestone} leads")
        logger.info(f"   - 🔄 RESUME: Can restart from last position")
        logger.info(f"🛡️  Duplicate filters active:")
        logger.info(f"   - {len(self.seen_emails)} previously scraped emails")
        logger.info(f"   - {len(self.seen_websites)} previously scraped websites")

        if self.current_search_index > 0:
            logger.info(f"")
            logger.info(f"🔄 RESUMING FROM PREVIOUS RUN:")
            logger.info(f"   - Starting at search #{self.current_search_index + 1}/{total_searches}")

        logger.info("")

        try:
            for idx in range(self.current_search_index, total_searches):
                self.current_search_index = idx

                term, location = all_searches[idx]
                search_key = f"{term}|{location}"

                if search_key in self.completed_searches:
                    logger.info(f"⭕ Skipping search {idx + 1}/{total_searches}: {term} in {location} (already done)")
                    continue

                if idx > 0 and idx % 50 == 0:
                    logger.info(f"🔄 Restarting browser to prevent memory issues (search {idx + 1})")
                    try:
                        self.driver.quit()
                    except:
                        pass
                    time.sleep(3)
                    self.setup_selenium()

                logger.info(f"🔍 Search {idx + 1}/{total_searches}: {term} in {location}")

                try:
                    leads = self.search_google_maps(term, location, max_results=60)

                    self.all_leads.extend(leads)

                    self.completed_searches.add(search_key)

                    logger.info(f"   Progress: {len(self.all_leads)} total verified leads | {len(leads)} added this batch")

                    self.save_progress_state()
                    self.save_progress(after_each_search=True)
                    self.save_progress()

                except Exception as e:
                    logger.error(f"❌ Search failed: {e}")
                    logger.info(f"🔄 Attempting to restart browser...")
                    try:
                        self.driver.quit()
                    except:
                        pass
                    time.sleep(3)
                    self.setup_selenium()
                    continue

                time.sleep(random.uniform(3, 7))

        finally:
            logger.info("")
            logger.info("🔒 Finalizing and saving all data...")
            self.save_progress(force=True)
            self.cleanup()

        if self.all_leads:
            self.save_results()
        else:
            logger.warning("⚠️  No new leads found (all were duplicates)")

        logger.info("=" * 70)
        logger.info(f"✅ SCRAPING COMPLETE: {len(self.all_leads)} VERIFIED leads")
        logger.info(f"📊 Scraping Statistics:")
        logger.info(f"   ✅ Verified emails (saved): {self.email_stats['verified']}")
        logger.info(f"   ⭕ Unverified emails (skipped): {self.email_stats['unverified']}")
        logger.info(f"   ⭕ No website/email (skipped): {self.email_stats['none']}")
        logger.info("=" * 70)

    def cleanup(self):
        """Close browser."""
        if self.driver:
            logger.info("🧹 Closing browser...")
            try:
                self.driver.quit()
            except:
                pass

    def save_results(self):
        """Save results to JSON."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"data/raw_leads_{timestamp}.json"

        Path(filename).parent.mkdir(parents=True, exist_ok=True)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.all_leads, f, indent=2, ensure_ascii=False)

        logger.info(f"💾 Saved to: {filename}")


def main():
    """Test the scraper."""
    scraper = CarpentryLeadScraper()
    scraper.run_full_scrape()

    print(f"\n✅ Scraped {len(scraper.all_leads)} leads")

    if scraper.all_leads:
        print("\n📋 Sample lead:")
        print(json.dumps(scraper.all_leads[0], indent=2))


if __name__ == "__main__":
    main()