#!/usr/bin/env python3
"""
Test script to validate CI/CD setup for CMS project.
Run this script to ensure the basic requirements are met.
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists and print status."""
    exists = os.path.exists(filepath)
    status = "[OK]" if exists else "[FAIL]"
    print(f"{status} {description}: {filepath}")
    return exists

def check_yaml_syntax(filepath):
    """Check if YAML file has valid syntax."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            yaml.safe_load(f)
        print(f"[OK] YAML syntax valid: {filepath}")
        return True
    except yaml.YAMLError as e:
        print(f"[FAIL] YAML syntax error in {filepath}: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] Error reading {filepath}: {e}")
        return False

def check_python_imports():
    """Check if essential Python imports work."""
    required_imports = [
        'django',
        'django.conf',
        'django.core.management',
    ]
    
    all_ok = True
    for import_name in required_imports:
        try:
            __import__(import_name)
            print(f"[OK] Python import: {import_name}")
        except ImportError as e:
            print(f"[FAIL] Python import failed: {import_name} - {e}")
            all_ok = False
    
    return all_ok

def check_github_workflows():
    """Check GitHub Actions workflow files."""
    workflows_dir = Path(".github/workflows")
    
    if not workflows_dir.exists():
        print("[FAIL] .github/workflows directory not found")
        return False
    
    workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    
    if not workflow_files:
        print("[FAIL] No workflow files found in .github/workflows")
        return False
    
    print(f"Found {len(workflow_files)} workflow files:")
    
    all_valid = True
    for wf in workflow_files:
        if check_yaml_syntax(wf):
            # Check basic structure
            with open(wf, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'name:' in content and 'on:' in content and 'jobs:' in content:
                    print(f"   - Basic structure OK: {wf.name}")
                else:
                    print(f"   [WARN] Missing required sections in: {wf.name}")
                    all_valid = False
        else:
            all_valid = False
    
    return all_valid

def check_requirements_files():
    """Check requirements files."""
    requirements_files = [
        ("requirements.txt", "Main requirements"),
        ("requirements-dev.txt", "Development requirements"),
    ]
    
    all_ok = True
    for filename, description in requirements_files:
        if check_file_exists(filename, description):
            # Check if file has content
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if len(content) > 0:
                        print(f"   - Has content ({len(content.splitlines())} lines)")
                    else:
                        print(f"   [WARN] File is empty: {filename}")
                        all_ok = False
            except Exception as e:
                print(f"   [FAIL] Error reading {filename}: {e}")
                all_ok = False
    
    return all_ok

def check_deployment_scripts():
    """Check deployment scripts."""
    deployment_scripts = [
        ("deploy.sh", "Main deployment script"),
        ("backup.sh", "Backup script"),
        ("restore.sh", "Restore script"),
    ]
    
    all_ok = True
    for filename, description in deployment_scripts:
        if check_file_exists(filename, description):
            # Check if executable (on Unix-like systems)
            if os.name != 'nt':  # Not Windows
                import stat
                st = os.stat(filename)
                if st.st_mode & stat.S_IXUSR:
                    print(f"   - Is executable")
                else:
                    print(f"   [WARN] Not executable (run: chmod +x {filename})")
    
    return all_ok

def run_django_check():
    """Run Django system check."""
    print("\nRunning Django system check...")
    try:
        result = subprocess.run(
            [sys.executable, "manage.py", "check"],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            print("[OK] Django system check passed")
            return True
        else:
            print(f"[WARN] Django system check warnings/errors:")
            print(result.stdout)
            if result.stderr:
                print(result.stderr)
            return False
    except Exception as e:
        print(f"[FAIL] Failed to run Django check: {e}")
        return False

def main():
    """Main test function."""
    print("=" * 60)
    print("CI/CD Setup Validation for CMS Project")
    print("=" * 60)
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Essential files
    print("\n[1/6] Checking essential files...")
    essential_files = [
        ("manage.py", "Django management script"),
        (".gitignore", "Git ignore file"),
        ("README.md", "Project documentation"),
    ]
    
    for filename, description in essential_files:
        tests_total += 1
        if check_file_exists(filename, description):
            tests_passed += 1
    
    # Test 2: GitHub workflows
    print("\n[2/6] Checking GitHub Actions workflows...")
    tests_total += 1
    if check_github_workflows():
        tests_passed += 1
    
    # Test 3: Requirements files
    print("\n[3/6] Checking requirements files...")
    tests_total += 1
    if check_requirements_files():
        tests_passed += 1
    
    # Test 4: Deployment scripts
    print("\n[4/6] Checking deployment scripts...")
    tests_total += 1
    if check_deployment_scripts():
        tests_passed += 1
    
    # Test 5: Python imports
    print("\n[5/6] Checking Python imports...")
    tests_total += 1
    if check_python_imports():
        tests_passed += 1
    
    # Test 6: Django check
    print("\n[6/6] Running Django system check...")
    tests_total += 1
    if run_django_check():
        tests_passed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests passed: {tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("SUCCESS: All tests passed! CI/CD setup appears to be valid.")
        print("\nNext steps:")
        print("1. Configure GitHub Secrets in repository settings")
        print("2. Push to GitHub to trigger CI workflow")
        print("3. Monitor GitHub Actions for any issues")
        return 0
    else:
        print(f"WARNING: {tests_total - tests_passed} test(s) failed")
        print("\nRecommended actions:")
        print("1. Review the failed tests above")
        print("2. Fix any missing files or configuration issues")
        print("3. Run this test again after making changes")
        return 1

if __name__ == "__main__":
    sys.exit(main())