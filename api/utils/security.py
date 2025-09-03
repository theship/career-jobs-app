"""
Security utilities for input validation and sanitization
Protects against malicious file uploads, injections, and other attacks
"""

import io
import os
import re
import hashlib
import logging
from typing import BinaryIO, Optional, Tuple
from pathlib import Path

import magic
import pikepdf
import bleach
import pandas as pd
from fastapi import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# File upload limits
MAX_PDF_SIZE = 10 * 1024 * 1024  # 10MB
MAX_CSV_SIZE = 5 * 1024 * 1024   # 5MB
MAX_TEXT_SIZE = 1 * 1024 * 1024  # 1MB
MAX_CSV_ROWS = 10000
MAX_CSV_COLUMNS = 100

# Allowed file extensions and MIME types
ALLOWED_PDF_EXTENSIONS = {'.pdf'}
ALLOWED_PDF_MIMETYPES = {'application/pdf'}

ALLOWED_CSV_EXTENSIONS = {'.csv', '.txt'}
ALLOWED_CSV_MIMETYPES = {'text/csv', 'text/plain', 'application/csv'}

# Rate limiter for upload endpoints
limiter = Limiter(key_func=get_remote_address)


class FileSecurityError(HTTPException):
    """Custom exception for file security issues"""
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and other attacks
    
    Args:
        filename: Original filename from user
        
    Returns:
        Sanitized filename safe for storage
    """
    if not filename:
        raise FileSecurityError("Filename is required")
    
    # Remove any path components to prevent traversal
    filename = os.path.basename(filename)
    
    # Remove leading dots to prevent hidden files
    filename = filename.lstrip('.')
    
    # Allow only safe characters (alphanumeric, dots, underscores, hyphens)
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Ensure filename isn't empty after sanitization
    if not filename or filename == '_':
        filename = 'document'
    
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 100:
        name = name[:100]
    filename = name + ext
    
    return filename


def validate_pdf(file_content: bytes, filename: str) -> Tuple[bytes, str]:
    """
    Validate and sanitize PDF file
    
    Args:
        file_content: Raw PDF bytes
        filename: Original filename
        
    Returns:
        Tuple of (sanitized_content, safe_filename)
        
    Raises:
        FileSecurityError: If file is invalid or malicious
    """
    # Check size
    if len(file_content) > MAX_PDF_SIZE:
        raise FileSecurityError(f"PDF file too large. Maximum size is {MAX_PDF_SIZE // 1024 // 1024}MB")
    
    # Verify file extension
    safe_filename = sanitize_filename(filename)
    ext = os.path.splitext(safe_filename)[1].lower()
    if ext not in ALLOWED_PDF_EXTENSIONS:
        raise FileSecurityError(f"Invalid file extension. Only PDF files are allowed")
    
    # Verify MIME type using python-magic
    try:
        mime = magic.from_buffer(file_content, mime=True)
        if mime not in ALLOWED_PDF_MIMETYPES:
            raise FileSecurityError(f"Invalid file type. Detected: {mime}")
    except Exception as e:
        logger.error(f"Error checking MIME type: {e}")
        raise FileSecurityError("Could not verify file type")
    
    # Sanitize PDF using pikepdf (removes JavaScript, forms, embedded files)
    try:
        with pikepdf.open(io.BytesIO(file_content)) as pdf:
            # Remove potentially malicious elements
            sanitized = io.BytesIO()
            
            # Save with linearization (web optimization) and compression
            # This strips out JavaScript, forms, and other potentially dangerous elements
            pdf.save(
                sanitized, 
                linearize=True, 
                compress_streams=True,
                # Remove interactive elements
                preserve_pdfa=False,
                object_stream_mode=pikepdf.ObjectStreamMode.generate
            )
            
            # Get the sanitized content
            sanitized_content = sanitized.getvalue()
            
            # Verify the sanitized PDF is still valid
            if len(sanitized_content) == 0:
                raise FileSecurityError("PDF sanitization failed - empty result")
            
            logger.info(f"PDF sanitized: {len(file_content)} -> {len(sanitized_content)} bytes")
            
            return sanitized_content, safe_filename
            
    except pikepdf.PdfError as e:
        logger.error(f"Invalid PDF file: {e}")
        raise FileSecurityError("Invalid or corrupted PDF file")
    except Exception as e:
        logger.error(f"Error sanitizing PDF: {e}")
        raise FileSecurityError("Could not process PDF file")


def validate_csv(file_content: bytes, filename: str) -> Tuple[pd.DataFrame, str]:
    """
    Validate and sanitize CSV file
    
    Args:
        file_content: Raw CSV bytes
        filename: Original filename
        
    Returns:
        Tuple of (sanitized_dataframe, safe_filename)
        
    Raises:
        FileSecurityError: If file is invalid or malicious
    """
    # Check size
    if len(file_content) > MAX_CSV_SIZE:
        raise FileSecurityError(f"CSV file too large. Maximum size is {MAX_CSV_SIZE // 1024 // 1024}MB")
    
    # Verify file extension
    safe_filename = sanitize_filename(filename)
    ext = os.path.splitext(safe_filename)[1].lower()
    if ext not in ALLOWED_CSV_EXTENSIONS:
        raise FileSecurityError(f"Invalid file extension. Only CSV/TXT files are allowed")
    
    try:
        # Decode content
        content = file_content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            content = file_content.decode('latin-1')
        except UnicodeDecodeError:
            raise FileSecurityError("Could not decode CSV file. Please ensure it's a valid text file")
    
    # Remove potential formula injections (Excel formulas that start with =, +, -, @)
    # These could execute commands when opened in Excel
    content = re.sub(r'^[=+\-@]', '', content, flags=re.MULTILINE)
    
    # Remove null bytes that could cause issues
    content = content.replace('\x00', '')
    
    try:
        # Parse CSV with limits
        df = pd.read_csv(
            io.StringIO(content),
            nrows=MAX_CSV_ROWS,      # Limit rows
            dtype=str,               # Force all columns to string to prevent type injection
            na_filter=False,         # Don't interpret values as NaN
            engine='python',         # Use Python engine for better error handling
            on_bad_lines='skip'      # Skip malformed lines
        )
        
        # Check column count
        if len(df.columns) > MAX_CSV_COLUMNS:
            raise FileSecurityError(f"Too many columns. Maximum is {MAX_CSV_COLUMNS}")
        
        # Sanitize all cell contents
        for col in df.columns:
            df[col] = df[col].apply(lambda x: sanitize_text(str(x)) if pd.notna(x) else '')
        
        # Sanitize column names
        df.columns = [sanitize_text(str(col))[:100] for col in df.columns]
        
        logger.info(f"CSV validated: {len(df)} rows, {len(df.columns)} columns")
        
        return df, safe_filename
        
    except pd.errors.ParserError as e:
        logger.error(f"CSV parsing error: {e}")
        raise FileSecurityError("Invalid CSV format")
    except Exception as e:
        logger.error(f"Error processing CSV: {e}")
        raise FileSecurityError("Could not process CSV file")


def sanitize_text(text: str, max_length: int = 10000) -> str:
    """
    Sanitize text input to prevent XSS and injection attacks
    
    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text safe for storage and display
    """
    if not text:
        return ""
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length]
    
    # Remove any HTML tags and JavaScript
    text = bleach.clean(text, tags=[], strip=True)
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text


def sanitize_json_input(data: dict) -> dict:
    """
    Recursively sanitize all string values in a JSON/dict input
    
    Args:
        data: Dictionary to sanitize
        
    Returns:
        Sanitized dictionary
    """
    if isinstance(data, dict):
        return {k: sanitize_json_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json_input(item) for item in data]
    elif isinstance(data, str):
        return sanitize_text(data)
    else:
        return data


def calculate_file_hash(file_content: bytes) -> str:
    """
    Calculate SHA256 hash of file content
    
    Args:
        file_content: File bytes
        
    Returns:
        Hex string of SHA256 hash
    """
    return hashlib.sha256(file_content).hexdigest()


def validate_url(url: str) -> str:
    """
    Validate and sanitize URL
    
    Args:
        url: URL string to validate
        
    Returns:
        Sanitized URL
        
    Raises:
        FileSecurityError: If URL is invalid
    """
    if not url:
        raise FileSecurityError("URL is required")
    
    # Basic URL validation
    url = url.strip()
    
    # Ensure URL has a scheme
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Validate URL format
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )
    
    if not url_pattern.match(url):
        raise FileSecurityError("Invalid URL format")
    
    # Prevent SSRF attacks - block internal IPs and local addresses
    blocked_patterns = [
        r'^https?://127\.',
        r'^https?://192\.168\.',
        r'^https?://10\.',
        r'^https?://172\.(1[6-9]|2[0-9]|3[0-1])\.',
        r'^https?://localhost',
        r'^https?://0\.0\.0\.0'
    ]
    
    for pattern in blocked_patterns:
        if re.match(pattern, url, re.IGNORECASE):
            raise FileSecurityError("Internal URLs are not allowed")
    
    return url


def get_safe_content_type(filename: str) -> str:
    """
    Get safe content type for file based on extension
    
    Args:
        filename: Filename to check
        
    Returns:
        Safe content type string
    """
    ext = os.path.splitext(filename)[1].lower()
    
    content_types = {
        '.pdf': 'application/pdf',
        '.csv': 'text/csv',
        '.txt': 'text/plain',
        '.json': 'application/json'
    }
    
    return content_types.get(ext, 'application/octet-stream')