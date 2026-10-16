"""
api/index.py - Vercel Serverless Function Entry Point for SpendSmart
===================================================================
Exposes the Flask WSGI `app` object for Vercel Python Runtime.
"""

import os
import sys

# Ensure the project root directory is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app
