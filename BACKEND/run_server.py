#!/usr/bin/env python3
"""
Server runner script that suppresses deprecation warnings and runs the FastAPI server
"""
import warnings
import sys

# Suppress deprecation warnings for cleaner output
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Now import and run the main app
if __name__ == "__main__":
    import uvicorn
    from main import app
    
    print("\n" + "="*60)
    print("🚀 SMART BOOK FINDER - STARTING BACKEND")
    print("="*60 + "\n")
    
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=True
    )
