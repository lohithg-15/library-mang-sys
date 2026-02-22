from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import sys
import traceback
import threading
from typing import Optional

# Add BACKEND directory to path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from ocr import extract_text_from_image, extract_book_fields, extract_book_fields_with_gemini, _get_easyocr_reader, _is_likely_author_names, GEMINI_API_KEY
from database import create_table, insert_book, search_books, search_books_fuzzy, get_all_books, delete_all_books
from book_lookup import identify_book
from auth import (
    create_users_table, login_user, register_user, verify_token, 
    get_user_by_id, list_all_users, ROLE_SHOPKEEPER, ROLE_CUSTOMER
)

app = FastAPI()

# Enable CORS to allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploads"
BACKEND_READY = {"ocr": False, "database": False, "auth": False}

# Dependency: Get current user from token
async def get_current_user(authorization: Optional[str] = Header(None)):
    """Extract and verify user from Bearer token"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return payload


async def get_shopkeeper_user(current_user: dict = Depends(get_current_user)):
    """Ensure user is a shopkeeper"""
    if current_user.get("role") != ROLE_SHOPKEEPER:
        raise HTTPException(status_code=403, detail="Shopkeeper access required")
    return current_user


@app.on_event("startup")
def startup():
    """Initialize database and upload folder on startup"""
    print("\n" + "="*60)
    print("🚀 SMART BOOK FINDER - BACKEND STARTUP")
    print("="*60)
    
    # Initialize books table
    create_table()
    BACKEND_READY["database"] = True
    print("✅ Database initialized")
    
    # Initialize users table
    create_users_table()
    BACKEND_READY["auth"] = True
    print("✅ Authentication initialized")
    
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        print(f"✅ Upload folder created at: {UPLOAD_FOLDER}")
    
    # Initialize EasyOCR in background (takes 3-5 mins on first run)
    print("\n⏳ Initializing EasyOCR (this may take 3-5 minutes on first run)...")
    print("   Don't worry, this only happens once!")
    print("   You can start uploading books once this completes.\n")
    
    def init_ocr():
        try:
            _get_easyocr_reader()
            BACKEND_READY["ocr"] = True
            print("✅ EasyOCR ready! Backend is fully initialized.\n")
        except Exception as e:
            print(f"⚠️ EasyOCR initialization warning: {e}")
            print("   System will use Tesseract fallback if available.\n")
            BACKEND_READY["ocr"] = True  # Mark ready even if warning
    
    # Run OCR init in background so backend responds immediately
    ocr_thread = threading.Thread(target=init_ocr, daemon=True)
    ocr_thread.start()
    
    print("="*60 + "\n")

@app.get("/")
def home():
    return {"message": "Book Finder Backend running", "version": "2.0", "features": ["authentication", "role-based-access"]}

@app.get("/status/")
def status():
    """Check backend readiness"""
    return {
        "backend_running": True,
        "database_ready": BACKEND_READY["database"],
        "auth_ready": BACKEND_READY["auth"],
        "ocr_ready": BACKEND_READY["ocr"],
        "status": "ready" if all(BACKEND_READY.values()) else "initializing",
        "message": "All systems ready!" if all(BACKEND_READY.values()) else "Initializing..."
    }

# ======================== AUTHENTICATION ENDPOINTS ========================

@app.post("/auth/register/")
def register(username: str = Form(...), password: str = Form(...), role: str = Form(default=ROLE_CUSTOMER)):
    """Register a new user (customer or shopkeeper)"""
    result = register_user(username, password, role)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@app.post("/auth/login/")
def login(username: str = Form(...), password: str = Form(...)):
    """Login endpoint - returns JWT token"""
    result = login_user(username, password)
    
    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("error", "Login failed"))
    
    return result


@app.get("/auth/me/")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user info"""
    user = get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/auth/logout/")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout endpoint (frontend will delete token)"""
    return {
        "message": "Logged out successfully",
        "status": "success"
    }

# ======================== BOOK UPLOAD (SHOPKEEPER ONLY) ========================

@app.post("/upload-book/")
async def upload_book(
    image: UploadFile = File(...),
    quantity: int = Form(...),
    shelf: str = Form(...),
    shopkeeper: dict = Depends(get_shopkeeper_user)
):
    """Upload book - SHOPKEEPER ONLY"""
    try:
        print(f"\n{'='*70}")
        print(f"📤 BOOK UPLOAD - Started by: {shopkeeper['username']}")
        print(f"{'='*70}")
        
        image_path = os.path.join(UPLOAD_FOLDER, image.filename)
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        print(f"✅ Image saved: {image_path}")

        # ============ GEMINI-POWERED EXTRACTION (PRIMARY) ============
        print(f"\n🤖 EXTRACTION PHASE 1: Gemini AI Analysis (ChatGPT-level accuracy)")
        if GEMINI_API_KEY:
            print(f"   Using advanced AI vision model for accurate extraction...")
        else:
            print(f"   ⚠️ GEMINI_API_KEY not set - using OCR fallback")
            print(f"   💡 For best accuracy like ChatGPT, set GEMINI_API_KEY in .env file")
        gemini_result = extract_book_fields_with_gemini(image_path)
        
        extraction_method = "unknown"
        title = "Unknown"
        author = "Unknown"
        
        if gemini_result and gemini_result.get("title") and gemini_result.get("title").lower() != "unknown":
            # Gemini extraction successful
            title = gemini_result.get("title", "Unknown").strip()
            author = gemini_result.get("author", "Unknown").strip()
            extraction_method = "gemini"
            
            print(f"\n   ✅ GEMINI SUCCESS!")
            print(f"   Title:     {title}")
            print(f"   Author:    {author}")
            print(f"   Publisher: {gemini_result.get('publisher', 'N/A')}")
            print(f"   Subtitle:  {gemini_result.get('subtitle', 'N/A')}")
            
            ocr_debug = {
                "method": "gemini",
                "publisher": gemini_result.get("publisher", ""),
                "isbn": gemini_result.get("isbn", ""),
                "subtitle": gemini_result.get("subtitle", ""),
                "confidence": gemini_result.get("confidence", "unknown")
            }
        else:
            # Fallback to OCR + improved heuristic
            print(f"\n⚠️ EXTRACTION PHASE 2: OCR + Heuristic Analysis")
            print(f"   Gemini failed/unavailable, using OCR extraction...")
            
            text, ocr_debug = extract_text_from_image(image_path)
            print(f"   ✅ OCR extracted {len(text)} characters from image")
            
            fields = extract_book_fields(text)
            title = fields.get("title", "Unknown").strip()
            author = fields.get("author", "Unknown").strip()
            extraction_method = "ocr_heuristic"
            
            print(f"   Title:  {title}")
            print(f"   Author: {author}")
            print(f"   Method: {fields.get('extraction_method', 'unknown')}")

        # ============ VALIDATION & CORRECTION ============
        print(f"\n✅ VALIDATION")
        
        # Check if title and author might be swapped (author names in title field)
        if _is_likely_author_names(title) and not _is_likely_author_names(author):
            print(f"   ⚠️ Detected possible title/author swap, correcting...")
            title, author = author, title
            print(f"   🔄 Swapped: Title='{title}', Author='{author}'")
        
        # Final validation
        if not title or title.lower() == "unknown" or len(title.strip()) < 3:
            title = "Book (OCR Failed)"
            print(f"   ⚠️ Title is invalid, using fallback: {title}")
        if not author or author.lower() == "unknown" or len(author.strip()) < 3:
            author = "Unknown Author"
            print(f"   ⚠️ Author is invalid, using fallback: {author}")
        
        # Clean up any remaining issues
        title = title.strip()
        author = author.strip().replace("$", "S")  # Fix OCR errors in author
        
        print(f"   Final Title:  {title}")
        print(f"   Final Author: {author}")

        # ============ BOOK IDENTIFICATION (Open Library) ============
        isbn_from_extraction = None
        if gemini_result and gemini_result.get("isbn") and str(gemini_result.get("isbn", "")).lower() not in ("unknown", ""):
            isbn_from_extraction = str(gemini_result.get("isbn", "")).strip()
        print(f"\n📚 BOOK IDENTIFICATION (for consistent metadata with many books)")
        title, author, isbn_saved = identify_book(title, author, isbn_from_extraction)

        # ============ DATABASE SAVE ============
        print(f"\n💾 DATABASE SAVE")
        print(f"   Quantity: {quantity}, Shelf: {shelf}")
        insert_book(title, author, quantity, shelf, isbn=isbn_saved)
        print(f"   ✅ Successfully inserted into database")
        print(f"\n{'='*70}\n")

        return {
            "message": "Book uploaded successfully",
            "title": title,
            "author": author,
            "quantity": quantity,
            "shelf": shelf,
            "uploaded_by": shopkeeper['username'],
            "extraction_method": extraction_method,
            "ocr_debug": ocr_debug
        }
    except Exception as e:
        print(f"❌ Upload error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ======================== BOOK SEARCH (PUBLIC - ANYONE CAN SEARCH) ========================

@app.get("/search-book/")
def search_book(query: str):
    """Search for books by title or author. Uses partial match first, then fuzzy (typo-tolerant) if no results."""
    try:
        # Validate input
        if not query or query.strip() == "":
            return {
                "count": 0,
                "books": [],
                "error": "Query cannot be empty",
                "status": "error"
            }

        print(f"\n🔍 Search query: '{query}'")
        results = search_books(query)

        # If no results from partial match, try fuzzy (typo-tolerant) search
        did_you_mean = None
        if not results:
            fuzzy_results, suggested = search_books_fuzzy(query)
            if fuzzy_results:
                results = fuzzy_results
                did_you_mean = suggested  # e.g. "Harry Potter" for query "Harry Poter"

        books = []
        for r in results:
            books.append({
                "title": r[0] if r[0] else "Unknown",
                "author": r[1] if r[1] else "Unknown",
                "quantity": r[2] if r[2] else 0,
                "shelf": r[3] if r[3] else "N/A"
            })

        print(f"✅ Found {len(books)} book(s) for query '{query}'\n")

        out = {
            "count": len(books),
            "books": books,
            "status": "success" if len(books) > 0 else "not_found",
            "query": query
        }
        if did_you_mean is not None:
            out["did_you_mean"] = did_you_mean
        return out
    except Exception as e:
        print(f"❌ Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


# ======================== DEBUG ENDPOINTS (SHOPKEEPER ONLY) ========================

@app.get("/debug/all-books/")
async def debug_all_books(shopkeeper: dict = Depends(get_shopkeeper_user)):
    """Debug: See all books in database - SHOPKEEPER ONLY"""
    try:
        books = get_all_books()
        return {
            "total_books": len(books),
            "accessed_by": shopkeeper['username'],
            "books": [
                {
                    "title": b[0],
                    "author": b[1],
                    "quantity": b[2],
                    "shelf": b[3]
                } for b in books
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/debug/reset-database/")
async def reset_database(shopkeeper: dict = Depends(get_shopkeeper_user)):
    """Debug: Reset database - SHOPKEEPER ONLY"""
    try:
        delete_all_books()
        print(f"⚠️ Database reset by {shopkeeper['username']}")
        return {
            "message": "✅ Database reset successfully",
            "reset_by": shopkeeper['username'],
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug/list-users/")
async def list_users(shopkeeper: dict = Depends(get_shopkeeper_user)):
    """Debug: List all users - SHOPKEEPER ONLY"""
    users = list_all_users()
    return {
        "total_users": len(users),
        "accessed_by": shopkeeper['username'],
        "users": users
    }

