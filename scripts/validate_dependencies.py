#!/usr/bin/env python3
"""
Validate all required dependencies are available and configured
Exit with error if any critical dependencies are missing
"""

import os
import sys
from typing import Tuple


def check_env_var(name: str, required: bool = True) -> Tuple[bool, str]:
    """Check if environment variable is set"""
    value = os.getenv(name)
    if value:
        # Mask sensitive values for display
        if "KEY" in name or "SECRET" in name:
            display = f"{value[:8]}..." if len(value) > 8 else "***"
        else:
            display = value
        return True, display
    elif required:
        return False, "NOT SET (REQUIRED)"
    else:
        return True, "NOT SET (optional)"


def check_redis() -> Tuple[bool, str]:
    """Check Redis connection"""
    try:
        import redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = redis.from_url(redis_url)
        client.ping()

        # Get Redis info
        info = client.info("server")
        version = info.get("redis_version", "unknown")

        return True, f"Connected (v{version})"
    except ImportError:
        return False, "Redis package not installed"
    except Exception as e:
        return False, f"Connection failed: {e}"


def check_supabase() -> Tuple[bool, str]:
    """Check Supabase configuration"""
    try:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not url or not key:
            return False, "Missing URL or service key"

        # Try to import and create client
        from supabase import create_client

        client = create_client(url, key)

        # Test connection with a simple query
        client.table("app_user").select("user_id").limit(1).execute()

        return True, f"Connected to {url.split('.')[0].split('//')[1]}"
    except ImportError:
        return False, "Supabase package not installed"
    except Exception as e:
        error_msg = str(e)
        if "relation" in error_msg:
            return True, "Connected (tables not migrated)"
        return False, f"Connection failed: {error_msg[:50]}"


def check_openai() -> Tuple[bool, str]:
    """Check OpenAI API configuration"""
    try:
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            return False, "API key not set"

        if not api_key.startswith("sk-"):
            return False, "Invalid API key format"

        # We can't test the actual connection without making an API call
        # which costs money, so just validate the format
        return True, f"Configured ({api_key[:7]}...)"
    except Exception as e:
        return False, f"Check failed: {e}"


def main():
    """Run all validation checks"""
    print("=" * 60)
    print("Career Jobs App - Dependency Validation")
    print("=" * 60)

    all_checks_passed = True

    # Environment variables
    print("\n📋 Environment Variables:")
    print("-" * 40)

    env_checks = [
        ("SUPABASE_URL", True),
        ("SUPABASE_SERVICE_ROLE_KEY", True),
        ("OPENAI_API_KEY", True),
        ("REDIS_URL", True),
        ("HMAC_SECRET", False),
        ("WANDB_API_KEY", False),
        ("ANTHROPIC_API_KEY", False),
    ]

    for var_name, required in env_checks:
        success, message = check_env_var(var_name, required)
        status = "✅" if success else "❌"
        print(f"{status} {var_name:30} {message}")
        if not success and required:
            all_checks_passed = False

    # Service connections
    print("\n🔌 Service Connections:")
    print("-" * 40)

    # Redis (REQUIRED)
    success, message = check_redis()
    status = "✅" if success else "❌"
    print(f"{status} Redis:                         {message}")
    if not success:
        all_checks_passed = False
        print("\n  ⚠️  Redis is REQUIRED for security features!")
        print("  Install: brew install redis (macOS) or apt-get install redis-server")
        print("  Start:   redis-server or docker run -d -p 6379:6379 redis:7-alpine")

    # Supabase (REQUIRED)
    success, message = check_supabase()
    status = "✅" if success else "❌"
    print(f"{status} Supabase:                      {message}")
    if not success:
        all_checks_passed = False
        print("\n  ⚠️  Supabase is REQUIRED for database operations!")
        print("  1. Create project at https://supabase.com")
        print("  2. Copy URL and service role key to .env")

    # OpenAI (REQUIRED for full functionality)
    success, message = check_openai()
    status = "✅" if success else "❌"
    print(f"{status} OpenAI:                        {message}")
    if not success:
        print("\n  ⚠️  OpenAI API key needed for embeddings and AI features")
        print("  Get key at https://platform.openai.com/api-keys")

    # Python packages
    print("\n📦 Python Packages:")
    print("-" * 40)

    required_packages = [
        "fastapi",
        "uvicorn",
        "redis",
        "supabase",
        "openai",
        "pdfminer",
        "pydantic",
        "httpx",
        "jwt",
    ]

    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package:30} Installed")
        except ImportError:
            print(f"❌ {package:30} NOT INSTALLED")
            all_checks_passed = False

    # Summary
    print("\n" + "=" * 60)
    if all_checks_passed:
        print("✅ All critical dependencies are configured!")
        print("\nYou can start the application with:")
        print("  python -m uvicorn api.main:app --reload")
        return 0
    else:
        print("❌ Some critical dependencies are missing!")
        print("\nPlease:")
        print("1. Install missing packages: pip install -r requirements.txt")
        print("2. Start Redis: redis-server")
        print("3. Configure environment variables in .env")
        return 1


if __name__ == "__main__":
    # Load .env file if it exists
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        print("Warning: python-dotenv not installed, using system environment only")

    sys.exit(main())
