#!/usr/bin/env python
"""
Generate self-signed SSL certificate for local development
"""
from OpenSSL import crypto
import os

def generate_self_signed_cert():
    # Create a key pair
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 2048)

    # Create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "State"
    cert.get_subject().L = "City"
    cert.get_subject().O = "Organization"
    cert.get_subject().OU = "Organizational Unit"
    cert.get_subject().CN = "localhost"
    
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365*24*60*60)  # Valid for 1 year
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha256')

    # Save certificate
    with open("localhost.pem", "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    
    # Save private key
    with open("localhost-key.pem", "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
    
    print("✓ Certificate generated successfully!")
    print("  - localhost.pem")
    print("  - localhost-key.pem")

if __name__ == "__main__":
    if os.path.exists("localhost.pem") and os.path.exists("localhost-key.pem"):
        print("Certificate files already exist. Delete them first if you want to regenerate.")
    else:
        generate_self_signed_cert()
