import base64
import json
import os
from typing import Dict, List, Tuple

import cv2
import numpy as np
import pytesseract
import requests
from PIL import Image, ImageFilter, ImageOps, ImageEnhance
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Windows: allow overriding Tesseract install path via env; fall back to default
pytesseract.pytesseract.tesseract_cmd = os.getenv(
    "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

OCR_BACKEND = os.getenv("OCR_BACKEND", "easyocr").lower()  # Default to easyocr now
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize EasyOCR reader (lazy loaded on first use)
_easyocr_reader = None

def _get_easyocr_reader():
    """Lazy load EasyOCR reader on first use"""
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(['en'], gpu=False)
        except ImportError:
            raise RuntimeError(
                "EasyOCR not installed. Install with: pip install easyocr\n"
                "Or set OCR_BACKEND=tesseract to use Tesseract instead."
            )
    return _easyocr_reader


def _preprocess_image(image_path: str, upscale_factor: int = 2) -> Image.Image:
    """
    Enhanced preprocessing for better OCR accuracy:
    - Upscale image (Tesseract works better on 300+ DPI)
    - Convert to grayscale
    - Auto-contrast
    - Denoise
    - Adaptive threshold (better than hard threshold)
    - Sharpening for better text recognition
    """
    image = Image.open(image_path)
    
    # Upscale for better OCR (but don't go too large)
    max_dimension = 3000  # Max dimension to avoid memory issues
    if image.width * upscale_factor > max_dimension or image.height * upscale_factor > max_dimension:
        # Scale proportionally to fit max dimension
        scale = min(max_dimension / image.width, max_dimension / image.height)
        new_size = (int(image.width * scale), int(image.height * scale))
    else:
        new_size = (image.width * upscale_factor, image.height * upscale_factor)
    
    image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Convert to grayscale
    gray = image.convert("L")
    
    # Enhance contrast
    contrasted = ImageOps.autocontrast(gray, cutoff=2)
    
    # Apply sharpening filter for better text edges
    enhancer = ImageEnhance.Sharpness(contrasted)
    sharpened = enhancer.enhance(2.0)  # Increase sharpness
    
    # Denoise
    denoised = sharpened.filter(ImageFilter.MedianFilter(size=3))
    
    # Use numpy for adaptive thresholding
    img_array = np.array(denoised)
    # Adaptive threshold: better contrast, adjusts to image variations
    _, thresholded = cv2.threshold(img_array, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return Image.fromarray(thresholded)


def _run_tesseract(img: Image.Image, psm: int) -> str:
    config = f"--oem 3 --psm {psm}"
    return pytesseract.image_to_string(img, lang="eng", config=config)


def _extract_with_easyocr(image_path: str) -> Tuple[str, Dict]:
    """
    Use EasyOCR for extraction. More accurate than Tesseract.
    - Works offline
    - Better accuracy on real-world images
    - Can extract with confidence scores
    """
    try:
        reader = _get_easyocr_reader()
        # Extract with detail to get confidence scores
        results = reader.readtext(image_path, detail=1)
        
        # Filter by confidence (remove low confidence results)
        filtered_results = [r for r in results if len(r) >= 3 and r[2] > 0.3]  # Confidence > 30%
        
        # Extract text
        text_lines = [r[1] for r in filtered_results]
        text = "\n".join(text_lines)
        
        avg_confidence = sum(r[2] for r in filtered_results) / len(filtered_results) if filtered_results else 0
        
        debug = {
            "model": "easyocr",
            "chars": len(text),
            "lines": len(text_lines),
            "avg_confidence": round(avg_confidence, 2),
            "total_detections": len(results)
        }
        return text, debug
    except Exception as e:
        raise RuntimeError(f"EasyOCR extraction failed: {str(e)}")



def _extract_with_gemini(image_path: str) -> Tuple[str, Dict]:
    """
    Use Gemini 1.5 Flash for OCR. Falls back to raising an error if not configured.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": (
                            "Extract plain text you see on this book cover / page. "
                            "Return only the text lines."
                        )
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": b64,
                        }
                    },
                ]
            }
        ]
    }

    res = requests.post(url, json=payload, params={"key": GEMINI_API_KEY}, timeout=30)
    res.raise_for_status()
    data = res.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini OCR returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    text_parts = [p.get("text", "") for p in parts if "text" in p]
    text = "\n".join([t.strip() for t in text_parts if t.strip()])

    debug = {"model": "gemini-1.5-flash", "chars": len(text)}
    return text, debug


def _extract_with_tesseract(image_path: str) -> Tuple[str, Dict]:
    """
    Run OCR using enhanced Tesseract with multiple passes.
    Improved preprocessing and more PSM modes for better accuracy.
    """
    processed = _preprocess_image(image_path)

    # Try multiple modes for better coverage:
    # 3 = auto, 6 = uniform block, 4 = multiple columns/lines, 11 = sparse text
    passes = []
    for psm in (3, 6, 4, 11):
        try:
            text = _run_tesseract(processed, psm=psm)
            passes.append({"psm": psm, "text": text})
        except Exception:
            continue

    # Combine unique non-empty lines from all passes
    combined_lines: List[str] = []
    for p in passes:
        for line in p["text"].splitlines():
            cleaned = line.strip()
            if cleaned and len(cleaned) > 2 and cleaned not in combined_lines:
                combined_lines.append(cleaned)

    combined_text = "\n".join(combined_lines)
    debug = {
        "backend": "tesseract_enhanced",
        "passes": len(passes),
        "combined_chars": len(combined_text),
        "lines": len(combined_lines),
    }
    return combined_text, debug


def extract_text_from_image(image_path: str) -> Tuple[str, Dict]:
    """
    Choose OCR backend intelligently:
    1. OCR_BACKEND=easyocr (default, best accuracy, FREE)
    2. OCR_BACKEND=tesseract (fallback if easyocr not installed)
    3. OCR_BACKEND=gemini (if GEMINI_API_KEY set, falls back to easyocr)
    
    All backends are completely FREE.
    """
    backend = OCR_BACKEND
    
    # Try EasyOCR first (best accuracy, completely free)
    if backend in ("easyocr", "auto"):
        try:
            return _extract_with_easyocr(image_path)
        except ImportError:
            print("⚠️ EasyOCR not installed. Install with: pip install easyocr")
            print("⚠️ Falling back to Tesseract...")
            backend = "tesseract"
        except Exception as e:
            print(f"⚠️ EasyOCR failed: {e}. Trying Tesseract...")
            backend = "tesseract"
    
    # Try Tesseract if EasyOCR not available/failed
    if backend == "tesseract":
        try:
            return _extract_with_tesseract(image_path)
        except Exception as e:
            print(f"⚠️ Tesseract failed: {e}")
            if GEMINI_API_KEY:
                print("⚠️ Trying Gemini as last resort...")
                backend = "gemini"
            else:
                raise RuntimeError(
                    "All OCR backends failed. Install EasyOCR: pip install easyocr"
                )
    
    # Try Gemini if available (completely optional, free tier)
    if backend == "gemini":
        try:
            return _extract_with_gemini(image_path)
        except Exception as e:
            print(f"⚠️ Gemini failed: {e}")
            # Final fallback to Tesseract
            return _extract_with_tesseract(image_path)
    
    raise RuntimeError("No OCR backend available")


def extract_book_fields_with_gemini(image_path: str, max_retries: int = 2) -> Dict[str, str]:
    """
    Use Gemini 1.5 Pro/Flash to intelligently extract book metadata from image.
    Uses ChatGPT-level detailed analysis with step-by-step instructions.
    Tries multiple models and retries for better accuracy.
    """
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY not set, using heuristic extraction")
        return None
    
    # Try gemini-1.5-pro first (better accuracy), fallback to flash
    models_to_try = [
        "gemini-1.5-pro",
        "gemini-1.5-flash"
    ]
    
    for model_name in models_to_try:
        for attempt in range(max_retries):
            try:
                print(f"   🔄 Attempt {attempt + 1}/{max_retries} with {model_name}...")
                result = _extract_with_gemini_model(image_path, model_name)
                if result and result.get("title") and result.get("title").lower() != "unknown":
                    return result
                elif attempt < max_retries - 1:
                    print(f"   ⚠️ {model_name} returned invalid result, retrying...")
                    continue
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"   ⚠️ {model_name} timeout, retrying...")
                    continue
                print(f"   ⚠️ {model_name} timeout after {max_retries} attempts")
            except Exception as e:
                error_msg = str(e)[:100]
                print(f"   ⚠️ {model_name} failed: {error_msg}")
                if model_name == models_to_try[-1] and attempt == max_retries - 1:
                    # Last model, last attempt
                    return None
                if attempt < max_retries - 1:
                    continue
                break
    
    print("   ⚠️ All Gemini models failed or returned invalid results")
    return None


def _extract_with_gemini_model(image_path: str, model_name: str) -> Dict[str, str]:
    """Extract book fields using a specific Gemini model"""
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        
        prompt = """You are an expert book cover analyzer with exceptional attention to detail. Analyze this book cover image systematically.

STEP-BY-STEP ANALYSIS PROCESS:

STEP 1: IDENTIFY ALL TEXT ELEMENTS
- Scan the entire image carefully
- Note the position, size, and prominence of each text element
- Identify which text appears largest/most prominent
- Identify which text appears at the top/center (likely title)
- Identify which text appears at the bottom (likely author/publisher)

STEP 2: DETERMINE THE BOOK TITLE
- The TITLE is typically:
  * The LARGEST text on the cover
  * Positioned at the TOP or CENTER of the cover
  * The main name of the book
  * May include a subtitle (smaller text directly below or after the main title)
- Examples of correct titles:
  * "Bhagavad Gita"
  * "Python Programming: Beginners Guide"
  * "The Lord of the Rings"
  * "Harry Potter and the Sorcerer's Stone"
- If there's a subtitle, combine it with the main title: "Main Title: Subtitle" or "Main Title - Subtitle"
- IMPORTANT: Do NOT confuse author names with the title. Author names are usually at the bottom.

STEP 3: DETERMINE THE AUTHOR(S)
- The AUTHOR is typically:
  * Smaller text than the title
  * Positioned at the BOTTOM of the cover
  * May say "By", "Written by", "Author:", or just show names
  * Can be one or multiple authors (separated by commas, "and", or "&")
- Examples of correct authors:
  * "Vyasa" or "Ved Vyasa" (for Bhagavad Gita)
  * "J.K. Rowling"
  * "Mark Lutz, David Ascher"
  * "Sundarrajan M, Mani Deepak Choudhry"
- Extract ALL author names exactly as they appear, separated by commas
- If multiple lines contain author names, combine them

STEP 4: EXTRACT ADDITIONAL INFORMATION
- Publisher: Usually small text at bottom, may say "Published by" or show publisher logo/name
- ISBN: Usually a 10 or 13 digit number, may be labeled "ISBN"
- Subtitle: Only if it's clearly separate from the main title

STEP 5: VALIDATION
- Ensure title is NOT author names
- Ensure author is NOT the book title
- Title should be meaningful (not just "BOOK" or generic words)
- Author should be person names (not book titles)

CRITICAL: Read ALL text carefully. Do not miss any words. Extract EXACT text as it appears, but fix obvious OCR errors if you can identify them.

Return ONLY a valid JSON object with no additional text, explanations, or markdown formatting:
{
  "title": "Complete book title exactly as it appears, including subtitle if present",
  "author": "All author names exactly as they appear, separated by commas",
  "subtitle": "Subtitle only if it's clearly separate from main title, otherwise empty string",
  "publisher": "Publisher name exactly as it appears, or 'Unknown' if not visible",
  "isbn": "ISBN number exactly as it appears, or 'Unknown' if not visible",
  "confidence": "high/medium/low based on clarity of text"
}"""

        # Determine image MIME type
        img_ext = os.path.splitext(image_path)[1].lower()
        mime_type_map = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_type_map.get(img_ext, 'image/png')
        
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,  # Lower temperature for more accurate extraction
                "topK": 1,
                "topP": 0.8,
            }
        }

        print(f"   📡 Calling Gemini API ({model_name})...")
        res = requests.post(url, json=payload, params={"key": GEMINI_API_KEY}, timeout=60)
        res.raise_for_status()
        data = res.json()

        candidates = data.get("candidates", [])
        if not candidates:
            print("   ⚠️ Gemini returned no candidates")
            return None

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            print("   ⚠️ Gemini returned no parts")
            return None

        response_text = parts[0].get("text", "").strip()
        print(f"   📝 Gemini response: {response_text[:200]}...")
        
        # Try to extract JSON - handle markdown code blocks
        json_str = None
        
        # Remove markdown code blocks if present
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            if end > start:
                json_str = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            if end > start:
                json_str = response_text[start:end].strip()
        else:
            # Find JSON object
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
        
        if not json_str:
            print(f"   ⚠️ No JSON found in response")
            print(f"   Full response: {response_text[:500]}")
            return None
        
        try:
            parsed = json.loads(json_str)
            
            # Validate and clean the response
            title = (parsed.get("title") or "").strip()
            author = (parsed.get("author") or "").strip()
            subtitle = (parsed.get("subtitle") or "").strip()
            publisher = (parsed.get("publisher") or "Unknown").strip()
            isbn = (parsed.get("isbn") or "Unknown").strip()
            
            # Combine title and subtitle if subtitle exists and not already in title
            if subtitle and subtitle.lower() not in title.lower() and subtitle.lower() != "unknown":
                # Smart combination: check if subtitle should be added
                if len(subtitle) > 2:  # Valid subtitle
                    title = f"{title}: {subtitle}".strip()
            
            # Clean up author: fix common OCR errors and normalize
            if author:
                author = author.replace("$", "S")
                author = author.replace("  ", " ")  # Remove double spaces
                author = " ".join(author.split())  # Normalize whitespace
                author = author.strip()
            
            # Clean up title
            if title:
                title = " ".join(title.split())  # Normalize whitespace
                title = title.strip()
            
            # Validate title is not empty or "Unknown"
            if not title or title.lower() == "unknown" or len(title) < 2:
                print(f"   ⚠️ Gemini returned invalid/empty title: '{title}'")
                return None
            
            # Validate author - if empty, try to set a reasonable default
            if not author or author.lower() == "unknown" or len(author) < 2:
                # For some books like Bhagavad Gita, author might be "Vyasa" or similar
                # But we'll mark as Unknown Author if truly not found
                author = "Unknown Author"
            
            result = {
                "title": title,
                "author": author,
                "subtitle": subtitle,
                "publisher": publisher,
                "isbn": isbn,
                "extraction_method": f"gemini-{model_name}"
            }
            
            print(f"   ✅ Gemini ({model_name}): Title='{result['title'][:60]}', Author='{result['author'][:60]}'")
            return result
            
        except json.JSONDecodeError as e:
            print(f"   ⚠️ Failed to parse JSON: {str(e)[:100]}")
            print(f"   JSON string was: {json_str[:300]}")
            return None

    except requests.exceptions.Timeout:
        print(f"   ⚠️ Gemini API timeout")
        return None
    except requests.exceptions.RequestException as e:
        print(f"   ⚠️ Gemini API error: {str(e)[:100]}")
        return None
    except Exception as e:
        print(f"   ⚠️ Unexpected error in Gemini extraction: {str(e)[:100]}")
        return None


def _is_likely_author_names(text: str) -> bool:
    """
    Heuristic to detect if a line is likely author names rather than a title.
    Author names typically have:
    - Multiple names separated by commas
    - "AND" keyword
    - Dollar signs (from OCR errors)
    - Many capitalized words in sequence
    - Patterns like "FIRSTNAME LASTNAME, FIRSTNAME LASTNAME"
    """
    text_upper = text.upper()
    text_clean = text.strip()
    
    # Check for author-like patterns
    author_patterns = [
        text.count(',') >= 1 and len(text) > 30,  # Multiple names with comma
        ' AND ' in text_upper,  # Multiple authors with AND
        '$' in text,  # OCR artifact common in author names
        text.count(' ') >= 2 and text.count(',') >= 1,  # Multiple comma-separated names
        # Pattern: "NAME, NAME" or "NAME, NAME, NAME"
        (text.count(',') >= 1 and any(word.isupper() and len(word) > 2 for word in text.split())),
    ]
    
    return any(author_patterns)


def extract_book_fields(text: str) -> Dict[str, str]:
    """
    Improved heuristic extraction with better title/author distinction.
    Strategy:
    1. Separate lines into potential titles vs authors
    2. Title is usually: first few lines, shorter, not comma-heavy
    3. Author is usually: last few lines, comma-separated names
    4. Combine subtitle with title if adjacent
    """
    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 2]
    
    if not lines:
        return {
            "title": "Unknown",
            "author": "Unknown",
            "lines": [],
            "extraction_method": "heuristic"
        }

    # Separate author lines from potential title lines
    author_lines = []
    title_candidates = []
    
    for line in lines:
        if _is_likely_author_names(line):
            author_lines.append(line)
        else:
            title_candidates.append(line)
    
    # If no clear separation, use position-based heuristics
    # Usually: first 1-3 lines = title, last 1-2 lines = author
    if not title_candidates or not author_lines:
        # Try to identify by position
        if len(lines) >= 2:
            # First few lines are likely title
            title_candidates = lines[:min(3, len(lines)//2 + 1)]
            # Last few lines are likely author
            author_lines = lines[-min(2, len(lines)//2):]
        else:
            title_candidates = lines
            author_lines = []
    
    # Build title: combine first few title candidates (title + subtitle)
    title_parts = []
    for candidate in title_candidates[:3]:  # Max 3 lines for title
        if not _is_likely_author_names(candidate):
            title_parts.append(candidate)
    
    title = " ".join(title_parts).strip() if title_parts else "Unknown"
    
    # Clean up title: remove extra spaces, normalize
    if title and title != "Unknown":
        title = " ".join(title.split())  # Normalize whitespace
        # Limit title length
        if len(title) > 150:
            title = title[:147] + "..."
    
    # Build author: combine all author lines
    author_parts = []
    for line in author_lines:
        if _is_likely_author_names(line) or len(author_parts) == 0:
            # Clean up common OCR errors
            cleaned = line.replace("$", "S").strip()
            author_parts.append(cleaned)
    
    author = ", ".join(author_parts).strip() if author_parts else "Unknown"
    
    # If we still don't have author, try to find it in remaining lines
    if author == "Unknown" and len(lines) > len(title_candidates):
        remaining = lines[len(title_candidates):]
        for line in remaining:
            if _is_likely_author_names(line) or (line.count(',') > 0 and len(line) > 20):
                author = line.replace("$", "S").strip()
                break
    
    # Final validation
    if title == "Unknown" or len(title) < 3:
        # Fallback: use first non-author line
        for line in lines:
            if not _is_likely_author_names(line) and len(line) > 3:
                title = line
                break
    
    if author == "Unknown" or len(author) < 3:
        # Fallback: use last line if it looks like author
        if lines:
            last_line = lines[-1]
            if last_line.count(',') > 0 or len(last_line) > 20:
                author = last_line.replace("$", "S").strip()

    return {
        "title": title,
        "author": author,
        "lines": lines,
        "extraction_method": "heuristic"
    }
