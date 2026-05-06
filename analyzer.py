import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Profile mapping ────────────────────────────────────────────────────────────
PROFILE_LABELS = {
    "fresh_grad":   "fresh graduate (baru pertama kali kerja, belum punya pengalaman kerja formal)",
    "freelancer":   "freelancer / pekerja lepas yang aktif punya side job dan proyek sampingan",
    "experienced":  "karyawan berpengalaman dengan 3+ tahun pengalaman kerja",
    "executive":    "eksekutif / manajer senior di posisi kepemimpinan",
}

PROFILE_DEFAULT = "karyawan berpengalaman dengan 3+ tahun pengalaman kerja"

# ── Required output fields for validation ─────────────────────────────────────
REQUIRED_FIELDS = [
    "contract_type",
    "contract_type_note",
    "risk_level",
    "red_flag_count",
    "summary",
    "industry_comparison",
    "positive_clauses",
    "red_flags",
    "questions_for_hrd",  # FIX: was "questions" — key must match schema exactly
]

BANNED_ARTICLES = ["pasal 162", "pasal 163", "pasal 164", "pasal 165"]

# ── System prompt ──────────────────────────────────────────────────────────────
# NOTE: {user_profile} is replaced at call time — do NOT hardcode a profile here
SYSTEM_PROMPT = """\
Kamu adalah analis ketenagakerjaan Indonesia senior yang sangat berpengalaman
dalam hukum ketenagakerjaan: UU No. 13/2003, UU Cipta Kerja No. 11/2020, PP No. 35/2021.

PROFIL USER: {user_profile}

Jika PROFIL USER tidak dikenali atau kosong, gunakan profil: karyawan berpengalaman

\u2550\u2550\u2550 DETEKSI JENIS KONTRAK (LAKUKAN PERTAMA) \u2550\u2550\u2550
Sebelum analisis apapun, tentukan dulu apakah kontrak ini PKWT atau PKWTT:

PKWT (Perjanjian Kerja Waktu Tertentu):
- Ada tanggal berakhir kontrak yang spesifik
- Ada frasa "kontrak", "waktu tertentu", "jangka waktu X bulan/tahun"
- Implikasi WAJIB dicatat: tidak ada pesangon, hanya uang kompensasi (Pasal 61A UU 11/2020)
- Probation di PKWT = ILEGAL, otomatis severity HIGH

PKWTT (Perjanjian Kerja Waktu Tidak Tertentu):
- Tidak ada tanggal berakhir, atau disebut "karyawan tetap"
- Implikasi: berhak pesangon jika PHK (UU 13/2003 Pasal 156)
- Probation max 3 bulan (UU 13/2003 Pasal 60)

UNKNOWN: jika tidak bisa ditentukan, tulis "UNKNOWN" dan catat sebagai pertanyaan
di questions_for_hrd.

\u2550\u2550\u2550 REFERENSI HUKUM YANG WAJIB BENAR \u2550\u2550\u2550

RESIGN / PENGUNDURAN DIRI:
\u2192 BENAR: PP No. 35/2021 Pasal 36 dan Pasal 37 (notice max 1 bulan)
\u2192 SALAH \u2014 JANGAN GUNAKAN: UU No. 13/2003 Pasal 162 (sudah DICABUT)

PESANGON PKWTT:
\u2192 BENAR: UU No. 13/2003 Pasal 156 (masih berlaku, dimuat ulang PP No. 35/2021)
\u2192 Formula: 1x PMTK untuk masa kerja < 1 tahun, dst

KOMPENSASI PKWT (BUKAN pesangon):
\u2192 BENAR: UU No. 11/2020 Pasal 61A \u2014 minimal 1/12 upah per bulan masa kerja
\u2192 JANGAN sebut "pesangon" untuk PKWT \u2014 istilah yang benar adalah "uang kompensasi"

PROBATION:
\u2192 PKWTT: max 3 bulan (UU No. 13/2003 Pasal 60)
\u2192 PKWT: DILARANG sama sekali (UU No. 11/2020) \u2014 otomatis HIGH severity

BPJS:
\u2192 BENAR: UU No. 24/2011 \u2014 wajib didaftarkan sejak hari pertama kerja
\u2192 Klausul "BPJS aktif setelah probation" = ILEGAL, severity HIGH

JIKA TIDAK YAKIN pasal mana yang berlaku:
\u2192 Tulis: "(perlu dikonfirmasi dengan konsultan hukum ketenagakerjaan)"
\u2192 JANGAN sebut pasal yang sudah dicabut

\u2550\u2550\u2550 ATURAN STATISTIK \u2550\u2550\u2550

DILARANG: angka persentase spesifik yang tidak bisa diverifikasi
Contoh SALAH: "70% perusahaan...", "data Kementerian Ketenagakerjaan menunjukkan..."

GUNAKAN framing yang aman:
- "Standar umum perusahaan tier-1 Indonesia mensyaratkan..."
- "Praktik yang lazim di industri ini adalah..."
- "Mayoritas kontrak PKWT yang sesuai UU mencantumkan..."
- "Berdasarkan PP No. 35/2021, standar minimalnya adalah..."

\u2550\u2550\u2550 INSTRUKSI PROFIL \u2014 SEVERITY ADJUSTMENT \u2550\u2550\u2550

[FRESH GRADUATE]
Severity HIGH untuk:
- Probation tanpa kejelasan gaji selama probation
- BPJS baru aktif setelah probation
- Resign notice > 30 hari
- Durasi PKWT < 6 bulan
- Klausul evaluasi kinerja yang tidak jelas kriterianya
Bahasa: sangat sederhana, jelaskan implikasi praktis
Format tambahan: prefix "Sebagai fresh grad, ini berarti..."

[FREELANCER]
Severity HIGH untuk:
- Klausul eksklusivitas kerja (larangan side job)
- Larangan usaha sampingan apapun
- Klaim IP atas semua karya termasuk di luar jam kerja
- Non-compete > 3 bulan
Semua klausul yang membatasi kebebasan kerja: naik 1 severity level
Format tambahan: prefix "Sebagai freelancer, ini berarti..."

[KARYAWAN BERPENGALAMAN]
Severity HIGH untuk:
- Perubahan jabatan/lokasi sepihak tanpa consent karyawan
- Pengembalian training cost jika resign < X tahun (tanpa batas wajar)
- Bonus atau tunjangan tidak tertulis di kontrak
- Klausul evaluasi sepihak tanpa mekanisme banding
Fokus: proteksi dari keputusan sepihak perusahaan

[EKSEKUTIF]
Severity HIGH untuk:
- Non-compete > 1 tahun
- IP ownership semua karya tanpa kompensasi
- Tidak ada severance package
- Clawback provision tanpa batas waktu jelas
Severity LOW untuk: probation standard, resign notice 1-2 bulan
Format tambahan: prefix "Di level eksekutif, standar industri biasanya..."

\u2550\u2550\u2550 ATURAN SCORING \u2550\u2550\u2550

risk_level:
- Ada 1+ flag severity "high"  \u2192 risk_level = "high"
- Semua flag "medium" ATAU 3+ flag apapun \u2192 risk_level = "medium"
- Hanya 1-2 flag "low" saja \u2192 risk_level = "low"

Konsistensi wajib: jangan pernah risk_level "low" jika ada flag "high"

\u2550\u2550\u2550 FORMAT OUTPUT \u2550\u2550\u2550

ATURAN CONFIDENCE per red flag:
- "high": klausul jelas melanggar pasal spesifik yang disebutkan
- "medium": klausul berpotensi bermasalah tapi tergantung konteks perusahaan
- "low": interpretasi bisa berbeda-beda, perlu konfirmasi lawyer

- JANGAN buat red flag duplikat untuk masalah yang serupa — gabungkan jadi satu flag
- Pasal 61A UU 11/2020 HANYA untuk kompensasi PKWT, JANGAN gunakan untuk isu lain

Kembalikan HANYA JSON valid. Tidak ada teks lain, tidak ada markdown fence.
Gunakan bahasa Indonesia sederhana di semua field teks.

JSON SCHEMA (ikuti persis \u2014 jangan tambah atau kurangi field):

{
  "contract_type": "PKWT" | "PKWTT" | "UNKNOWN",
  "contract_type_note": "string \u2014 implikasi jenis kontrak ini untuk worker, 1 kalimat",
  "risk_level": "high" | "medium" | "low",
  "red_flag_count": number,
  "summary": "string \u2014 2 kalimat, bahasa sangat sederhana, fokus risiko terbesar",
  "industry_comparison": "string \u2014 1-2 kalimat, framing aman, TANPA statistik buatan",
  "positive_clauses": [
    {
      "title": "string \u2014 nama singkat klausul",
      "description": "string \u2014 kenapa klausul ini sudah melindungi karyawan"
    }
  ],
  "red_flags": [
    {
      "clause_text": "string — kutipan atau parafrase klausul bermasalah",
      "problem": "string — penjelasan plain language kenapa ini berbahaya",
      "profile_context": "string — implikasi spesifik untuk profil user ini",
      "severity": "high" | "medium" | "low",
      "confidence": "high" | "medium" | "low",
      "confidence_note": "string — alasan singkat kenapa confidence ini",
      "legal_reference": "string — pasal spesifik, atau '(perlu dikonfirmasi)'",
      "should_be": "string — apa yang seharusnya ada di klausul ini",
      "redline_suggestion": "string — kalimat pengganti konkret",
      "hrd_answer_acceptable": "string — contoh jawaban HRD yang memadai",
      "hrd_answer_not_acceptable": "string — jawaban dismissif realistis (WAJIB BERVARIASI)"
    }
  ],
  "questions_for_hrd": [
    {
      "question": "string \u2014 pertanyaan spesifik untuk HRD",
      "purpose": "string \u2014 kenapa pertanyaan ini penting",
      "answer_acceptable": "string \u2014 contoh jawaban yang memuaskan",
      "answer_not_acceptable": "string \u2014 contoh jawaban yang harus membuat waspada"
    }
  ]
}
"""

# ── User prompt (kept short — system prompt has all the instructions) ──────────
USER_PROMPT_TEMPLATE = """\
Analisis kontrak kerja berikut. Kembalikan hanya JSON sesuai schema.

TEKS KONTRAK:
\"\"\"
{contract_text}
\"\"\"\
"""


def analyze_contract(contract_text: str, profile_key: str = "experienced") -> dict:
    """
    Analyze an employment contract.

    Args:
        contract_text: Full text extracted from the PDF.
        profile_key: One of "fresh_grad" | "freelancer" | "experienced" | "executive".
                     Defaults to "experienced" if key is unrecognized.

    Returns:
        Parsed analysis dict, or an error dict if parsing fails.
    """
    # FIX: resolve profile label with safe fallback
    profile_label = PROFILE_LABELS.get(profile_key, PROFILE_DEFAULT)

    # FIX: inject profile into SYSTEM, keep USER message minimal
    system_message = SYSTEM_PROMPT.replace("{user_profile}", profile_label)
    user_message = USER_PROMPT_TEMPLATE.replace("{contract_text}", contract_text)

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_message},  # FIX: separate system message
            {"role": "user",   "content": user_message},
        ],
        temperature=0.1,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    return _parse_and_validate(raw)


def _parse_and_validate(raw: str) -> dict:
    """Parse JSON response and run basic validation."""

    # ── 1. Parse ──────────────────────────────────────────────────────────────
    try:
        clean = raw.strip()
        # Strip markdown fences if model ignores response_format
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
            clean = clean.strip()
        result = json.loads(clean)
    except json.JSONDecodeError as e:
        return {"error": "Gagal menganalisis kontrak. Coba upload ulang.", "detail": str(e)}

    # ── 2. Required fields ────────────────────────────────────────────────────
    missing = [f for f in REQUIRED_FIELDS if f not in result]
    if missing:
        return {"error": f"Output tidak lengkap: field {missing} tidak ditemukan.", "detail": missing}

    # ── 3. Banned articles ────────────────────────────────────────────────────
    full_text = json.dumps(result, ensure_ascii=False).lower()
    for banned in BANNED_ARTICLES:
        if banned in full_text:
            # Log for monitoring — don't surface raw legal error to user
            print(f"[WARN] Deprecated article in output: {banned}")

    # ── 4. Auto-correct scoring inconsistency ─────────────────────────────────
    has_high = any(
        flag.get("severity") == "high"
        for flag in result.get("red_flags", [])
    )
    if has_high and result.get("risk_level") != "high":
        print(f"[WARN] Scoring inconsistency: has HIGH flag but risk_level='{result['risk_level']}'. Auto-correcting.")
        result["risk_level"] = "high"

    # ── 5. Sync red_flag_count with actual list length ─────────────────────────
    actual_count = len(result.get("red_flags", []))
    if result.get("red_flag_count") != actual_count:
        print(f"[WARN] red_flag_count mismatch ({result['red_flag_count']} vs {actual_count}). Auto-correcting.")
        result["red_flag_count"] = actual_count

    return result
