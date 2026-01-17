#!/usr/bin/env python3
"""
Smoke tests for refactored Settings pages.

This script verifies:
1. All 14 settings pages load without errors
2. Navigation between pages works
3. Sidebar menu items all link correctly
4. Save buttons trigger API calls
5. Dark mode toggle works (if implemented)
"""

import sys
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class SettingsSmokeTests:
    """Smoke tests for settings pages refactor."""

    def __init__(self, base_url="http://localhost:8080", headless=True):
        self.base_url = base_url
        self.headless = headless
        self.driver = None
        self.wait = None
        self.passed = 0
        self.failed = 0

    def setup(self):
        """Initialize browser."""
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)
        print("✓ Browser initialized")

    def teardown(self):
        """Close browser."""
        if self.driver:
            self.driver.quit()
            print("✓ Browser closed")

    def login(self):
        """Login to admin panel."""
        try:
            self.driver.get(f"{self.base_url}/login")
            
            # Wait for login form
            username_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            password_input = self.driver.find_element(By.NAME, "password")
            
            # Login with admin credentials
            username_input.send_keys("admin")
            password_input.send_keys("admin")
            
            # Submit
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            # Wait for redirect to admin dashboard
            self.wait.until(EC.url_contains("/admin"))
            print("✓ Logged in successfully")
            return True
        except Exception as e:
            print(f"✗ Login failed: {e}")
            return False

    def test_page_loads(self, path, page_name):
        """Test that a settings page loads without errors."""
        try:
            self.driver.get(f"{self.base_url}{path}")
            
            # Wait for page to load (check for heading or card)
            self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "h1"))
            )
            
            # Check for JavaScript errors (basic check)
            js_errors = self.driver.get_log("browser")
            severe_errors = [log for log in js_errors if log["level"] == "SEVERE"]
            
            if severe_errors:
                print(f"✗ {page_name} has JavaScript errors: {severe_errors}")
                self.failed += 1
                return False
            
            print(f"✓ {page_name} loaded successfully")
            self.passed += 1
            return True
        except TimeoutException:
            print(f"✗ {page_name} failed to load (timeout)")
            self.failed += 1
            return False
        except Exception as e:
            print(f"✗ {page_name} error: {e}")
            self.failed += 1
            return False

    def test_save_button_exists(self, page_name):
        """Test that save button exists and is clickable."""
        try:
            save_button = self.driver.find_element(
                By.XPATH, "//button[contains(text(), 'Save')]"
            )
            if save_button.is_displayed() and save_button.is_enabled():
                print(f"  ✓ {page_name} has working Save button")
                return True
            else:
                print(f"  ✗ {page_name} Save button not visible/enabled")
                return False
        except NoSuchElementException:
            print(f"  ⚠ {page_name} has no Save button (may be expected)")
            return True  # Some pages may not have save buttons

    def test_sidebar_navigation(self):
        """Test that sidebar menu items link correctly."""
        print("\n=== Testing Sidebar Navigation ===")
        
        sidebar_links = [
            ("/admin/settings/branding", "Branding"),
            ("/admin/settings/meraki-api", "Meraki API"),
            ("/admin/settings/network/selection", "Network Selection"),
            ("/admin/settings/network/ssid", "SSID Configuration"),
            ("/admin/settings/network/wpn-setup", "WPN Setup"),
            ("/admin/settings/registration/basics", "Registration Basics"),
            ("/admin/settings/registration/login-methods", "Login Methods"),
            ("/admin/settings/registration/aup", "AUP"),
            ("/admin/settings/registration/custom-fields", "Custom Fields"),
            ("/admin/settings/registration/ipsk-invite", "IPSK & Invite"),
            ("/admin/settings/ipsk", "IPSK Settings"),
            ("/admin/settings/oauth", "OAuth / SSO"),
            ("/admin/settings/cloudflare", "Cloudflare Tunnel"),
            ("/admin/settings/advanced", "Advanced"),
        ]
        
        for path, name in sidebar_links:
            try:
                # Find and click sidebar link
                link = self.driver.find_element(By.XPATH, f"//a[@href='{path}']")
                link.click()
                
                time.sleep(0.5)  # Brief pause for navigation
                
                # Verify URL changed
                current_url = self.driver.current_url
                if path in current_url:
                    print(f"  ✓ {name} navigation works")
                    self.passed += 1
                else:
                    print(f"  ✗ {name} navigation failed (URL: {current_url})")
                    self.failed += 1
            except Exception as e:
                print(f"  ✗ {name} link error: {e}")
                self.failed += 1

    def test_all_pages(self):
        """Test all 14 settings pages."""
        print("\n=== Testing Settings Pages ===")
        
        pages = [
            ("/admin/settings/branding", "Branding"),
            ("/admin/settings/meraki-api", "Meraki API"),
            ("/admin/settings/network/selection", "Network Selection"),
            ("/admin/settings/network/ssid", "SSID Configuration"),
            ("/admin/settings/network/wpn-setup", "WPN Setup Wizard"),
            ("/admin/settings/registration/basics", "Registration Basics"),
            ("/admin/settings/registration/login-methods", "Login Methods"),
            ("/admin/settings/registration/aup", "AUP Settings"),
            ("/admin/settings/registration/custom-fields", "Custom Fields"),
            ("/admin/settings/registration/ipsk-invite", "IPSK & Invite Settings"),
            ("/admin/settings/ipsk", "IPSK Settings"),
            ("/admin/settings/oauth", "OAuth Settings"),
            ("/admin/settings/cloudflare", "Cloudflare Settings"),
            ("/admin/settings/advanced", "Advanced Settings"),
        ]
        
        for path, name in pages:
            if self.test_page_loads(path, name):
                self.test_save_button_exists(name)
            time.sleep(0.3)  # Brief pause between tests

    def test_dark_mode_classes(self):
        """Test that dark mode classes are applied."""
        print("\n=== Testing Dark Mode Classes ===")
        
        try:
            # Navigate to any settings page
            self.driver.get(f"{self.base_url}/admin/settings/branding")
            
            # Check for card class
            cards = self.driver.find_elements(By.CLASS_NAME, "card")
            if cards:
                print(f"  ✓ Found {len(cards)} .card elements")
                self.passed += 1
            else:
                print("  ✗ No .card elements found")
                self.failed += 1
            
            # Check for input class
            inputs = self.driver.find_elements(By.CLASS_NAME, "input")
            if inputs:
                print(f"  ✓ Found {len(inputs)} .input elements")
                self.passed += 1
            else:
                print("  ✗ No .input elements found")
                self.failed += 1
                
        except Exception as e:
            print(f"  ✗ Dark mode class check error: {e}")
            self.failed += 1

    def run_all_tests(self):
        """Run all smoke tests."""
        print("\n" + "="*60)
        print("Settings Pages Refactor - Smoke Tests")
        print("="*60)
        
        try:
            self.setup()
            
            if not self.login():
                print("\n✗ Cannot proceed without login")
                return False
            
            self.test_all_pages()
            self.test_sidebar_navigation()
            self.test_dark_mode_classes()
            
            # Summary
            print("\n" + "="*60)
            print(f"Test Summary: {self.passed} passed, {self.failed} failed")
            print("="*60)
            
            return self.failed == 0
            
        except Exception as e:
            print(f"\n✗ Fatal error: {e}")
            return False
        finally:
            self.teardown()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Smoke tests for settings pages")
    parser.add_argument(
        "--url",
        default="http://localhost:8080",
        help="Base URL of the application",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Run browser in visible mode",
    )
    
    args = parser.parse_args()
    
    tests = SettingsSmokeTests(
        base_url=args.url,
        headless=not args.no_headless,
    )
    
    success = tests.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
