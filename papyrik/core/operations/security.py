"""Security: encrypt and decrypt with a user password.

Pure functions - paths + params in, an output path out; the input file is never
modified. Encryption uses AES-256.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter


def encrypt(input_pdf: str | Path, password: str, output: str | Path) -> Path:
    """Write a copy of `input_pdf` protected by `password` (AES-256)."""
    if not password:
        raise ValueError("Password cannot be empty.")
    reader = PdfReader(str(input_pdf))
    if reader.is_encrypted and reader.decrypt("") == 0:
        raise ValueError(
            f"'{Path(input_pdf).name}' is already password-protected; "
            "decrypt it first."
        )
    writer = PdfWriter()
    writer.append(reader)
    writer.encrypt(user_password=password, algorithm="AES-256")

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        writer.write(fh)
    return out


def decrypt(input_pdf: str | Path, password: str, output: str | Path) -> Path:
    """Write a plaintext copy of `input_pdf`, removing its password."""
    reader = PdfReader(str(input_pdf))
    if not reader.is_encrypted:
        raise ValueError(f"'{Path(input_pdf).name}' is not password-protected.")
    if reader.decrypt(password) == 0:
        raise ValueError("Wrong password.")

    writer = PdfWriter()
    writer.append(reader)  # no encrypt() call -> output is plaintext

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        writer.write(fh)
    return out
