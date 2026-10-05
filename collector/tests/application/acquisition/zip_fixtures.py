"""ZIPs sintéticos para inspeção. Sem extração e sem binários no Git."""

from __future__ import annotations

import io
import zipfile
from zipfile import ZipInfo


def zip_bytes(*pairs: tuple[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in pairs:
            archive.writestr(name, content)
    return buffer.getvalue()


def zip_with_info(info: ZipInfo, content: bytes = b"x") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(info, content)
    return buffer.getvalue()


def encrypted_zip() -> bytes:
    info = ZipInfo("secret.pdf")
    info.flag_bits |= 0x1
    return zip_with_info(info, b"cipher")


def symlink_zip() -> bytes:
    info = ZipInfo("link")
    info.external_attr = 0xA000 << 16
    return zip_with_info(info, b"/tmp/target")


PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
UNKNOWN_BYTES = b"hello-usiar"
