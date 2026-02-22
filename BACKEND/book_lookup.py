"""
Book identification via Open Library API (free, no API key).
Resolves/corrects title and author so many books are stored with consistent, canonical metadata.
"""
import re
import requests
from typing import Dict, Optional, Tuple

OPENLIBRARY_SEARCH = "https://openlibrary.org/search.json"
REQUEST_TIMEOUT = 8


def _normalize_isbn(isbn: str) -> Optional[str]:
    """Extract digits only from ISBN (10 or 13)."""
    if not isbn or not isinstance(isbn, str):
        return None
    digits = re.sub(r"\D", "", isbn.strip())
    if len(digits) == 10:
        return digits
    if len(digits) == 13:
        return digits
    if len(digits) > 13:
        return digits[:13]
    return digits if len(digits) >= 10 else None


def _clean_for_query(s: str) -> str:
    """Clean string for API query (strip, collapse spaces)."""
    if not s or not isinstance(s, str):
        return ""
    return " ".join(s.strip().split())[:200]


def lookup_by_isbn(isbn: str) -> Optional[Dict[str, str]]:
    """
    Look up book by ISBN using Open Library. Returns canonical title, author, and ISBN.
    """
    isbn_clean = _normalize_isbn(isbn)
    if not isbn_clean:
        return None
    try:
        url = f"{OPENLIBRARY_SEARCH}?isbn={isbn_clean}&limit=1"
        r = requests.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        docs = data.get("docs") or []
        if not docs:
            return None
        doc = docs[0]
        title = (doc.get("title") or "").strip()
        author_list = doc.get("author_name")
        author = ", ".join(author_list) if isinstance(author_list, list) else (author_list or "")
        isbn_return = isbn_clean
        if not title:
            return None
        return {"title": title, "author": author.strip() or "Unknown Author", "isbn": isbn_return}
    except Exception as e:
        print(f"   ⚠️ Open Library ISBN lookup failed: {e}")
        return None


def lookup_by_title_author(title: str, author: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Look up book by title (and optionally author) using Open Library.
    Returns best match: canonical title, author, and ISBN if available.
    """
    title_clean = _clean_for_query(title)
    if not title_clean:
        return None
    try:
        params = {"title": title_clean, "limit": 5}
        if author:
            params["author"] = _clean_for_query(author)
        r = requests.get(OPENLIBRARY_SEARCH, params=params, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        docs = data.get("docs") or []
        if not docs:
            return None
        # Prefer first result (best relevance)
        doc = docs[0]
        canonical_title = (doc.get("title") or "").strip()
        author_list = doc.get("author_name")
        canonical_author = ", ".join(author_list) if isinstance(author_list, list) else (author_list or "")
        isbns = doc.get("isbn")
        isbn = isbns[0] if isinstance(isbns, list) and isbns else (isbns or "")
        if not canonical_title:
            return None
        return {
            "title": canonical_title,
            "author": (canonical_author or "Unknown Author").strip(),
            "isbn": isbn if isinstance(isbn, str) else "",
        }
    except Exception as e:
        print(f"   ⚠️ Open Library title/author lookup failed: {e}")
        return None


def identify_book(
    title: str,
    author: str,
    isbn: Optional[str] = None,
) -> Tuple[str, str, Optional[str]]:
    """
    Identify book using Open Library: return (resolved_title, resolved_author, isbn_or_none).
    If lookup fails, returns (title, author, None) as-is (normalized).
    """
    title = (title or "").strip()
    author = (author or "").strip()
    if not title:
        return ("Book (Unknown)", author or "Unknown Author", None)

    # 1) If we have ISBN, try that first (most reliable)
    if isbn:
        result = lookup_by_isbn(isbn)
        if result:
            print(f"   📚 Identified by ISBN: '{result['title']}' by {result['author']}")
            return (
                result["title"],
                result["author"],
                result.get("isbn"),
            )

    # 2) Try title + author
    result = lookup_by_title_author(title, author if author and author.lower() != "unknown author" else None)
    if result:
        print(f"   📚 Identified by title/author: '{result['title']}' by {result['author']}")
        isbn_out = result.get("isbn") or None
        if isbn_out:
            return result["title"], result["author"], isbn_out
        return result["title"], result["author"], None

    # 3) Fallback: return cleaned input
    return (
        title or "Book (Unknown)",
        author or "Unknown Author",
        _normalize_isbn(isbn) if isbn else None,
    )
