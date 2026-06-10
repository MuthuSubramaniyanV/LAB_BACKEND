from fastapi import FastAPI, UploadFile, File
import fitz
import google.generativeai as genai
from dotenv import load_dotenv
import os
import tempfile

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")

app = FastAPI()


@app.get("/")
def home():
    return {"status": "working"}


@app.post("/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...)):

    if not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files allowed"}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(await file.read())
        pdf_path = temp_file.name

    text = ""

    try:
        doc = fitz.open(pdf_path)

        for page in doc:
            text += page.get_text()

        doc.close()

    except Exception as e:
        return {"error": f"PDF extraction failed: {str(e)}"}

    if len(text.strip()) < 20:
        return {"error": "No readable text found in PDF"}

    prompt = f"""
    Summarize this lab report.

    Return:
    1. Key findings
    2. Abnormal values
    3. Important observations

    Do not diagnose diseases.
    Do not prescribe medicines.

    Lab Report:
    {text[:15000]}
    """

    try:
        response = model.generate_content(prompt)

        return {
            "success": True,
            "summary": response.text
        }

    except Exception as e:
        return {"error": f"Gemini failed: {str(e)}"}