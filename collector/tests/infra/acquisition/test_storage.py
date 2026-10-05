"""Storage local content-addressed. Nome remoto não controla path."""

from pathlib import Path

from collector.infra.acquisition import LocalArtifactStorage


def test_put_exists_and_dedup(tmp_path: Path) -> None:
    storage = LocalArtifactStorage(tmp_path)
    digest = "ab" + "c" * 62
    first = storage.open_temp()
    first.write(b"payload")
    put = storage.commit(first, sha256=digest)
    assert put.created is True
    assert storage.exists(digest)
    assert (tmp_path / put.storage_key).read_bytes() == b"payload"

    second = storage.open_temp()
    second.write(b"payload")
    again = storage.commit(second, sha256=digest)
    assert again.created is False
    assert list((tmp_path / "sha256").rglob(digest))  # um arquivo


def test_temp_cleanup_on_discard(tmp_path: Path) -> None:
    storage = LocalArtifactStorage(tmp_path)
    temp = storage.open_temp()
    temp.write(b"tmp")
    path = temp._path
    temp.discard()
    assert path.exists() is False


def test_remote_name_does_not_affect_path(tmp_path: Path) -> None:
    storage = LocalArtifactStorage(tmp_path)
    digest = "11" + "2" * 62
    temp = storage.open_temp()
    temp.write(b"x")
    put = storage.commit(temp, sha256=digest)
    assert "../" not in put.storage_key
    assert "edital.zip" not in put.storage_key
    assert put.storage_key == f"sha256/{digest[:2]}/{digest[2:4]}/{digest}"
