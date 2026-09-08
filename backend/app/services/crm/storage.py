"""File storage abstraction for client documents (ТЗ §14: "не зберігати
binary-файли прямо в PostgreSQL; використовувати object storage, у БД —
metadata та storage key").

`LocalFileStorage` is the default so the CRM works out of the box with no
extra account to set up. Swap in an S3/R2-backed implementation later by
matching this same three-method interface — nothing above this layer needs
to change. Known limitation: on a platform with an ephemeral filesystem
(e.g. a Railway container), local files are lost on redeploy — move to
object storage before relying on file uploads in production.
"""

from __future__ import annotations

import uuid
from pathlib import Path


class LocalFileStorage:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, client_id: int, filename: str, data: bytes) -> str:
        safe_name = Path(filename).name
        key = f"{client_id}/{uuid.uuid4().hex}_{safe_name}"
        path = self.base_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def read(self, storage_key: str) -> bytes:
        return (self.base_dir / storage_key).read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self.base_dir / storage_key
        if path.exists():
            path.unlink()


_default_storage: LocalFileStorage | None = None


def get_storage() -> LocalFileStorage:
    global _default_storage
    if _default_storage is None:
        from app.core.config import settings

        _default_storage = LocalFileStorage(settings.file_storage_dir)
    return _default_storage
