#!/usr/bin/env python
"""Generate a self-signed CA plus server/client certificates for local mTLS.

Certificates are written under var/certs/ (gitignored) so they never enter
the repository. Development/staging smoke use only -- production must use
the real CA and a proper secret store.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CERT_DIR = ROOT / "var" / "certs"

CA_KEY = CERT_DIR / "ca.key"
CA_CERT = CERT_DIR / "ca.crt"
SERVER_KEY = CERT_DIR / "server.key"
SERVER_CERT = CERT_DIR / "server.crt"
CLIENT_KEY = CERT_DIR / "client.key"
CLIENT_CERT = CERT_DIR / "client.crt"
SERVER_CNF = CERT_DIR / "openssl-server.cnf"


def _run(args: list[str]) -> None:
    subprocess.run(args, check=True, capture_output=True, text=True)


def main() -> int:
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    # 1. Self-signed CA
    _run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
          "-keyout", str(CA_KEY), "-out", str(CA_CERT), "-days", "365",
          "-subj", "/CN=travel-agent-local-ca"])
    # 2. Server key + CSR
    _run(["openssl", "req", "-newkey", "rsa:2048", "-nodes",
          "-keyout", str(SERVER_KEY), "-out", str(CERT_DIR / "server.csr"),
          "-subj", "/CN=travel-agent-server"])
    SERVER_CNF.write_text(
        "subjectAltName=DNS:localhost,DNS:travel-agent-api,DNS:travel-gateway,"
        "IP:127.0.0.1\n"
        "extendedKeyUsage=serverAuth\n",
        encoding="utf-8",
    )
    _run(["openssl", "x509", "-req", "-in", str(CERT_DIR / "server.csr"),
          "-CA", str(CA_CERT), "-CAkey", str(CA_KEY), "-CAcreateserial",
          "-out", str(SERVER_CERT), "-days", "365",
          "-extfile", str(SERVER_CNF)])
    # 3. Client key + cert (gateway -> runtime mTLS identity)
    _run(["openssl", "req", "-newkey", "rsa:2048", "-nodes",
          "-keyout", str(CLIENT_KEY), "-out", str(CERT_DIR / "client.csr"),
          "-subj", "/CN=travel-gateway-client"])
    _run(["openssl", "x509", "-req", "-in", str(CERT_DIR / "client.csr"),
          "-CA", str(CA_CERT), "-CAkey", str(CA_KEY), "-CAcreateserial",
          "-out", str(CLIENT_CERT), "-days", "365"])
    # Best-effort private key hygiene (POSIX only; Windows ACLs skipped here).
    for key in (CA_KEY, SERVER_KEY, CLIENT_KEY):
        try:
            key.chmod(0o600)
        except OSError:
            pass
    print(f"certificates written under {CERT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
