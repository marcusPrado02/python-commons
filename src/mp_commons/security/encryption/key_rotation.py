from __future__ import annotations

from mp_commons.security.encryption.fernet import EncryptionProvider

__all__ = ["KeyRotationService"]


class KeyRotationService:
    """Re-encrypts ciphertext from one provider to another."""

    @staticmethod
    def re_encrypt(
        old_provider: EncryptionProvider,
        new_provider: EncryptionProvider,
        ciphertext: bytes,
    ) -> bytes:
        plaintext = old_provider.decrypt(ciphertext)
        return new_provider.encrypt(plaintext)

    @staticmethod
    async def rotate_column(session, model_cls, field_name: str,
                            old_provider: EncryptionProvider,
                            new_provider: EncryptionProvider) -> int:
        """Batch-rotate an encrypted column in the DB.

        Returns number of rows updated.
        """
        from sqlalchemy import select, update

        col = getattr(model_cls, field_name)
        result = await session.execute(select(model_cls))
        rows = result.scalars().all()
        count = 0
        for row in rows:
            old_ct: bytes | None = getattr(row, field_name)
            if old_ct:
                new_ct = KeyRotationService.re_encrypt(old_provider, new_provider, old_ct)
                setattr(row, field_name, new_ct)
                count += 1
        await session.flush()
        return count
