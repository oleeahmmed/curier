#!/usr/bin/env python
"""
Run Django development server with HTTPS using self-signed certificate
"""
import os
import sys
from pathlib import Path

def main():
    # Find the most recent certificate file
    cert_files = list(Path('.').glob('localhost+*.pem'))
    key_files = list(Path('.').glob('localhost+*-key.pem'))
    
    # Remove key files from cert_files list
    cert_files = [f for f in cert_files if '-key' not in f.name]
    
    if not cert_files or not key_files:
        print("=" * 60)
        print("SSL Certificate not found!")
        print("=" * 60)
        print("\nPlease run mkcert to create certificates:\n")
        print("1. Find your local IP address:")
        print("   ipconfig")
        print("\n2. Create certificate (replace YOUR_IP with your actual IP):")
        print("   .\\mkcert-v1.4.4-windows-amd64.exe localhost 127.0.0.1 0.0.0.0 ::1 YOUR_IP")
        print("\n3. Run this script again")
        print("=" * 60)
        sys.exit(1)
    
    # Use the most recent certificate
    cert_file = sorted(cert_files)[-1]
    key_file = sorted(key_files)[-1]
    
    print(f"\nUsing certificate: {cert_file.name}")
    print(f"Using key: {key_file.name}")
    
    # Run Django with SSL
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    
    from django.core.management import execute_from_command_line
    
    print("\n" + "=" * 60)
    print("Starting Django with HTTPS...")
    print("Local access: https://localhost:8000")
    print("Network access: https://YOUR_IP:8000")
    print("=" * 60 + "\n")
    
    execute_from_command_line([
        'manage.py',
        'runserver_plus',
        '--cert-file', str(cert_file),
        '--key-file', str(key_file),
        '0.0.0.0:8000'
    ])

if __name__ == '__main__':
    main()
