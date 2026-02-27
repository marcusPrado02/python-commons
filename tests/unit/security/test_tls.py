"""Unit tests for §87 – TLS / Certificate Helpers."""
from __future__ import annotations

import hashlib

import pytest

from mp_commons.security.tls import CertPinningError, CertificatePinner


class TestCertificatePinner:
    def test_pin_and_verify_correct(self):
        pinner = CertificatePinner()
        cert_der = b"fake-cert-der-bytes"
        fp = hashlib.sha256(cert_der).hexdigest()
        pinner.pin("example.com", [fp])
        assert pinner.verify("example.com", cert_der) is True

    def test_pin_with_colon_format(self):
        pinner = CertificatePinner()
        cert_der = b"fake-cert"
        raw = hashlib.sha256(cert_der).hexdigest()
        # Build XX:YY:ZZ format
        coloned = ":".join(raw[i:i+2] for i in range(0, len(raw), 2))
        pinner.pin("host.io", [coloned])
        assert pinner.verify("host.io", cert_der) is True

    def test_verify_mismatch_raises(self):
        pinner = CertificatePinner()
        pinner.pin("example.com", ["aabbcc"])
        with pytest.raises(CertPinningError, match="example.com"):
            pinner.verify("example.com", b"different-cert")

    def test_unknown_host_always_true(self):
        pinner = CertificatePinner()
        assert pinner.verify("unknown.host", b"any-cert") is True

    def test_multiple_fingerprints(self):
        pinner = CertificatePinner()
        cert_der1 = b"cert1"
        cert_der2 = b"cert2"
        fp1 = hashlib.sha256(cert_der1).hexdigest()
        fp2 = hashlib.sha256(cert_der2).hexdigest()
        pinner.pin("example.com", [fp1, fp2])
        assert pinner.verify("example.com", cert_der1) is True
        assert pinner.verify("example.com", cert_der2) is True

    def test_pinned_hosts_returns_list(self):
        pinner = CertificatePinner()
        pinner.pin("a.com", ["aa"])
        pinner.pin("b.com", ["bb"])
        hosts = pinner.pinned_hosts()
        assert "a.com" in hosts
        assert "b.com" in hosts

    def test_pin_multiple_calls_accumulate(self):
        pinner = CertificatePinner()
        cert_der = b"cert"
        fp = hashlib.sha256(cert_der).hexdigest()
        pinner.pin("host", ["notmatch"])
        pinner.pin("host", [fp])
        assert pinner.verify("host", cert_der) is True


class TestCertificateLoaderImport:
    def test_import_succeeds(self):
        from mp_commons.security.tls import CertificateLoader  # noqa: F401

    def test_mtls_client_import(self):
        from mp_commons.security.tls import MtlsHttpxClient  # noqa: F401

    def test_expiry_checker_import(self):
        from mp_commons.security.tls import CertificateExpiryChecker  # noqa: F401
