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


@app.post("/webhook")
async def webhook(request: Request):

    body = await request.body()

    print("=" * 50)
    print("RAW BODY:")
    print(body)
    print("=" * 50)

    try:
        if body:
            data = json.loads(body)
            print("JSON DATA:")
            print(json.dumps(data, indent=2))
    except Exception as e:
        print("NOT JSON:", str(e))

    return {"success": True}