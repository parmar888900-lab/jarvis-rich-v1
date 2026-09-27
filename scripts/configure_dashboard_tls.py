#!/usr/bin/env python3
"""Create a private self-signed LAN certificate for an explicitly named host."""

import argparse
import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def create_certificate(host: str, directory: Path) -> tuple[Path, Path]:
    host = host.strip()
    if not host or any(c in host for c in "/\\:* ?#"):
        raise ValueError("Provide one LAN IP address or DNS host")
    try:
        san = x509.IPAddress(ipaddress.ip_address(host))
    except ValueError:
        san = x509.DNSName(host)
    directory.mkdir(parents=True, exist_ok=True)
    certificate = directory / "dashboard.pem"
    private_key = directory / "dashboard.key"
    if certificate.exists() or private_key.exists():
        raise FileExistsError("Dashboard certificate already exists; preserve it or choose a new directory")
    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
            .add_extension(x509.SubjectAlternativeName([san]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    private_key.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.TraditionalOpenSSL,
                             serialization.NoEncryption()))
    certificate.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return certificate, private_key


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--directory", type=Path,
                        default=Path("generated/state/dashboard-tls"))
    args = parser.parse_args()
    cert, key = create_certificate(args.host, args.directory)
    print(f"Certificate: {cert}; private key: {key}. Trust the certificate on the iPad manually.")
