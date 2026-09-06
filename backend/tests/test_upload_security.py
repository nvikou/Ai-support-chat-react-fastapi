"""Regression: knowledge upload must bound size and trust magic bytes.

Attack vector: await file.read() loads arbitrary payloads into memory,
and trusting client content_type lets an attacker upload executables
disguised as text/plain.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from app.services.upload_security import UploadTooLargeError
from app.services.upload_security import UploadTypeRejectedError
from app.services.upload_security import detect_kind_from_magic
from app.services.upload_security import save_upload_streaming


class FakeUpload:
    """Minimal UploadFile stand-in (no FastAPI / network)."""

    def __init__(self, data: bytes, filename: str = "doc.bin") -> None:
        self.filename = filename
        self.content_type = "application/octet-stream"
        self._buf = io.BytesIO(data)

    async def read(self, size: int = -1) -> bytes:
        return self._buf.read(size)


def test_magic_accepts_pdf_header() -> None:
    assert detect_kind_from_magic(b"%PDF-1.7\n...") == "pdf"


def test_magic_rejects_exe_even_if_named_txt() -> None:
    # PE/DOS header — must not be treated as text.
    assert detect_kind_from_magic(b"MZ\x90\x00fake-pe") is None


def test_magic_accepts_utf8_text() -> None:
    assert detect_kind_from_magic(b"# FAQ\nHello world\n") == "text"


@pytest.mark.asyncio
async def test_oversized_upload_rejected_while_streaming(
    tmp_path: Path,
) -> None:
    payload = b"%PDF-1.4\n" + (b"x" * 2000)
    upload = FakeUpload(payload, filename="big.pdf")
    with pytest.raises(UploadTooLargeError) as exc_info:
        await save_upload_streaming(
            upload,
            max_bytes=1024,
            chunk_size=256,
            temp_dir=tmp_path,
        )
    assert exc_info.value.status_code == 413
    # Temp file must not be left behind after rejection.
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_spoofed_text_plain_exe_rejected(
    tmp_path: Path,
) -> None:
    pe = b"MZ" + b"\x00" * 64 + b"This program cannot be run"
    upload = FakeUpload(pe, filename="notes.txt")
    upload.content_type = "text/plain"
    with pytest.raises(UploadTypeRejectedError):
        await save_upload_streaming(
            upload,
            max_bytes=10 * 1024 * 1024,
            temp_dir=tmp_path,
        )


@pytest.mark.asyncio
async def test_legitimate_pdf_accepted(tmp_path: Path) -> None:
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    upload = FakeUpload(pdf, filename="guide.pdf")
    upload.content_type = "application/pdf"
    result = await save_upload_streaming(
        upload,
        max_bytes=10 * 1024 * 1024,
        temp_dir=tmp_path,
    )
    assert result.kind == "pdf"
    assert result.size == len(pdf)
    assert Path(result.path).is_file()
    assert Path(result.path).read_bytes() == pdf
    Path(result.path).unlink(missing_ok=True)
