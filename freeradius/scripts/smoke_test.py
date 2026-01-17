#!/usr/bin/env python3
"""Smoke test script for FreeRADIUS deployment.

Runs basic smoke tests to verify the deployment is functional.

Usage:
    python3 smoke_test.py [--api-url URL] [--api-token TOKEN]
    
Arguments:
    --api-url: FreeRADIUS API URL (default: http://localhost:8000)
    --api-token: API authentication token (from environment if not provided)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ requests module not installed. Install with: pip install requests")
    sys.exit(1)

# Color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_test(name):
    """Print test name."""
    print(f"\n{BLUE}► {name}{RESET}")


def print_pass(msg):
    """Print pass message."""
    print(f"{GREEN}  ✅ {msg}{RESET}")


def print_fail(msg):
    """Print fail message."""
    print(f"{RED}  ❌ {msg}{RESET}")


def test_health_endpoint(api_url):
    """Test health endpoint (no auth required)."""
    print_test("Test 1: Health Endpoint (No Auth)")
    
    try:
        response = requests.get(f"{api_url}/health", timeout=10)
        
        if response.status_code != 200:
            print_fail(f"Health check failed with status {response.status_code}")
            return False
        
        data = response.json()
        
        # Check response structure
        required_fields = ["status", "timestamp", "radius_running", 
                          "portal_db_connected", "config_files_exist"]
        
        for field in required_fields:
            if field not in data:
                print_fail(f"Missing field in health response: {field}")
                return False
        
        print_pass(f"Status: {data['status']}")
        print_pass(f"RADIUS running: {data['radius_running']}")
        print_pass(f"Database connected: {data['portal_db_connected']}")
        print_pass(f"Config files exist: {data['config_files_exist']}")
        
        if data['status'] == 'healthy':
            print_pass("Health check PASSED")
            return True
        else:
            print_fail(f"System not healthy: {data['status']}")
            return False
            
    except requests.RequestException as e:
        print_fail(f"Health check request failed: {e}")
        return False
    except json.JSONDecodeError:
        print_fail("Health check returned invalid JSON")
        return False


def test_auth_required(api_url):
    """Test that protected endpoints require authentication."""
    print_test("Test 2: Authentication Required")
    
    try:
        # Try without auth
        response = requests.post(
            f"{api_url}/api/reload",
            json={"force": False},
            timeout=5
        )
        
        if response.status_code == 401:
            print_pass("Endpoint correctly requires authentication")
            return True
        else:
            print_fail(f"Endpoint returned {response.status_code}, expected 401")
            return False
            
    except requests.RequestException as e:
        print_fail(f"Request failed: {e}")
        return False


def test_invalid_token_rejected(api_url):
    """Test that invalid tokens are rejected."""
    print_test("Test 3: Invalid Token Rejected")
    
    try:
        response = requests.post(
            f"{api_url}/api/reload",
            json={"force": False},
            headers={"Authorization": "Bearer invalid-token-12345"},
            timeout=5
        )
        
        if response.status_code == 401:
            print_pass("Invalid token correctly rejected")
            return True
        else:
            print_fail(f"Invalid token returned {response.status_code}, expected 401")
            return False
            
    except requests.RequestException as e:
        print_fail(f"Request failed: {e}")
        return False


def test_config_status(api_url, api_token):
    """Test config status endpoint."""
    print_test("Test 4: Config Status (Authenticated)")
    
    if not api_token:
        print_fail("API token not provided, skipping authenticated tests")
        return False
    
    try:
        response = requests.get(
            f"{api_url}/api/config/status",
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=5
        )
        
        if response.status_code != 200:
            print_fail(f"Config status failed with status {response.status_code}")
            if response.status_code == 401:
                print_fail("Authentication failed - check API_AUTH_TOKEN")
            return False
        
        data = response.json()
        
        print_pass(f"Clients count: {data.get('clients_count', 0)}")
        print_pass(f"Assignments count: {data.get('assignments_count', 0)}")
        print_pass(f"Status: {data.get('status', 'unknown')}")
        
        return True
        
    except requests.RequestException as e:
        print_fail(f"Request failed: {e}")
        return False


def test_config_reload(api_url, api_token):
    """Test config reload endpoint."""
    print_test("Test 5: Config Reload (Authenticated)")
    
    if not api_token:
        print_fail("API token not provided, skipping")
        return False
    
    try:
        response = requests.post(
            f"{api_url}/api/reload",
            json={"force": True},
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=30
        )
        
        if response.status_code != 200:
            print_fail(f"Config reload failed with status {response.status_code}")
            return False
        
        data = response.json()
        
        if not data.get('success'):
            print_fail(f"Reload failed: {data.get('message', 'Unknown error')}")
            return False
        
        print_pass(f"Reload successful: {data.get('message')}")
        print_pass(f"Clients regenerated: {data.get('clients_regenerated', False)}")
        print_pass(f"Users regenerated: {data.get('users_regenerated', False)}")
        print_pass(f"RADIUS reloaded: {data.get('reloaded', False)}")
        
        return True
        
    except requests.RequestException as e:
        print_fail(f"Request failed: {e}")
        return False


def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="FreeRADIUS smoke tests")
    parser.add_argument("--api-url", default="http://localhost:8000",
                       help="FreeRADIUS API URL")
    parser.add_argument("--api-token", default=os.getenv("API_AUTH_TOKEN"),
                       help="API authentication token")
    
    args = parser.parse_args()
    
    print(f"{BLUE}")
    print("=" * 60)
    print("FreeRADIUS v2.0.0 - Smoke Tests")
    print("=" * 60)
    print(f"{RESET}")
    print(f"API URL: {args.api_url}")
    print(f"API Token: {'***' + args.api_token[-8:] if args.api_token else 'Not provided'}")
    
    results = []
    
    # Run tests
    results.append(("Health Endpoint", test_health_endpoint(args.api_url)))
    results.append(("Auth Required", test_auth_required(args.api_url)))
    results.append(("Invalid Token Rejected", test_invalid_token_rejected(args.api_url)))
    results.append(("Config Status", test_config_status(args.api_url, args.api_token)))
    results.append(("Config Reload", test_config_reload(args.api_url, args.api_token)))
    
    # Summary
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}TEST SUMMARY{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = f"{GREEN}✅ PASS{RESET}" if result else f"{RED}❌ FAIL{RESET}"
        print(f"{name:30s} {status}")
    
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    
    if passed == total:
        print(f"{GREEN}🎉 All {total} tests PASSED!{RESET}")
        return 0
    else:
        print(f"{RED}❌ {total - passed} of {total} tests FAILED{RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
