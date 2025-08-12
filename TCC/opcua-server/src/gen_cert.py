#!/usr/bin/env python3
"""
Gera chaves RSA e certificados X.509 autoassinados com SAN
para o servidor OPC UA (pasta opcua-server/certs)
e para o cliente-gateway (pasta gateway/certs), usando 'cryptography'.
Inclui ApplicationURI e hostname nos SANs para evitar avisos de OPC UA.
"""

import socket
import ipaddress
from pathlib import Path
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.x509 import UniformResourceIdentifier
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# === CONFIGURAÇÃO ===
C  = "BR"
ST = "SC"
L  = "Itajaí"
O  = "IFSC"
OU = "TCC"

CN_SERVER = "opcua-server"
CN_CLIENT = "gateway-client"

HOST = socket.gethostname()  # ex.: gabriel-pc
DNS_LIST = [CN_SERVER, "localhost", HOST]
IP_LIST  = ["127.0.0.1", "192.168.0.10"]
VALID_DAYS = 365

# Script está em opcua-server/src/
BASE_DIR = Path(__file__).resolve().parent.parent           # opcua-server/
SERVER_CERT_DIR = BASE_DIR / "certs"                        # opcua-server/certs
CLIENT_CERT_DIR = BASE_DIR.parent / "gateway" / "certs"     # gateway/certs

SERVER_KEY = SERVER_CERT_DIR / "server_key.pem"
SERVER_CRT = SERVER_CERT_DIR / "server_cert.pem"
CLIENT_KEY = CLIENT_CERT_DIR / "gw_key.pem"
CLIENT_CRT = CLIENT_CERT_DIR / "gw_cert.pem"

SERVER_URI = f"urn:{HOST}:opcua-server"
CLIENT_URI = f"urn:{HOST}:gateway-client"
# =====================

def _save_pem(key, cert, key_path: Path, crt_path: Path):
    key_path.parent.mkdir(parents=True, exist_ok=True)
    crt_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        )
    )
    crt_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Gerado → chave: {key_path}\n          cert.: {crt_path}\n")

def make_server_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, C),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, ST),
        x509.NameAttribute(NameOID.LOCALITY_NAME, L),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, O),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, OU),
        x509.NameAttribute(NameOID.COMMON_NAME, CN_SERVER),
    ])
    alt_names = [x509.DNSName(d) for d in DNS_LIST] + \
                [x509.IPAddress(ipaddress.ip_address(ip)) for ip in IP_LIST] + \
                [UniformResourceIdentifier(SERVER_URI)]
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)  # autoassinado
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=VALID_DAYS))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    _save_pem(key, cert, SERVER_KEY, SERVER_CRT)

def make_client_cert():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, C),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, ST),
        x509.NameAttribute(NameOID.LOCALITY_NAME, L),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, O),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, OU),
        x509.NameAttribute(NameOID.COMMON_NAME, CN_CLIENT),
    ])
    # para cliente, incluímos hostname e ApplicationURI do cliente
    client_dns = [CN_CLIENT, "localhost", HOST]
    client_ips = ["127.0.0.1"]  # suficiente p/ cliente local
    alt_names = [x509.DNSName(d) for d in client_dns] + \
                [x509.IPAddress(ipaddress.ip_address(ip)) for ip in client_ips] + \
                [UniformResourceIdentifier(CLIENT_URI)]
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)  # autoassinado
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=VALID_DAYS))
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    _save_pem(key, cert, CLIENT_KEY, CLIENT_CRT)

def main():
    print("=== Gerando certificados separados (com ApplicationURI & hostname) ===")
    make_server_cert()
    make_client_cert()
    print("=== OK ===")
    print(f"Servidor → {SERVER_CRT}\nGateway  → {CLIENT_CRT}")

if __name__ == "__main__":
    main()