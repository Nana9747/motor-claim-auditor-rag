import os
import sys
from dotenv import load_dotenv
from src.pdf_extractor import parse_surveyor_pdf
from src.auditor_agent import audit_claim_assessment, draft_dispute_letter

load_dotenv()

def main():
    print("=" * 70)
    print("      AUTOMATED VEHICLE CLAIM AUDITOR & EXPLAINER (RAG-POWERED)      ")
    print("=" * 70)

    pdf_path = os.path.join("data", "sample_claim.pdf")
    if not os.path.exists(pdf_path):
        print(f"\n[Error] PDF file not found at: {pdf_path}")
        print("Please ensure your sample PDF exists in the 'data' folder before running.")
        sys.exit(1)

    # 1. Extraction Phase
    print(f"\n[1/3] Reading and extracting data from: {pdf_path}...")
    try:
        assessment = parse_surveyor_pdf(pdf_path)
        print("      Extraction complete!")
        print(f"      - Insurer:     {assessment.insurer_name}")
        print(f"      - Policy No:   {assessment.policy_number}")
        print(f"      - Claim No:    {assessment.claim_number}")
        print(f"      - Vehicle Reg: {assessment.vehicle_number}")
        print(f"      - Zero-Dep:    {'Active (Yes)' if assessment.has_zero_dep else 'No'}")
        print(f"      - Line Items:  {len(assessment.parts)} replacement parts detected")
    except Exception as e:
        print(f"[Error during extraction]: {e}")
        sys.exit(1)

    # 2. Auditing Phase (Deterministic Rules + RAG Retrieval)
    print("\n[2/3] Querying regulatory knowledge base and auditing deductions...")
    try:
        audit_report, rules_result = audit_claim_assessment(assessment)
        print("      Audit complete!")
        print(f"      - Overall Verdict:    {audit_report.overall_verdict}")
        print(f"      - Total Claimed:      INR {rules_result.total_claimed:,.2f}")
        print(f"      - Approved by Insurer: INR {rules_result.total_approved:,.2f}")
        print(f"      - Total Shortfall:    INR {rules_result.total_shortfall:,.2f}")
        print(f"      - Recoverable Unfair: INR {rules_result.recoverable_unfair_amount:,.2f}")
        print(f"      - Legitimate Cuts:    INR {rules_result.legitimate_statutory_amount:,.2f}")
    except Exception as e:
        print(f"[Error during auditing]: {e}")
        sys.exit(1)

    # 3. Dispute Drafting Phase
    print("\n[3/3] Generating formal representation letter...")
    try:
        dispute_letter = draft_dispute_letter(assessment, audit_report, rules_result)
        print("\n" + "=" * 70)
        print("                   FORMAL CLAIM DISPUTE LETTER                   ")
        print("=" * 70)
        print(dispute_letter)
        print("=" * 70)
    except Exception as e:
        print(f"[Error drafting letter]: {e}")

if __name__ == "__main__":
    main()