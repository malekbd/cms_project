#!/usr/bin/env python3
"""
Diagnostic and fix script for 502 Bad Gateway errors in CMS project.
This script helps identify and fix common causes of 502 errors.
"""

import os
import sys
import subprocess
import socket
import time
from pathlib import Path

def check_gunicorn_process():
    """Check if Gunicorn is running."""
    print("Checking Gunicorn processes...")
    try:
        # Different commands for different OS
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq gunicorn.exe"],
                capture_output=True,
                text=True,
                shell=True
            )
            if "gunicorn.exe" in result.stdout:
                print("✓ Gunicorn is running")
                return True
            else:
                print("✗ Gunicorn is NOT running")
                return False
        else:
            result = subprocess.run(
                ["pgrep", "-f", "gunicorn"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✓ Gunicorn is running (PID(s): {})".format(result.stdout.strip()))
                return True
            else:
                print("✗ Gunicorn is NOT running")
                return False
    except Exception as e:
        print(f"Error checking Gunicorn: {e}")
        return False

def check_socket_file():
    """Check if the Unix socket file exists and has correct permissions."""
    socket_path = os.environ.get("GUNICORN_SOCKET", "/run/cms/cms.sock")
    print(f"Checking socket file: {socket_path}")
    
    if sys.platform == "win32":
        print("⚠ Windows detected - Unix sockets not supported")
        return False
    
    if os.path.exists(socket_path):
        print(f"✓ Socket file exists at {socket_path}")
        # Check permissions
        stat = os.stat(socket_path)
        print(f"  Permissions: {oct(stat.st_mode)[-3:]}")
        print(f"  Owner: {stat.st_uid}")
        return True
    else:
        print(f"✗ Socket file does NOT exist at {socket_path}")
        return False

def check_port_listening(port=8000):
    """Check if a port is listening."""
    print(f"Checking if port {port} is listening...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            print(f"✓ Port {port} is listening")
            return True
        else:
            print(f"✗ Port {port} is NOT listening")
            return False
    except Exception as e:
        print(f"Error checking port: {e}")
        return False

def check_database():
    """Check database connectivity."""
    print("Checking database connectivity...")
    try:
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cms_project.settings')
        django.setup()
        
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        if result and result[0] == 1:
            print("✓ Database connection successful")
            return True
        else:
            print("✗ Database connection failed")
            return False
    except Exception as e:
        print(f"✗ Database error: {e}")
        return False

def check_nginx_config():
    """Check Nginx configuration (Linux only)."""
    if sys.platform == "win32":
        print("⚠ Windows detected - skipping Nginx check")
        return True
    
    print("Checking Nginx configuration...")
    try:
        # Check if Nginx is running
        result = subprocess.run(
            ["systemctl", "is-active", "nginx"],
            capture_output=True,
            text=True
        )
        if result.stdout.strip() == "active":
            print("✓ Nginx is running")
            
            # Check Nginx configuration
            result = subprocess.run(
                ["nginx", "-t"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✓ Nginx configuration is valid")
                return True
            else:
                print("✗ Nginx configuration has errors:")
                print(result.stderr)
                return False
        else:
            print("✗ Nginx is NOT running")
            return False
    except FileNotFoundError:
        print("⚠ Nginx not installed")
        return True
    except Exception as e:
        print(f"Error checking Nginx: {e}")
        return False

def fix_gunicorn_config():
    """Fix common Gunicorn configuration issues."""
    print("\nFixing Gunicorn configuration...")
    
    config_path = "gunicorn.conf.py"
    if not os.path.exists(config_path):
        print(f"✗ Gunicorn config not found at {config_path}")
        return False
    
    try:
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Check for Windows incompatible settings
        fixes = []
        
        if sys.platform == "win32" and "unix:/" in content:
            print("⚠ Windows detected but config uses Unix socket")
            # Suggest using TCP instead
            new_content = content.replace(
                'bind = "unix:/run/cms/cms.sock"',
                'bind = "127.0.0.1:8000"  # Changed from Unix socket for Windows compatibility'
            )
            if new_content != content:
                with open(config_path, 'w') as f:
                    f.write(new_content)
                print("✓ Updated Gunicorn config to use TCP instead of Unix socket")
                fixes.append("socket_type")
        
        # Check for user/group settings that might cause issues
        if "user = \"cmsuser\"" in content and sys.platform == "win32":
            print("⚠ Windows doesn't support user/group settings in Gunicorn")
            # Comment out user/group settings
            new_content = content.replace(
                'user = "cmsuser"',
                '# user = "cmsuser"  # Commented out for Windows compatibility'
            ).replace(
                'group = "cmsuser"',
                '# group = "cmsuser"  # Commented out for Windows compatibility'
            )
            if new_content != content:
                with open(config_path, 'w') as f:
                    f.write(new_content)
                print("✓ Commented out user/group settings for Windows")
                fixes.append("user_group")
        
        if fixes:
            print(f"✓ Applied fixes: {', '.join(fixes)}")
            return True
        else:
            print("✓ No fixes needed for Gunicorn config")
            return True
            
    except Exception as e:
        print(f"✗ Error fixing Gunicorn config: {e}")
        return False

def start_gunicorn():
    """Start Gunicorn server."""
    print("\nStarting Gunicorn server...")
    
    if sys.platform == "win32":
        print("⚠ Gunicorn has limited support on Windows")
        print("Consider using waitress or django development server instead")
        return False
    
    try:
        # Use the gunicorn command
        cmd = [
            "gunicorn",
            "--config", "gunicorn.conf.py",
            "cms_project.wsgi:application"
        ]
        
        print(f"Running: {' '.join(cmd)}")
        # Run in background
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give it a moment to start
        time.sleep(3)
        
        # Check if it's still running
        if process.poll() is None:
            print("✓ Gunicorn started successfully")
            return True
        else:
            stdout, stderr = process.communicate()
            print("✗ Gunicorn failed to start")
            print(f"Stderr: {stderr[:500]}")
            return False
            
    except Exception as e:
        print(f"✗ Error starting Gunicorn: {e}")
        return False

def main():
    print("=" * 60)
    print("502 Bad Gateway Diagnostic Tool")
    print("=" * 60)
    
    # Run diagnostics
    print("\n[DIAGNOSTICS]")
    gunicorn_running = check_gunicorn_process()
    socket_ok = check_socket_file()
    port_ok = check_port_listening(8000)
    db_ok = check_database()
    nginx_ok = check_nginx_config()
    
    print("\n[SUMMARY]")
    issues = []
    if not gunicorn_running:
        issues.append("Gunicorn not running")
    if not socket_ok and sys.platform != "win32":
        issues.append("Socket file missing or wrong permissions")
    if not port_ok:
        issues.append("Port not listening")
    if not db_ok:
        issues.append("Database connection failed")
    if not nginx_ok:
        issues.append("Nginx issues")
    
    if issues:
        print(f"✗ Found {len(issues)} potential issue(s):")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✓ No obvious issues found")
    
    # Offer to fix
    print("\n[FIXES]")
    if issues:
        response = input("Do you want to attempt automatic fixes? (y/n): ")
        if response.lower() == 'y':
            fix_gunicorn_config()
            
            if not gunicorn_running:
                start_response = input("Start Gunicorn now? (y/n): ")
                if start_response.lower() == 'y':
                    start_gunicorn()
    
    print("\n[RECOMMENDATIONS]")
    if sys.platform == "win32":
        print("1. Use Django development server for Windows development:")
        print("   python manage.py runserver 127.0.0.1:8000")
        print("2. For production on Windows, consider using waitress:")
        print("   pip install waitress")
        print("   waitress-serve --port=8000 cms_project.wsgi:application")
    else:
        print("1. Check Gunicorn logs: tail -f logs/gunicorn-error.log")
        print("2. Check Nginx logs: tail -f /var/log/nginx/error.log")
        print("3. Verify socket permissions: ls -la /run/cms/cms.sock")
    
    print("\n" + "=" * 60)
    print("Diagnostic complete. Check the recommendations above.")
    print("=" * 60)

if __name__ == "__main__":
    main()
