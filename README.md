# rpa-ai-summarizer (แบบที่ 1: Laiye ยิง API → API เรียก Vertex AI → คืน JSON)

โปรเจกต์นี้คือ API กลาง (Python + FastAPI) สำหรับรับ KPI/สรุปข้อมูลจาก RPA แล้วให้ Gemini บน Vertex AI สรุปเป็น JSON
เพื่อให้ RPA (เช่น Laiye) parse ได้ง่ายและส่งอีเมลต่อได้ทันที

## Endpoints
- `GET /health` ตรวจสุขภาพ
- `POST /summarize_daily` รับ JSON แล้วคืน JSON สรุป

## Env vars (สำคัญ)
- `GOOGLE_CLOUD_PROJECT` : Project ID
- `GOOGLE_CLOUD_LOCATION` : เช่น `us-central1`
- `MODEL_NAME` (optional) : default `gemini-2.0-flash`

## Run ในเครื่อง (ทดสอบก่อน)
1) สร้าง venv และติดตั้ง
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

2) ตั้งค่าฝั่ง Vertex AI (ถ้าทดสอบแบบเรียกจริงต้อง auth กับ GCP)
- วิธีง่ายสุด: ใช้ `gcloud auth application-default login` (ต้องติดตั้ง gcloud)
- และ set env:
```bash
set GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID
set GOOGLE_CLOUD_LOCATION=us-central1
```

3) รัน
```bash
uvicorn main:app --reload --port 8080
```

4) ทดสอบ
```bash
curl -X POST http://127.0.0.1:8080/summarize_daily -H "Content-Type: application/json" --data-binary @sample_payload.json
```

## Deploy ไป Cloud Run (แนวทาง)
- Build/Deploy จาก source ได้ (Console หรือ gcloud)
- ตั้ง Service account ของ Cloud Run ให้มีสิทธิ `Vertex AI User`
