"""PDFs sintéticos mínimos para extração. Sem binários no Git."""

from __future__ import annotations


def text_pdf(*pages: str) -> bytes:
    """Monta um PDF 1.4 com texto Helvetica por página."""
    kids: list[int] = []
    objects: dict[int, bytes] = {}
    next_id = 3
    font_id = 3 + 2 * len(pages)
    objects[font_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    for text in pages:
        content_id = next_id
        page_id = next_id + 1
        next_id += 2
        escaped = (
            text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1", "replace")
        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        ).encode("ascii")
        kids.append(page_id)

    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids_ref = " ".join(f"{kid} 0 R" for kid in kids) or ""
    objects[2] = (
        f"<< /Type /Pages /Kids [{kids_ref}] /Count {len(kids)} >>".encode("ascii")
    )

    max_id = max(objects)
    body = b"%PDF-1.4\n"
    offsets = {0: 0}
    for obj_id in range(1, max_id + 1):
        offsets[obj_id] = len(body)
        payload = objects.get(obj_id, b"<< >>")
        body += f"{obj_id} 0 obj\n".encode("ascii") + payload + b"\nendobj\n"

    xref_at = len(body)
    body += f"xref\n0 {max_id + 1}\n".encode("ascii")
    body += b"0000000000 65535 f \n"
    for obj_id in range(1, max_id + 1):
        body += f"{offsets[obj_id]:010d} 00000 n \n".encode("ascii")
    body += (
        f"trailer << /Size {max_id + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode("ascii")
    return body


BLANK_PDF = text_pdf("")
ONE_PAGE_PDF = text_pdf("Hello page one")
TWO_PAGE_PDF = text_pdf("First page text", "Second page text")
FAKE_PDF_HEADER = b"%PDF-1.4\nthis is not a real pdf structure"
INVALID_BYTES = b"not-a-pdf"
