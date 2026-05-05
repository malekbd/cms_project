#!/usr/bin/env python3
"""Test deployment fixes"""
import os
import sys
import subprocess

# Apply security patch at module level
try:
    from cms_project.security_patch import *
    SECURITY_PATCH_LOADED = True
except ImportError:
    SECURITY_PATCH_LOADED = False

def test_security_patch():
    """Test that security patch works"""
    print("Testing security patch...")
    if not SECURITY_PATCH_LOADED:
        print("✗ Security patch failed to load")
        return False
    
    print("✓ Security patch imported successfully")
    
    # Try to simulate Django model loading
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cms_project.settings')
    try:
        import django
        django.setup()
        print("✓ Django setup completed without ForeignKey error")
        return True
    except Exception as e:
        print(f"✗ Django setup failed: {e}")
        return False

def test_database_connection():
    """Test database connection"""
    print("\nTesting database connection...")
    try:
        result = subprocess.run(
            [sys.executable, 'manage.py', 'check', '--database', 'default'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print("✓ Database connection check passed")
            return True
        else:
            print(f"✗ Database connection check failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ Database check timed out")
        return False
    except Exception as e:
        print(f"✗ Error running database check: {e}")
        return False

def test_deploy_script_syntax():
    """Test deploy.sh syntax"""
    print("\nTesting deploy.sh syntax...")
    try:
        result = subprocess.run(
            ['bash', '-n', 'deploy.sh'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ deploy.sh syntax is valid")
            return True
        else:
            print(f"✗ deploy.sh syntax error: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Error checking deploy.sh: {e}")
        return False

def main():
    print("=== Testing Deployment Fixes ===")
    
    all_passed = True
    
    # Test 1: Security patch
    if not test_security_patch():
        all_passed = False
    
    # Test 2: Database connection
    if not test_database_connection():
        all_passed = False
    
    # Test 3: Deploy script syntax
    if not test_deploy_script_syntax():
        all_passed = False
    
    print("\n=== Summary ===")
    if all_passed:
        print("✓ All tests passed! Deployment fixes are ready.")
        return 0
    else:
        print("✗ Some tests failed. Review the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())