"""Unit tests for §84 – Security Encryption."""
import pytest

from mp_commons.security.encryption import (
    AesGcmEncryptionProvider,
    FernetEncryptionProvider,
    KeyRotationService,
)


class TestFernetEncryptionProvider:
    def test_round_trip(self):
        key = FernetEncryptionProvider.generate_key()
        provider = FernetEncryptionProvider([key])
        ct = provider.encrypt(b"hello world")
        assert provider.decrypt(ct) == b"hello world"

    def test_ciphertext_not_plaintext(self):
        key = FernetEncryptionProvider.generate_key()
        provider = FernetEncryptionProvider([key])
        ct = provider.encrypt(b"secret")
        assert b"secret" not in ct

    def test_two_encryptions_differ(self):
        key = FernetEncryptionProvider.generate_key()
        provider = FernetEncryptionProvider([key])
        ct1 = provider.encrypt(b"msg")
        ct2 = provider.encrypt(b"msg")
        assert ct1 != ct2  # Fernet uses random IV

    def test_wrong_key_raises(self):
        key1 = FernetEncryptionProvider.generate_key()
        key2 = FernetEncryptionProvider.generate_key()
        p1 = FernetEncryptionProvider([key1])
        p2 = FernetEncryptionProvider([key2])
        ct = p1.encrypt(b"data")
        with pytest.raises(Exception):
            p2.decrypt(ct)

    def test_key_rotation_decryption(self):
        """MultiFernet should decrypt ciphertexts from any key in the list."""
        key1 = FernetEncryptionProvider.generate_key()
        key2 = FernetEncryptionProvider.generate_key()
        p_old = FernetEncryptionProvider([key1])
        ct = p_old.encrypt(b"payload")
        # New provider has both keys; should decrypt old ciphertext
        p_new = FernetEncryptionProvider([key2, key1])
        assert p_new.decrypt(ct) == b"payload"


class TestAesGcmEncryptionProvider:
    def test_round_trip(self):
        key = AesGcmEncryptionProvider.generate_key()
        provider = AesGcmEncryptionProvider(key)
        ct = provider.encrypt(b"secure data")
        assert provider.decrypt(ct) == b"secure data"

    def test_ciphertext_includes_nonce(self):
        key = AesGcmEncryptionProvider.generate_key()
        provider = AesGcmEncryptionProvider(key)
        ct = provider.encrypt(b"x")
        assert len(ct) > 12  # nonce + ciphertext + tag

    def test_different_nonces_produce_different_ct(self):
        key = AesGcmEncryptionProvider.generate_key()
        provider = AesGcmEncryptionProvider(key)
        ct1 = provider.encrypt(b"same")
        ct2 = provider.encrypt(b"same")
        assert ct1 != ct2

    def test_invalid_key_length_raises(self):
        with pytest.raises(ValueError):
            AesGcmEncryptionProvider(b"short")

    def test_wrong_key_raises(self):
        key1 = AesGcmEncryptionProvider.generate_key()
        key2 = AesGcmEncryptionProvider.generate_key()
        p1 = AesGcmEncryptionProvider(key1)
        p2 = AesGcmEncryptionProvider(key2)
        ct = p1.encrypt(b"data")
        with pytest.raises(Exception):
            p2.decrypt(ct)


class TestKeyRotationService:
    def test_re_encrypt_produces_decryptable_output(self):
        key1 = FernetEncryptionProvider.generate_key()
        key2 = FernetEncryptionProvider.generate_key()
        p_old = FernetEncryptionProvider([key1])
        p_new = FernetEncryptionProvider([key2])
        original_ct = p_old.encrypt(b"rotate me")
        new_ct = KeyRotationService.re_encrypt(p_old, p_new, original_ct)
        assert p_new.decrypt(new_ct) == b"rotate me"

    def test_re_encrypt_old_key_cannot_decrypt_new(self):
        key1 = FernetEncryptionProvider.generate_key()
        key2 = FernetEncryptionProvider.generate_key()
        p_old = FernetEncryptionProvider([key1])
        p_new = FernetEncryptionProvider([key2])
        original_ct = p_old.encrypt(b"secret")
        new_ct = KeyRotationService.re_encrypt(p_old, p_new, original_ct)
        with pytest.raises(Exception):
            p_old.decrypt(new_ct)  # old key can't decrypt new ciphertext
