#!/usr/bin/env python3
"""
CORS Connection Checker
=======================
Simulates a browser request from the frontend to verify CORS is configured correctly.

Usage:
    python scripts/check_connection.py [backend_url] [frontend_origin]

Examples:
    # Check production
    python scripts/check_connection.py https://grand-learning-production-bc96.up.railway.app https://frontend-production-a7cf.up.railway.app

    # Check local
    python scripts/check_connection.py http://localhost:8000 http://localhost:3000
"""

import sys
import requests
from urllib.parse import urlparse


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'


def check_cors(backend_url: str, frontend_origin: str) -> bool:
    """
    Simulate a CORS preflight request and actual request from frontend origin.
    Returns True if CORS is properly configured.
    """
    print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}CORS Connection Check{Colors.END}")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}")
    print(f"\n{Colors.BLUE}Backend URL:{Colors.END}    {backend_url}")
    print(f"{Colors.BLUE}Frontend Origin:{Colors.END} {frontend_origin}")

    health_url = f"{backend_url.rstrip('/')}/health"
    all_passed = True

    # ==========================================================================
    # Test 1: Basic Health Check (no CORS headers)
    # ==========================================================================
    print(f"\n{Colors.YELLOW}[Test 1] Basic Health Check{Colors.END}")
    try:
        resp = requests.get(health_url, timeout=10)
        if resp.status_code == 200:
            print(f"  {Colors.GREEN}✅ Backend is reachable{Colors.END}")
            print(f"  Response: {resp.json()}")
        else:
            print(f"  {Colors.RED}❌ Backend returned {resp.status_code}{Colors.END}")
            all_passed = False
    except requests.RequestException as e:
        print(f"  {Colors.RED}❌ Cannot reach backend: {e}{Colors.END}")
        return False

    # ==========================================================================
    # Test 2: CORS Preflight (OPTIONS request)
    # ==========================================================================
    print(f"\n{Colors.YELLOW}[Test 2] CORS Preflight (OPTIONS){Colors.END}")
    preflight_headers = {
        "Origin": frontend_origin,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type, Authorization",
    }

    try:
        resp = requests.options(health_url, headers=preflight_headers, timeout=10)
        cors_origin = resp.headers.get("Access-Control-Allow-Origin", "")
        cors_methods = resp.headers.get("Access-Control-Allow-Methods", "")
        cors_headers = resp.headers.get("Access-Control-Allow-Headers", "")
        cors_credentials = resp.headers.get("Access-Control-Allow-Credentials", "")

        print(f"  Status: {resp.status_code}")
        print(f"  Access-Control-Allow-Origin: {cors_origin or '(not set)'}")
        print(f"  Access-Control-Allow-Methods: {cors_methods or '(not set)'}")
        print(f"  Access-Control-Allow-Headers: {cors_headers or '(not set)'}")
        print(f"  Access-Control-Allow-Credentials: {cors_credentials or '(not set)'}")

        # Check if origin is allowed
        origin_ok = cors_origin == frontend_origin or cors_origin == "*"
        if origin_ok:
            print(f"  {Colors.GREEN}✅ Origin is allowed{Colors.END}")
        else:
            print(f"  {Colors.RED}❌ Origin NOT allowed!{Colors.END}")
            print(f"     Expected: {frontend_origin}")
            print(f"     Got: {cors_origin}")
            all_passed = False

    except requests.RequestException as e:
        print(f"  {Colors.RED}❌ Preflight request failed: {e}{Colors.END}")
        all_passed = False

    # ==========================================================================
    # Test 3: Actual Request with Origin header
    # ==========================================================================
    print(f"\n{Colors.YELLOW}[Test 3] Actual Request with Origin{Colors.END}")
    request_headers = {
        "Origin": frontend_origin,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(health_url, headers=request_headers, timeout=10)
        cors_origin = resp.headers.get("Access-Control-Allow-Origin", "")

        print(f"  Status: {resp.status_code}")
        print(f"  Access-Control-Allow-Origin: {cors_origin or '(not set)'}")

        if resp.status_code == 200 and (cors_origin == frontend_origin or cors_origin == "*"):
            print(f"  {Colors.GREEN}✅ Request succeeded with CORS headers{Colors.END}")
        else:
            print(f"  {Colors.RED}❌ CORS headers missing or incorrect{Colors.END}")
            all_passed = False

    except requests.RequestException as e:
        print(f"  {Colors.RED}❌ Request failed: {e}{Colors.END}")
        all_passed = False

    # ==========================================================================
    # Summary
    # ==========================================================================
    print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
    if all_passed:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ ALL CHECKS PASSED - CORS is configured correctly!{Colors.END}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ SOME CHECKS FAILED - Review CORS configuration{Colors.END}")
        print(f"\n{Colors.YELLOW}Troubleshooting:{Colors.END}")
        print("  1. Check ALLOWED_ORIGINS in backend/main.py")
        print("  2. Ensure the frontend origin matches exactly (including https://)")
        print("  3. Redeploy the backend after changes")
    print(f"{Colors.CYAN}{'='*60}{Colors.END}\n")

    return all_passed


def main():
    # Default URLs
    backend_url = "https://grand-learning-production-bc96.up.railway.app"
    frontend_origin = "https://frontend-production-a7cf.up.railway.app"

    # Override from command line
    if len(sys.argv) >= 2:
        backend_url = sys.argv[1]
    if len(sys.argv) >= 3:
        frontend_origin = sys.argv[2]

    # Validate URLs
    for name, url in [("Backend", backend_url), ("Frontend", frontend_origin)]:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            print(f"{Colors.RED}Invalid {name} URL: {url}{Colors.END}")
            print("URL must include scheme (http:// or https://)")
            sys.exit(1)

    success = check_cors(backend_url, frontend_origin)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
