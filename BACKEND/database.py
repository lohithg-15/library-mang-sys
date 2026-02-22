import sqlite3
import os
import difflib

# Use absolute path for database in the backend directory
DB_PATH = os.path.join(os.path.dirname(__file__), "books.db")

def get_connection():
    """Get database connection with proper settings for concurrent access"""
    conn = sqlite3.connect(DB_PATH, timeout=5.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    """Create books table if it doesn't exist"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Drop old table if exists (for fresh start if needed)
        # cursor.execute("DROP TABLE IF EXISTS books")
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            shelf TEXT NOT NULL,
            isbn TEXT
        )
        """)
        # Add isbn column if table already existed without it
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN isbn TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        # Indexes for fast search when many books
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_title ON books(LOWER(title))")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_author ON books(LOWER(author))")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn)")
        conn.commit()
        conn.close()
        print(f"✅ Database initialized at: {DB_PATH}")
        return True
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False

def insert_book(title, author, quantity, shelf, isbn=None):
    """Insert a new book into the database. isbn is optional (for identification)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO books (title, author, quantity, shelf, isbn)
        VALUES (?, ?, ?, ?, ?)
        """, (title, author, quantity, shelf, isbn))
        conn.commit()
        conn.close()
        print(f"✅ Book saved: '{title}' by '{author}' (Qty: {quantity}, Shelf: {shelf})")
        return True
    except Exception as e:
        print(f"❌ Error inserting book: {e}")
        return False

def search_books(keyword):
    """Search for books by title or author (partial match with LIKE)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Use case-insensitive partial match
        query = """
        SELECT title, author, quantity, shelf
        FROM books
        WHERE LOWER(title) LIKE LOWER(?) OR LOWER(author) LIKE LOWER(?)
        ORDER BY title ASC
        """
        cursor.execute(query, (f"%{keyword}%", f"%{keyword}%"))
        results = cursor.fetchall()
        conn.close()
        
        print(f"✅ Search '{keyword}' returned {len(results)} results")
        return results
    except Exception as e:
        print(f"❌ Error searching books: {e}")
        return []


# Minimum similarity ratio for fuzzy match (0.0–1.0). 0.5 = typo-tolerant, 0.6 = stricter
FUZZY_CUTOFF = 0.5


def search_books_fuzzy(keyword):
    """
    Typo-tolerant (fuzzy) search using difflib (built-in, no extra install).
    Scores each book by best match of query against title or author.
    Returns (list of rows, suggested_match_string or None).
    """
    if not keyword or not str(keyword).strip():
        return [], None
    keyword = str(keyword).strip().lower()
    books = get_all_books()
    if not books:
        return [], None
    scored = []
    for row in books:
        title = (row[0] or "").strip()
        author = (row[1] or "").strip()
        title_l, author_l = title.lower(), author.lower()
        r_title = difflib.SequenceMatcher(None, keyword, title_l).ratio()
        r_author = difflib.SequenceMatcher(None, keyword, author_l).ratio()
        score = max(r_title, r_author)
        scored.append((score, row))
    scored.sort(key=lambda x: -x[0])
    results = [row for score, row in scored if score >= FUZZY_CUTOFF]
    suggested = scored[0][1][0] if scored and scored[0][0] >= FUZZY_CUTOFF else None
    if results:
        print(f"✅ Fuzzy search '{keyword}' returned {len(results)} result(s), best match: {suggested}")
    return results, suggested

def get_all_books():
    """Get all books from the database"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT title, author, quantity, shelf, isbn FROM books ORDER BY title ASC")
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"❌ Error getting all books: {e}")
        return []

def delete_all_books():
    """Delete all books from database (for testing/reset)"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM books")
        conn.commit()
        conn.close()
        print(f"✅ All books deleted from database")
        return True
    except Exception as e:
        print(f"❌ Error deleting books: {e}")
        return False
