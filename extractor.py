import pdfplumber

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Terima raw bytes dari PDF, kembalikan text sebagai string.
    Raise ValueError kalau PDF kosong atau hasil scan.
    """
    full_text = ""

    with pdfplumber.open(file_bytes) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

    # Guard: reject PDF scan atau kosong
    if len(full_text.strip()) < 200:
        raise ValueError(
            "PDF ini sepertinya hasil scan atau tidak mengandung teks. "
            "Mohon upload versi digital dari kontrak kerja kamu."
        )

    return full_text.strip()