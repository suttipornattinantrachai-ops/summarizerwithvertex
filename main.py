import json
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field
from google import genai

app = FastAPI(title="RPA AI Summarizer", version="1.0.0")

# -----------------------------
# Request/Response Schemas
# -----------------------------
class CustomerSales(BaseModel):
    name: str
    sales: float

class SummarizeRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    kpi: Dict[str, Any] = Field(..., description="Key-value KPI summary")
    top_customers: Optional[List[CustomerSales]] = None
    aging: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    table_preview_csv: Optional[str] = Field(
        None,
        description="Optional CSV snippet (e.g., first 50 rows) for anomaly hints"
    )

class Anomaly(BaseModel):
    type: str
    detail: str
    severity: str  # low|medium|high
    suggestion: str

class SummarizeResponse(BaseModel):
    email_subject: str
    email_body_th: str
    exec_bullets: List[str]
    anomalies: List[Anomaly]


# -----------------------------
# Helpers
# -----------------------------
def build_prompt(payload: SummarizeRequest) -> str:
    compact = {
        "date": payload.date,
        "kpi": payload.kpi,
        "top_customers": [c.model_dump() for c in (payload.top_customers or [])],
        "aging": payload.aging or {},
        "notes": payload.notes or "",
        "table_preview_csv": payload.table_preview_csv or ""
    }

    schema_hint = {
        "email_subject": "string",
        "email_body_th": "string (thai professional email)",
        "exec_bullets": ["string", "string"],
        "anomalies": [
            {"type": "string", "detail": "string", "severity": "low|medium|high", "suggestion": "string"}
        ]
    }

    return f"""
คุณเป็นนักวิเคราะห์รายงานประจำวันสำหรับผู้บริหาร
กติกา:
- ห้ามเดาตัวเลขที่ไม่มีใน input
- ถ้าข้อมูลไม่พอ ให้เขียนใน anomalies ว่า "insufficient_data" พร้อมระบุข้อมูลที่ต้องการ
- ตอบกลับเป็น JSON เท่านั้น (ห้ามมีข้อความนอก JSON)
- ใช้ภาษาไทยสุภาพ กระชับ ชัดเจน

INPUT(JSON):
{json.dumps(compact, ensure_ascii=False)}

OUTPUT SCHEMA (ตัวอย่างโครงสร้างเท่านั้น):
{json.dumps(schema_hint, ensure_ascii=False)}
""".strip()


def call_gemini(prompt: str) -> str:
    # Cloud Run จะใช้ Service Account ของ service ในการ auth กับ Vertex AI
    # ต้องตั้ง env vars:
    # - GOOGLE_CLOUD_PROJECT (หรือใช้ค่า default ของ runtime)
    # - GOOGLE_CLOUD_LOCATION (เช่น us-central1)
    #
    # SDK: google-genai
    client = genai.Client(vertexai=True)
    resp = client.models.generate_content(
        model=os.getenv("MODEL_NAME", "gemini-2.0-flash"),
        contents=prompt
    )
    return (resp.text or "").strip()


def safe_parse_json(text: str) -> Dict[str, Any]:
    cleaned = text.strip()

    # กันเคสโมเดลส่ง ```json ... ```
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).replace("JSON\n", "", 1)

    # ลอง parse ตรง ๆ ก่อน
    try:
        return json.loads(cleaned)
    except Exception:
        # ถ้าโมเดลหลุด ให้พยายามหา JSON object ภายในข้อความ
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def make_fallback(req: SummarizeRequest) -> SummarizeResponse:
    return SummarizeResponse(
        email_subject=f"Daily Summary - {req.date}",
        email_body_th=(
            "เรียนผู้บริหาร\n\n"
            "ระบบสรุปรายงานอัตโนมัติไม่สามารถสร้างข้อความสรุปได้ในรอบนี้ "
            "กรุณาดูไฟล์แนบ/ตัวเลข KPI ตามรายงาน\n\n"
            f"หมายเหตุ: {req.notes or '-'}\n\n"
            "ขอบคุณครับ"
        ),
        exec_bullets=["ไม่สามารถสร้างสรุปอัตโนมัติได้ในรอบนี้ โปรดดูไฟล์แนบ"],
        anomalies=[
            Anomaly(
                type="ai_error",
                detail="Failed to generate/parse AI response",
                severity="medium",
                suggestion="ตรวจสอบ log ของ API และลองรันใหม่"
            )
        ],
    )


# -----------------------------
# Routes
# -----------------------------
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/summarize_daily", response_model=SummarizeResponse)
def summarize_daily(req: SummarizeRequest):
    try:
        prompt = build_prompt(req)
        raw = call_gemini(prompt)
        data = safe_parse_json(raw)
        return SummarizeResponse.model_validate(data)
    except Exception:
        # ไม่โยน error เพื่อไม่ให้ RPA ล้มทั้งงาน
        return make_fallback(req)
