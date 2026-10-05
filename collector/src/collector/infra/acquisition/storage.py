"""Armazenamento local content-addressed. Nome remoto não vira path."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from collector.application.acquisition.errors import AcquisitionError
from collector.application.acquisition.ports import StoragePutResult
from collector.application.acquisition.reasons import AcquisitionReason


class LocalTempBlob:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle = path.open("wb")
        self._size = 0
        self._discarded = False

    def write(self, chunk: bytes) -> None:
        self._handle.write(chunk)
        self._size += len(chunk)

    def size(self) -> int:
        return self._size

    def open_read(self):
        self._handle.flush()
        return self._path.open("rb")

    def discard(self) -> None:
        if self._discarded:
            return
        self._discarded = True
        try:
            if not self._handle.closed:
                self._handle.close()
        except OSError:
            pass
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            pass

    def close_for_commit(self) -> Path:
        self._handle.close()
        return self._path


class LocalArtifactStorage:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._tmp = root / "tmp"
        self._blobs = root / "sha256"
        self._tmp.mkdir(parents=True, exist_ok=True)
        self._blobs.mkdir(parents=True, exist_ok=True)

    def open_temp(self) -> LocalTempBlob:
        path = self._tmp / uuid4().hex
        return LocalTempBlob(path)

    def commit(self, temp: LocalTempBlob, *, sha256: str) -> StoragePutResult:
        digest = sha256.lower()
        dest = self._blob_path(digest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        source = temp.close_for_commit()
        if dest.exists():
            temp.discard()
            return StoragePutResult(storage_key=_storage_key(digest), created=False)
        try:
            os.replace(source, dest)
        except OSError as exc:
            temp.discard()
            raise AcquisitionError(
                "falha ao gravar artefato",
                reason=AcquisitionReason.STORAGE_ERROR,
            ) from exc
        return StoragePutResult(storage_key=_storage_key(digest), created=True)

    def exists(self, sha256: str) -> bool:
        return self._blob_path(sha256.lower()).exists()

    def delete_if_created(self, storage_key: str) -> None:
        path = self._root / storage_key
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def open(self, storage_key: str):
        return (self._root / storage_key).open("rb")

    def _blob_path(self, sha256: str) -> Path:
        return self._blobs / sha256[:2] / sha256[2:4] / sha256


def _storage_key(sha256: str) -> str:
    return f"sha256/{sha256[:2]}/{sha256[2:4]}/{sha256}"
