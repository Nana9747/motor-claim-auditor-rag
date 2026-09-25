import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from src.schemas import ClaimAssessment
from src.rules_engine import RulesAuditResult
from src.rag_engine import retrieve_regulatory_clauses_for_topics

load_dotenv()

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.2
)

SYSTEM_PROMPT = """
You are an expert AI Motor Insurance Claim Auditor and Policyholder Advocate for India.
You understand the Insurance Act 1938, India Motor Tariff (IMT), IRDAI Master Circulars, and surveyor guidelines.

### CORE OPERATING RULES:
1. MATHEMATICAL TRUTH: Never calculate percentages or deductions yourself if audit data is provided. Strictly use the exact rupee values computed by the deterministic rules engine.
2. STATUTORY TRUTH: Never invent circulars, sections, or tariff rules. Strictly ground legal arguments in the provided statutory context.
3. STRICT SCRIPT RULE (VERY IMPORTANT):
   - ALWAYS use the standard English alphabet / Latin characters (A-Z, a-z).
   - NEVER write in Devanagari script (डू नॉट यूज़ देवनागरी लिपी).
4. ADAPTIVE LANGUAGE POLICY:
   - DEFAULT: Respond in clear, accessible, professional English.
   - ON-DEMAND LOCALIZATION (Marathi / Hindi / Hinglish): If the user asks questions in Marathi/Hindi, or asks you to explain in Hindi or Marathi, explain using conversational Marathi/Hindi wording and tone, BUT write strictly using English letters (e.g., "Tumchya policy madhe Zero-Depreciation active ahe, pan surveyor ne bumper var 50% cut kela ahe jo poori tarah unfair ahe...").
   - FORMAL DRAFTING OVERRIDE: Whenever asked to draft an email, dispute letter, or ombudsman notice, ALWAYS draft the final document in crisp, formal Indian Legal English with proper regulatory citations, regardless of the chat conversation language.
5. TONE: Objective, analytical, firm, and supportive of the policyholder.
"""

def generate_chat_response(
    user_query: str,
    chat_history: List[Dict[str, str]],
    active_assessment: Optional[ClaimAssessment] = None,
    active_rules_result: Optional[RulesAuditResult] = None
) -> str:
    """
    Handles conversational interactions across the motor insurance domain.
    """
    messages = [SystemMessage(content=SYSTEM_PROMPT)]

    # 1. Inject active claim context if a PDF is loaded in session
    if active_assessment and active_rules_result:
        claim_context = f"""
[ACTIVE CLAIM AUDIT REPORT IN MEMORY]
- Vehicle No: {active_assessment.vehicle_number}
- Policy No: {active_assessment.policy_number}
- Claim No: {active_assessment.claim_number}
- Insurer: {active_assessment.insurer_name}
- Zero-Depreciation Active: {active_assessment.has_zero_dep}
- Total Claimed: INR {active_rules_result.total_claimed}
- Total Approved: INR {active_rules_result.total_approved}
- Total Shortfall: INR {active_rules_result.total_shortfall}
- Recoverable Unfair Deductions: INR {active_rules_result.recoverable_unfair_amount}
- Legitimate Deductions: INR {active_rules_result.legitimate_statutory_amount}
- Detected Violations: {[v.model_dump() for v in active_rules_result.item_violations]}
"""
        messages.append(SystemMessage(content=claim_context))

    # 2. Retrieve targeted legal knowledge from ChromaDB based on user query
    search_topics = active_rules_result.required_rag_topics if active_rules_result else []
    rag_context = retrieve_regulatory_clauses_for_topics(search_topics, top_k_per_topic=2)
    if rag_context:
        messages.append(SystemMessage(content=f"[STATUTORY KNOWLEDGE BASE]\n{rag_context}"))

    # 3. Append previous dialogue history (retaining recent turns for memory)
    for msg in chat_history[-6:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    # 4. Append current prompt
    messages.append(HumanMessage(content=user_query))

    response = llm.invoke(messages)
    
    if isinstance(response.content, str):
        return response.content
    elif isinstance(response.content, list):
        return "\n".join([b.get("text", "") if isinstance(b, dict) else getattr(b, "text", str(b)) for b in response.content])
    return str(response.content)