from fastapi import FastAPI, UploadFile, File,Request
from pydantic import BaseModel
import fitz
import google.generativeai as genai
from dotenv import load_dotenv
import os
import tempfile
import requests
import json
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")

@app.get("/")
def home():
    return {"status": "working"}


class PDFUrlRequest(BaseModel):
    pdf_url: str
    language: str


def extract_text_from_pdf(pdf_path):
    text = ""

    doc = fitz.open(pdf_path)

    for page in doc:
        text += page.get_text()

    doc.close()

    return text


def generate_summary(text):
    prompt = f"""
You are a medical lab report summarizer.

Return ONLY valid JSON.

{{
    "english": "WhatsApp-friendly English summary",
    "malayalam": "WhatsApp-friendly Malayalam summary",
    "status": "NORMAL or HIGH or LOW or ATTENTION"
}}

Rules:
- Use simple language
- Maximum 100 words
- Use emojis
- Do not diagnose diseases
- Do not prescribe medicines
- Mention only important values
- Add disclaimer
- Return only JSON
- Do not use markdown
- Do not wrap response in ```json

Lab Report:
{text[:15000]}
"""

    response = model.generate_content(prompt)

    clean_text = response.text.strip()
    clean_text = clean_text.replace("```json", "")
    clean_text = clean_text.replace("```", "")
    clean_text = clean_text.strip()

    return json.loads(clean_text)


@app.post("/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...)):

    if not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files allowed"}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(await file.read())
        pdf_path = temp_file.name

    try:
        text = extract_text_from_pdf(pdf_path)

        if len(text.strip()) < 20:
            return {"error": "No readable text found in PDF"}

        data = generate_summary(text)

        return {
            "success": True,
            "english": data["english"],
            "malayalam": data["malayalam"],
            "status": data["status"]
        }

    except Exception as e:
        return {"error": str(e)}


@app.post("/analyze-pdf-url")
async def analyze_pdf_url(request: PDFUrlRequest):

    try:
        response = requests.get(request.pdf_url, timeout=30)

        if response.status_code != 200:
            return {"error": "Unable to download PDF"}

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(response.content)
            pdf_path = temp_file.name

        text = extract_text_from_pdf(pdf_path)

        if len(text.strip()) < 20:
            return {"error": "No readable text found in PDF"}

        data = generate_summary(text)

        if request.language.lower() == "english":
            return {
                "success": True,
                "summary": data["english"],
                "status": data["status"]
            }

        return {
            "success": True,
            "summary": data["malayalam"],
            "status": data["status"]
        }

    except Exception as e:
        return {"error": str(e)}
SALEGROWY_TOKEN = os.getenv("SALEGROWY_TOKEN")

VENDOR_UID = "8c423097-9d41-4aa8-b259-e000c8c8ec6d"

SEND_URL = (
    f"https://app.salegrowy.com/api/"
    f"{VENDOR_UID}/contact/send-message"
    f"?token={SALEGROWY_TOKEN}"
)


def send_whatsapp_message(phone_number, message):

    payload = {
        "phone_number": phone_number,
        "message_body": message
    }

    response = requests.post(
        SEND_URL,
        json=payload,
        timeout=30
    )

    print("SEND STATUS:", response.status_code)
    print("SEND RESPONSE:", response.text)

    return response.text
@app.post("/webhook-english")
async def webhook_english(request: Request):
    return await process_pdf(request, "english")

@app.post("/webhook-malayalam")
async def webhook_malayalam(request: Request):
    return await process_pdf(request, "malayalam")

@app.post("/webhook")
async def webhook(request: Request):

    try:
        data = await request.json()

        print("=" * 50)
        print(json.dumps(data, indent=2))
        print("=" * 50)

        media = data.get("message", {}).get("media")

        if not media:
            return {"success": True}

        if media.get("type") != "document":
            return {"success": True}

        if media.get("mime_type") != "application/pdf":
            return {"success": True}

        pdf_url = media.get("link")

        response = requests.get(pdf_url, timeout=60)

        if response.status_code != 200:
            return {"error": "Unable to download PDF"}

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(response.content)
            pdf_path = temp_file.name

        text = extract_text_from_pdf(pdf_path)

        if len(text.strip()) < 20:
            return {"error": "No readable text found"}

        summary_data = generate_summary(text)

        print("SUMMARY:")
        print(summary_data)
        phone = data["contact"]["phone_number"]

        language = data["contact"].get("language_code")

        print("LANGUAGE =", language)

        if language and language.lower() == "malayalam":
            summary_text = summary_data["malayalam"]
        else:
            summary_text = summary_data["english"]

        message = (
            f"📋 Lab Report Summary\n\n"
            f"{summary_text}\n\n"
            f"Status: {summary_data['status']}"
        )

        send_whatsapp_message(phone, message)

        return {
            "success": True,
            "summary": summary_data
        }

    except Exception as e:
        print("WEBHOOK ERROR:", str(e))
        return {"error": str(e)}


async def process_pdf(request: Request, language: str):

    data = await request.json()

    media = data.get("message", {}).get("media")

    if not media:
        return {"success": True}

    if media.get("type") != "document":
        return {"success": True}

    pdf_url = media.get("link")

    response = requests.get(pdf_url, timeout=60)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(response.content)
        pdf_path = temp_file.name

    text = extract_text_from_pdf(pdf_path)

    summary_data = generate_summary(text)

    phone = data["contact"]["phone_number"]

    if language == "malayalam":
        summary_text = summary_data["malayalam"]
    else:
        summary_text = summary_data["english"]

    message = (
        f"📋 Lab Report Summary\n\n"
        f"{summary_text}\n\n"
        f"Status: {summary_data['status']}"
    )

    send_whatsapp_message(phone, message)

    return {"success": True}