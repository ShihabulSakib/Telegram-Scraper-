#!/usr/bin/env python3
"""
Link Downloader for Telegram Tools Unified
Downloads external content (YouTube, Google Drive) with parallel support.

FIXES (v5 - final):
  - Dropped gdown entirely. It fails on many public files because Google
    changed their download flow and gdown hasn't kept up.
  - Now uses a pure `requests` two-step approach that matches what a real
    browser does:
      Step 1: GET docs.google.com/uc?export=download&id=FILE_ID
      Step 2: If we get an HTML warning page (large file / virus scan),
              parse the hidden form fields and follow to
              drive.usercontent.google.com/download with those params.
  - Filename resolved from Content-Disposition header (real name with ext).
  - Folder listing uses Drive API v3 — works for any public folder.
  - All downloaded files are verified: HTML pages saved as PDFs are
    detected and deleted immediately.

REQUIREMENTS:
  pip install requests beautifulsoup4 yt-dlp
  (tqdm optional for progress bars)
"""

import os
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


# ── caption helpers ────────────────────────────────────────────────────────────

def _clean_caption(caption: str, fallback: str = "") -> str:
    """Extract the first meaningful line from a Telegram caption as a title."""
    if not caption:
        return fallback
    for line in caption.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r'https?://', line):
            continue
        if line.startswith('@'):
            continue
        if re.match(r'(main|paid)\s+channel', line, re.IGNORECASE):
            continue
        return line
    return fallback


def _sanitize(text: str, max_length: int = 120) -> str:
    """Make a string safe for use as a file/folder name."""
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', text)
    safe = safe.strip('. ')
    safe = re.sub(r'\s+', ' ', safe)
    return safe[:max_length] or 'file'


# ── Drive URL helpers ──────────────────────────────────────────────────────────

def _extract_drive_file_id(url: str) -> Optional[str]:
    if '/file/d/' in url:
        return url.split('/file/d/')[1].split('/')[0].split('?')[0]
    parsed = urlparse(url)
    return parse_qs(parsed.query).get('id', [None])[0]


def _extract_drive_folder_id(url: str) -> Optional[str]:
    if '/folders/' in url:
        return url.split('/folders/')[1].split('/')[0].split('?')[0]
    parsed = urlparse(url)
    return parse_qs(parsed.query).get('id', [None])[0]


def _is_folder_url(url: str) -> bool:
    return '/folders/' in url


# ── file integrity ─────────────────────────────────────────────────────────────

def _is_html_content(path: Path) -> bool:
    """Return True if the file is actually an HTML page (corrupt download)."""
    try:
        with open(path, 'rb') as f:
            header = f.read(64).lstrip()
        return header.startswith(b'<')
    except Exception:
        return False


def _filename_from_headers(headers: dict, fallback: str) -> str:
    """Extract real filename from Content-Disposition header."""
    cd = headers.get('Content-Disposition', '')
    # RFC 5987 encoded name takes priority
    m = re.search(r"filename\*=UTF-8''(.+)", cd, re.IGNORECASE)
    if m:
        from urllib.parse import unquote
        return _sanitize(unquote(m.group(1)))
    m = re.search(r'filename="?([^";]+)"?', cd, re.IGNORECASE)
    if m:
        return _sanitize(m.group(1).strip())
    return fallback


# ── core Drive file download ───────────────────────────────────────────────────

def _download_drive_file_to(
    session: requests.Session,
    file_id: str,
    dest_dir: Path,
    preferred_name: str,
) -> Tuple[bool, str]:
    """
    Download a single Google Drive file using the modern two-step request flow.

    Step 1 — Initial request to docs.google.com/uc?export=download&id=FILE_ID
    Step 2 — If Google returns an HTML confirmation page (virus scan warning),
              parse the hidden form and follow the real download URL at
              drive.usercontent.google.com/download

    Returns (success, final_filename_or_error_message).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    HEADERS = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
    }

    # ── Step 1 ─────────────────────────────────────────────────────────────────
    step1_url = 'https://docs.google.com/uc'
    try:
        resp = session.get(
            step1_url,
            params={'export': 'download', 'id': file_id},
            headers=HEADERS,
            stream=True,
            timeout=60,
        )
    except Exception as e:
        return False, f"Network error (step 1): {e}"

    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code} on initial request"

    content_type = resp.headers.get('Content-Type', '')

    # ── Step 2 — HTML confirmation page? ───────────────────────────────────────
    if 'text/html' in content_type or 'Content-Disposition' not in resp.headers:
        # Parse the confirmation form from the HTML
        try:
            html = resp.content.decode('utf-8', errors='replace')
        except Exception:
            return False, "Could not decode response HTML"

        soup = BeautifulSoup(html, 'html.parser')
        form = soup.find('form', {'id': 'download-form'})

        if form and form.get('action'):
            # Collect all hidden input fields (confirm, uuid, etc.)
            action_url = form['action']
            params = {}
            for inp in form.find_all('input', {'type': 'hidden'}):
                name  = inp.get('name')
                value = inp.get('value', '')
                if name:
                    params[name] = value

            try:
                resp = session.get(
                    action_url,
                    params=params,
                    headers=HEADERS,
                    stream=True,
                    timeout=120,
                )
            except Exception as e:
                return False, f"Network error (step 2 form): {e}"

        else:
            # Fallback: look for a confirm token in cookies or HTML text
            token = None
            for k, v in resp.cookies.items():
                if k.startswith('download_warning'):
                    token = v
                    break

            if not token:
                m = re.search(r'confirm=([0-9A-Za-z\-_]+)', html)
                if m:
                    token = m.group(1)

            if not token:
                return False, (
                    "Could not find download confirmation token. "
                    "File may be private or require a Google account."
                )

            try:
                resp = session.get(
                    step1_url,
                    params={'export': 'download', 'id': file_id, 'confirm': token},
                    headers=HEADERS,
                    stream=True,
                    timeout=120,
                )
            except Exception as e:
                return False, f"Network error (step 2 token): {e}"

    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code} on download request"

    # Sanity check — still HTML?
    ct = resp.headers.get('Content-Type', '')
    if 'text/html' in ct:
        return False, (
            "Still getting HTML after confirmation — "
            "file may be private or quota exceeded."
        )

    # ── resolve filename ───────────────────────────────────────────────────────
    filename = _filename_from_headers(resp.headers, preferred_name)
    dest_path = dest_dir / filename

    # Skip if already downloaded and non-empty
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return True, f"Already exists: {filename}"

    # ── stream to disk ─────────────────────────────────────────────────────────
    tmp_path = dest_dir / f'.tmp_{file_id}'
    try:
        with open(tmp_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        tmp_path.unlink(missing_ok=True)
        return False, f"Write error: {e}"

    # ── integrity check ────────────────────────────────────────────────────────
    if _is_html_content(tmp_path):
        tmp_path.unlink(missing_ok=True)
        return False, "Downloaded file is an HTML page — file is likely private."

    if tmp_path.stat().st_size == 0:
        tmp_path.unlink(missing_ok=True)
        return False, "Downloaded file is empty."

    tmp_path.rename(dest_path)
    return True, f"Saved as: {filename}"


# ── folder listing ─────────────────────────────────────────────────────────────

def _list_folder_files(folder_id: str) -> Tuple[List[Dict], str]:
    """
    List files in a public Google Drive folder using the Drive API v3.
    No API key required for folders shared as 'Anyone with the link'.
    """
    files: List[Dict] = []
    page_token: Optional[str] = None
    base_url = "https://www.googleapis.com/drive/v3/files"
    params = {
        "q": f"'{folder_id}' in parents and trashed = false",
        "fields": "nextPageToken, files(id, name, mimeType)",
        "pageSize": 100,
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }

    session = requests.Session()
    while True:
        if page_token:
            params["pageToken"] = page_token
        try:
            resp = session.get(base_url, params=params, timeout=30)
        except Exception as e:
            return files, f"Network error listing folder: {e}"

        if resp.status_code == 403:
            return files, (
                "HTTP 403 — folder is private. "
                "Set sharing to 'Anyone with the link can view'."
            )
        if resp.status_code != 200:
            return files, f"Drive API HTTP {resp.status_code}: {resp.text[:200]}"

        data = resp.json()
        files.extend(data.get("files", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    if not files:
        return [], "Folder is empty or access is restricted."
    return files, ""


# ── main class ─────────────────────────────────────────────────────────────────

class LinkDownloader:
    """Download external content (YouTube / Google Drive) with parallel support."""

    def __init__(self, data_manager, config, workers: int = 4):
        self.data_manager = data_manager
        self.config = config
        self.workers = workers

        self.output_dir  = Path(config.download_path)
        self.youtube_dir = self.output_dir / 'youtube'
        self.drive_dir   = self.output_dir / 'drive'

        self.youtube_dir.mkdir(parents=True, exist_ok=True)
        self.drive_dir.mkdir(parents=True, exist_ok=True)

    # ── YouTube ────────────────────────────────────────────────────────────────

    def download_youtube(self, url: str, caption: str) -> Tuple[bool, str]:
        if not yt_dlp:
            return False, "yt-dlp not installed — run: pip install yt-dlp"
        try:
            title = _sanitize(_clean_caption(caption) or 'video')
            ydl_opts = {
                'format': 'best[height<=1080]',
                'outtmpl': str(self.youtube_dir / f'{title}_%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True, "Success"
        except Exception as e:
            return False, str(e)[:120]

    # ── Google Drive — individual file ─────────────────────────────────────────

    def download_drive_file(self, url: str, caption: str) -> Tuple[bool, str]:
        file_id = _extract_drive_file_id(url)
        if not file_id:
            return False, "Could not extract file ID from URL"

        preferred_name = _sanitize(_clean_caption(caption, fallback=f'drive_{file_id}'))
        session = requests.Session()
        return _download_drive_file_to(session, file_id, self.drive_dir, preferred_name)

    # ── Google Drive — folder ──────────────────────────────────────────────────

    def download_drive_folder(self, url: str, caption: str) -> Tuple[bool, str]:
        folder_id = _extract_drive_folder_id(url)
        if not folder_id:
            return False, "Could not extract folder ID from URL"

        folder_title     = _clean_caption(caption, fallback=f'folder_{folder_id}')
        safe_folder_name = _sanitize(folder_title)
        folder_path      = self.drive_dir / safe_folder_name
        folder_path.mkdir(parents=True, exist_ok=True)

        print(f"    📁 Listing files in: {safe_folder_name}")
        files, err = _list_folder_files(folder_id)
        if not files:
            return False, err or "No files found in folder"

        print(f"    📂 {len(files)} file(s) found")
        session = requests.Session()
        success_count = 0
        fail_count = 0

        for i, f in enumerate(files, 1):
            preferred = _sanitize(f['name'])
            print(f"    [{i}/{len(files)}] ⬇️  {preferred}")
            ok, msg = _download_drive_file_to(session, f['id'], folder_path, preferred)
            if ok:
                print(f"    [{i}/{len(files)}] ✅ {msg}")
                success_count += 1
            else:
                print(f"    [{i}/{len(files)}] ❌ {msg}")
                fail_count += 1
            time.sleep(0.3)

        if success_count == 0:
            return False, f"All {fail_count} file(s) failed — folder may be private"

        result = f"Downloaded {success_count}/{len(files)} file(s) → {folder_path}"
        if fail_count:
            result += f" ({fail_count} failed)"
        return True, result

    # ── dispatcher ─────────────────────────────────────────────────────────────

    def download_single_link(
        self, link: Dict, index: int, total: int
    ) -> Tuple[Dict, bool, str]:
        url       = link['url']
        link_type = link['type']
        caption   = link.get('caption', '')

        print(f"[{index}/{total}] ⬇️  {link_type.upper()}: {url[:70]}")
        time.sleep(0.1)

        if link_type == 'youtube':
            success, msg = self.download_youtube(url, caption)
        elif link_type == 'drive':
            if _is_folder_url(url):
                success, msg = self.download_drive_folder(url, caption)
            else:
                success, msg = self.download_drive_file(url, caption)
        else:
            success, msg = False, f"Unsupported link type: {link_type}"

        print(f"[{index}/{total}] {'✅' if success else '❌'} {msg[:80]}")
        return link, success, msg

    # ── batch ──────────────────────────────────────────────────────────────────

    def download_batch(self, links: List[Dict]):
        if not links:
            print("No links to download")
            return

        folder_links = [l for l in links if l['type'] == 'drive' and _is_folder_url(l['url'])]
        file_links   = [l for l in links if not (l['type'] == 'drive' and _is_folder_url(l['url']))]

        total      = len(links)
        results    = {'success': 0, 'failed': 0, 'errors': []}
        start_time = time.time()

        print(f"\n{'='*70}")
        print(f"🚀 Starting download: {total} link(s)  ({len(folder_links)} folder(s), {len(file_links)} file(s))")
        print(f"   Workers for individual files: {self.workers}")
        print(f"{'='*70}\n")

        if folder_links:
            print(f"📁 Processing {len(folder_links)} folder link(s) sequentially...\n")
            for i, link in enumerate(folder_links, 1):
                link, success, msg = self.download_single_link(link, i, len(folder_links))
                self.data_manager.mark_link_downloaded(link, success)
                if success:
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({'url': link['url'], 'error': msg})

        if file_links:
            print(f"\n⚡ Processing {len(file_links)} file link(s) in parallel...\n")
            offset = len(folder_links)
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = {
                    executor.submit(self.download_single_link, link, offset + i + 1, total): link
                    for i, link in enumerate(file_links)
                }
                for future in as_completed(futures):
                    link, success, msg = future.result()
                    self.data_manager.mark_link_downloaded(link, success)
                    if success:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append({'url': link['url'], 'error': msg})

        elapsed = time.time() - start_time
        avg     = elapsed / total if total else 0

        print(f"\n{'='*70}")
        print(f"📊 DOWNLOAD SUMMARY")
        print(f"{'='*70}")
        print(f"  Total:        {total}")
        print(f"  ✓ Success:    {results['success']}  ({results['success']/total*100:.1f}%)")
        print(f"  ✗ Failed:     {results['failed']}  ({results['failed']/total*100:.1f}%)")
        print(f"  ⏱  Time:      {elapsed:.1f}s  (avg {avg:.1f}s/link)")
        print(f"{'='*70}")

        if results['errors']:
            print(f"\n❌ Failed links:")
            for err in results['errors'][:10]:
                print(f"  • {err['url'][:70]}")
                print(f"    {err['error'][:80]}")
            if len(results['errors']) > 10:
                print(f"  ... and {len(results['errors']) - 10} more")
        print()
