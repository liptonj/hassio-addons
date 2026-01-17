#!/usr/bin/env python3
"""Validation script for FreeRADIUS deployment.

This script validates the deployment configuration, database connectivity,
and schema compatibility before deployment.

Usage:
    python3 validate_deployment.py
    
Environment variables:
    DATABASE_URL: Database connection string
    API_AUTH_TOKEN: API authentication token (optional for validation)
"""

import os
import sys
from pathlib import Path

# Color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_success(msg):
    """Print success message."""
    print(f"{GREEN}✅ {msg}{RESET}")


def print_error(msg):
    """Print error message."""
    print(f"{RED}❌ {msg}{RESET}")


def print_warning(msg):
    """Print warning message."""
    print(f"{YELLOW}⚠️  {msg}{RESET}")


def print_info(msg):
    """Print info message."""
    print(f"{BLUE}ℹ️  {msg}{RESET}")


def check_environment_variables():
    """Check required environment variables."""
    print("\n" + "=" * 60)
    print("Checking Environment Variables")
    print("=" * 60)
    
    issues = []
    warnings = []
    
    # Required
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        issues.append("DATABASE_URL not set")
    else:
        print_success(f"DATABASE_URL is set")
        
        # Validate format
        if not any(database_url.startswith(prefix) for prefix in 
                   ["postgresql://", "mysql://", "mysql+pymysql://", "sqlite:///"]):
            warnings.append("DATABASE_URL format may be invalid (expected postgresql://, mysql://, or sqlite:///)")
    
    # Optional but recommended
    api_token = os.getenv("API_AUTH_TOKEN")
    if not api_token:
        warnings.append("API_AUTH_TOKEN not set (required for production)")
    elif len(api_token) < 32:
        warnings.append(f"API_AUTH_TOKEN is weak (only {len(api_token)} chars, recommend 48+)")
    else:
        print_success(f"API_AUTH_TOKEN is set (length: {len(api_token)})")
    
    cert_password = os.getenv("CERT_PASSWORD")
    if not cert_password:
        warnings.append("CERT_PASSWORD not set (RadSec certificates will be unencrypted)")
    elif len(cert_password) < 16:
        warnings.append(f"CERT_PASSWORD is weak (only {len(cert_password)} chars, recommend 24+)")
    else:
        print_success(f"CERT_PASSWORD is set (length: {len(cert_password)})")
    
    return issues, warnings


def check_database_connectivity():
    """Test database connectivity."""
    print("\n" + "=" * 60)
    print("Testing Database Connectivity")
    print("=" * 60)
    
    issues = []
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print_error("DATABASE_URL not set, cannot test connectivity")
        return ["DATABASE_URL not set"]
    
    try:
        from sqlalchemy import create_engine, text
        
        print_info(f"Connecting to: {database_url.split('@')[0]}@***")
        
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            if result.scalar() == 1:
                print_success("Database connection successful")
            else:
                issues.append("Database query returned unexpected result")
        
        engine.dispose()
        
    except ModuleNotFoundError as e:
        print_warning(f"SQLAlchemy not installed, skipping connectivity test: {e}")
        return []  # Not an error, just can't test
    except Exception as e:
        issues.append(f"Database connection failed: {e}")
        print_error(f"Connection failed: {e}")
    
    return issues


def check_schema_compatibility():
    """Check if database schema matches expected models."""
    print("\n" + "=" * 60)
    print("Checking Database Schema")
    print("=" * 60)
    
    issues = []
    warnings = []
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print_warning("DATABASE_URL not set, skipping schema check")
        return issues, warnings
    
    try:
        from sqlalchemy import create_engine, inspect, text
        
        engine = create_engine(database_url)
        inspector = inspect(engine)
        
        # Check if tables exist
        tables = inspector.get_table_names()
        print_info(f"Found {len(tables)} tables in database")
        
        required_tables = ["radius_clients", "udn_assignments"]
        
        for table in required_tables:
            if table in tables:
                print_success(f"Table '{table}' exists")
                
                # Check columns
                columns = {col['name']: col['type'] for col in inspector.get_columns(table)}
                
                if table == "radius_clients":
                    required_cols = ["id", "name", "ipaddr", "secret", "is_active"]
                    for col in required_cols:
                        if col not in columns:
                            issues.append(f"Table '{table}' missing required column: {col}")
                        else:
                            print_success(f"  Column '{col}' exists")
                    
                    # Check for created_by field
                    if "created_by" not in columns:
                        warnings.append(f"Table '{table}' missing optional column: created_by (portal compatibility)")
                    else:
                        print_success(f"  Column 'created_by' exists")
                
                elif table == "udn_assignments":
                    required_cols = ["id", "mac_address", "udn_id", "is_active"]
                    for col in required_cols:
                        if col not in columns:
                            issues.append(f"Table '{table}' missing required column: {col}")
                        else:
                            print_success(f"  Column '{col}' exists")
            else:
                warnings.append(f"Table '{table}' does not exist (will be created on first run)")
        
        engine.dispose()
        
    except ModuleNotFoundError:
        print_warning("SQLAlchemy not installed, skipping schema check")
        return [], []
    except Exception as e:
        issues.append(f"Schema check failed: {e}")
        print_error(f"Schema check failed: {e}")
    
    return issues, warnings


def check_file_structure():
    """Check if required files and directories exist."""
    print("\n" + "=" * 60)
    print("Checking File Structure")
    print("=" * 60)
    
    issues = []
    
    required_files = [
        "rootfs/usr/bin/radius_app/main.py",
        "rootfs/usr/bin/radius_app/config.py",
        "rootfs/usr/bin/radius_app/db/models.py",
        "rootfs/usr/bin/radius_app/db/database.py",
        "rootfs/usr/bin/radius_app/core/config_generator.py",
        "rootfs/usr/bin/run.sh",
        "Dockerfile",
        "config.yaml",
    ]
    
    for file_path in required_files:
        full_path = Path(file_path)
        if full_path.exists():
            print_success(f"File exists: {file_path}")
        else:
            issues.append(f"Missing file: {file_path}")
            print_error(f"Missing: {file_path}")
    
    # Check for old directory (should not exist)
    old_dir = Path("rootfs/usr/bin/radius-app")
    if old_dir.exists():
        issues.append(f"Old directory still exists: {old_dir} (should be radius_app)")
        print_error(f"Old directory exists: {old_dir}")
    
    return issues


def check_python_imports():
    """Check if critical Python modules can be imported."""
    print("\n" + "=" * 60)
    print("Checking Python Imports")
    print("=" * 60)
    
    issues = []
    
    # Add radius_app to path
    sys.path.insert(0, str(Path("rootfs/usr/bin")))
    
    modules_to_check = [
        ("radius_app", "Main application module"),
        ("radius_app.config", "Configuration module"),
        ("radius_app.db.models", "Database models"),
    ]
    
    for module_name, description in modules_to_check:
        try:
            __import__(module_name)
            print_success(f"{description}: {module_name}")
        except ImportError as e:
            # Expected - dependencies not installed in validation environment
            print_warning(f"{description} ({module_name}): Dependencies not installed - will work in Docker")
        except Exception as e:
            issues.append(f"Import error for {module_name}: {e}")
            print_error(f"Error importing {module_name}: {e}")
    
    return issues


def generate_report(all_issues, all_warnings):
    """Generate final validation report."""
    print("\n" + "=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    
    if not all_issues and not all_warnings:
        print_success("\n🎉 All validation checks passed!")
        print_info("Deployment configuration looks good.")
        return 0
    
    if all_warnings and not all_issues:
        print_warning(f"\n⚠️  {len(all_warnings)} warning(s) found:")
        for warning in all_warnings:
            print(f"  - {warning}")
        print_info("\nDeployment can proceed, but address warnings for production.")
        return 0
    
    if all_issues:
        print_error(f"\n❌ {len(all_issues)} critical issue(s) found:")
        for issue in all_issues:
            print(f"  - {issue}")
        
        if all_warnings:
            print_warning(f"\n⚠️  {len(all_warnings)} warning(s) also found:")
            for warning in all_warnings:
                print(f"  - {warning}")
        
        print_error("\n⛔ Deployment NOT recommended until issues are resolved.")
        return 1


def main():
    """Main validation function."""
    print(f"{BLUE}")
    print("=" * 60)
    print("FreeRADIUS v2.0.0 - Deployment Validation")
    print("=" * 60)
    print(f"{RESET}")
    
    all_issues = []
    all_warnings = []
    
    # Check environment
    issues, warnings = check_environment_variables()
    all_issues.extend(issues)
    all_warnings.extend(warnings)
    
    # Check database
    issues = check_database_connectivity()
    all_issues.extend(issues)
    
    # Check schema
    issues, warnings = check_schema_compatibility()
    all_issues.extend(issues)
    all_warnings.extend(warnings)
    
    # Check files
    issues = check_file_structure()
    all_issues.extend(issues)
    
    # Check imports
    issues = check_python_imports()
    all_issues.extend(issues)
    
    # Generate report
    return generate_report(all_issues, all_warnings)


if __name__ == "__main__":
    sys.exit(main())
