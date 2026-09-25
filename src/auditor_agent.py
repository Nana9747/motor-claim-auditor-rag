import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from src.schemas import ClaimAssessment, ClaimAuditReport, ItemAudit
from src.rules_engine import run_deterministic_rules_audit, RulesAuditResult
from src.rag_engine import retrieve_regulatory_clauses_for_topics

load_dotenv()

# Active Groq model configuration
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.0
)
structured_auditor = llm.with_structured_output(ClaimAuditReport)

def _extract_text(content: Any) -> str:
    """Helper to extract clean string from LLM responses."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
            elif hasattr(block, "text"):
                text_parts.append(block.text)
            elif isinstance(block, str):
                text_parts.append(block)
        return "\n".join(text_parts)
    return str(content)

def audit_claim_assessment(assessment: ClaimAssessment) -> tuple[ClaimAuditReport, RulesAuditResult]:
    """
    Module 3 Agent Orchestration:
    1. Executes Deterministic Rules Engine (No LLM math).
    2. Fetches verified statutory clauses using targeted RAG topics.
    3. Synthesizes findings without inventing new rules or calculations.
    """
    # 1. Deterministic evaluation
    rules_result: RulesAuditResult = run_deterministic_rules_audit(
        assessment=assessment,
        vehicle_age_months=12,
        engine_cc=1200
    )

    # 2. Targeted RAG retrieval based on rule violations
    regulatory_context = retrieve_regulatory_clauses_for_topics(
        topics=rules_result.required_rag_topics,
        top_k_per_topic=2
    )

    # 3. Agent Synthesis Prompt
    prompt = f"""
    You are an expert vehicle claim auditor representing an authorized workshop and car owner.
    Analyze the claim settlement using ONLY the provided verified facts and statutory ground truth.
    Do NOT recalculate figures or invent rules. Use the exact calculations provided below.

    CLAIM ASSESSMENT OVERVIEW:
    - Insurer: {assessment.insurer_name}
    - Policy No: {assessment.policy_number}
    - Claim No: {assessment.claim_number}
    - Vehicle Registration: {assessment.vehicle_number}
    - Zero-Depreciation Active: {assessment.has_zero_dep}

    DETERMINISTIC RULES ENGINE AUDIT (VERIFIED NUMBERS):
    - Total Claimed: INR {rules_result.total_claimed}
    - Total Approved: INR {rules_result.total_approved}
    - Total Shortfall: INR {rules_result.total_shortfall}
    - Recoverable Unfair Deductions: INR {rules_result.recoverable_unfair_amount}
    - Legitimate Deductions: INR {rules_result.legitimate_statutory_amount}
    - Has Unfair Cuts: {rules_result.has_unfair_cuts}

    VIOLATIONS DETECTED:
    {[v.model_dump() for v in rules_result.item_violations]}

    STATUTORY GROUND TRUTH (FROM RAG KNOWLEDGE BASE):
    --------------------------------------------------
    {regulatory_context}
    --------------------------------------------------

    TASK INSTRUCTIONS:
    1. Explain every line-item deduction in plain language suitable for the car owner.
    2. Map each identified violation to the relevant statutory clause cited in the RAG context.
    3. Check surveyor remarks: if a deduction lacks technical justification or photo evidence, highlight it as an evidentiary defect.
    4. Provide the overall verdict:
       - 'Dispute Recommended' if recoverable unfair deductions > 0.
       - 'Compliant' if all cuts are legitimate.
    5. Maintain strict consistency with the rules engine's financial totals.
    """

    audit_report: ClaimAuditReport = structured_auditor.invoke(prompt)
    return audit_report, rules_result

def draft_dispute_letter(
    assessment: ClaimAssessment, 
    audit_report: ClaimAuditReport, 
    rules_result: RulesAuditResult
) -> str:
    """
    Generates a formal legal representation email to the insurer/surveyor.
    """
    violations = [v.model_dump() for v in rules_result.item_violations]

    prompt = f"""
    You are an insurance dispute specialist drafting a formal objection email to {assessment.insurer_name}.
    Cite the verified violations and statutory clauses provided. Do not invent external numbers or rules.

    VEHICLE & POLICY DETAILS:
    - Vehicle No: {assessment.vehicle_number}
    - Policy No: {assessment.policy_number}
    - Claim No: {assessment.claim_number}
    - Insurer: {assessment.insurer_name}
    - Zero-Depreciation Endorsement: {'Active' if assessment.has_zero_dep else 'Inactive'}

    FINANCIAL SUMMARY:
    - Claimed: INR {rules_result.total_claimed}
    - Approved: INR {rules_result.total_approved}
    - Disputed Over-Deductions: INR {rules_result.recoverable_unfair_amount}

    DISPUTED LINE ITEMS:
    {violations}

    STATUTORY CITATIONS:
    {audit_report.statutory_rules_applied}

    DRAFTING REQUIREMENTS:
    1. Formal subject line including Claim Reference and Vehicle Registration.
    2. Addressed to the Claims Surveyor and Grievance Redressal Officer.
    3. Clear breakdown table of disputed cuts with relevant regulatory citations (IRDAI Master Circular 2024 / IMT Section 1).
    4. Explicit note regarding absence of technical justifications or photo evidence where applicable.
    5. Formal request for revised disbursement within 7 working days, referencing statutory turnaround limits.
    """

    response = llm.invoke(prompt)
    return _extract_text(response.content)