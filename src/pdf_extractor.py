import os
from dotenv import load_dotenv
from pypdf import PdfReader
from langchain_google_genai import ChatGoogleGenerativeAI
from src.schemas import ClaimAssessment
from langchain_groq import ChatGroq

load_dotenv()

# Dedicated extraction model
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.0
)

# Enforce strict parsing into our ClaimAssessment schema
structured_extractor = llm.with_structured_output(ClaimAssessment)

def extract_text_from_pdf(pdf_path: str) -> str:
    """Reads all pages from an insurance assessment PDF and extracts text."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Assessment PDF not found at path: {pdf_path}")
    
    reader = PdfReader(pdf_path)
    extracted_text = []
    
    for idx, page in enumerate(reader.pages):
        page_text = page.extract_text()
        if page_text:
            extracted_text.append(f"--- PAGE {idx + 1} ---\n{page_text}")
            
    return "\n\n".join(extracted_text)

def parse_surveyor_pdf(pdf_path: str) -> ClaimAssessment:
    """
    Ingests official insurance surveyor PDF and maps it
    directly into a structured ClaimAssessment object.
    """
    raw_document_text = extract_text_from_pdf(pdf_path)
    
    prompt = f"""
    You are an expert insurance document parser.
    Extract all relevant claim assessment data from this official insurance surveyor sheet.

    Document Content:
    \"\"\"
    {raw_document_text}
    \"\"\"

    Instructions:
    1. Extract the Insurer Name, Policy Number, Claim Number, and Vehicle Registration Number.
    2. Check the Policy Type and Add-on sections carefully: set `has_zero_dep` to True if Zero-Depreciation / Nil-Depreciation cover is mentioned as active; otherwise False.
    3. Extract every line item in the parts replacement section: include part name, material classification (plastic, glass, rubber, fiber, metal), claimed cost, approved cost, depreciation deducted, and any surveyor remarks.
    4. Extract labor claimed, labor approved, compulsory excess, and the final net payable amount.
    """

    assessment: ClaimAssessment = structured_extractor.invoke(prompt)
    return assessment