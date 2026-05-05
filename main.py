import io
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from extractor import extract_text_from_pdf
from analyzer import analyze_contract

app = FastAPI(title="BacaDulu API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Valid profile keys — harus cocok dengan PROFILE_LABELS di analyzer.py
VALID_PROFILES = {"fresh_grad", "freelancer", "experienced", "executive"}

@app.get("/")
def health_check():
    return {"status": "ok", "service": "BacaDulu API"}

@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    user_profile: str = Form(default="experienced")  # FIX: default key yang valid
):
    # Validasi format file
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Hanya file PDF yang diterima.")

    file_bytes = await file.read()

    # Validasi ukuran file
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ukuran file maksimal 10MB.")

    # FIX: sanitize profile key — kalau frontend kirim nilai aneh, fallback ke experienced
    profile_key = user_profile if user_profile in VALID_PROFILES else "experienced"

    # Extract teks dari PDF
    try:
        contract_text = extract_text_from_pdf(io.BytesIO(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # FIX: pakai profile_key (bukan user_profile langsung)
    result = analyze_contract(contract_text, profile_key=profile_key)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return JSONResponse(content=result)