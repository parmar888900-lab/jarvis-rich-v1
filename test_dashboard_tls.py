from cryptography import x509
from cryptography.x509 import DNSName, IPAddress

from scripts.configure_dashboard_tls import create_certificate


def test_certificate_binds_only_explicit_host_and_preserves_existing(tmp_path):
    cert, key = create_certificate("192.168.1.18", tmp_path)
    parsed = x509.load_pem_x509_certificate(cert.read_bytes())
    sans = parsed.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert [str(x) for x in sans.get_values_for_type(IPAddress)] == ["192.168.1.18"]
    assert sans.get_values_for_type(DNSName) == []
    original = key.read_bytes()
    try:
        create_certificate("192.168.1.18", tmp_path)
    except FileExistsError:
        pass
    else:
        raise AssertionError("Existing private key was overwritten")
    assert key.read_bytes() == original
