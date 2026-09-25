import os
import streamlit as st
from src.pdf_extractor import parse_surveyor_pdf
from src.auditor_agent import audit_claim_assessment, draft_dispute_letter
from src.chatbot_engine import generate_chat_response

st.set_page_config(
    page_title="IRDAI Motor Claim Auditor AI",
    page_icon="🚗",
    layout="wide"
)

# Initialize Session State
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "assessment" not in st.session_state:
    st.session_state.assessment = None
if "rules_result" not in st.session_state:
    st.session_state.rules_result = None
if "audit_report" not in st.session_state:
    st.session_state.audit_report = None

# Sidebar - Document Upload & Claim Analytics
with st.sidebar:
    st.title("🚗 Claim Control Desk")
    st.caption("Deterministic Rules Engine + IRDAI RAG Law")
    
    uploaded_file = st.file_uploader("Upload Surveyor Assessment (PDF)", type=["pdf"])
    
    if uploaded_file is not None:
        if st.session_state.assessment is None:
            with st.spinner("Extracting & running deterministic rules audit..."):
                os.makedirs("data", exist_ok=True)
                temp_path = os.path.join("data", "uploaded_claim.pdf")
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                try:
                    assessment = parse_surveyor_pdf(temp_path)
                    audit_rep, rules_res = audit_claim_assessment(assessment)
                    st.session_state.assessment = assessment
                    st.session_state.audit_report = audit_rep
                    st.session_state.rules_result = rules_res
                    st.success("Audit completed successfully!")
                except Exception as e:
                    st.error(f"Error processing file: {e}")

    # Display live metrics when an active claim is loaded
    if st.session_state.rules_result:
        res = st.session_state.rules_result
        st.markdown("---")
        st.subheader("Financial Breakdown")
        st.metric("Total Claimed", f"INR {res.total_claimed:,.2f}")
        st.metric("Approved by Insurer", f"INR {res.total_approved:,.2f}")
        st.metric(
            "Recoverable Unfair Cut",
            f"INR {res.recoverable_unfair_amount:,.2f}",
            delta="Actionable Discrepancy",
            delta_color="inverse"
        )
        
        st.markdown("---")
        if st.button("📄 Generate Formal Dispute Letter"):
            with st.spinner("Drafting legal notice..."):
                letter = draft_dispute_letter(
                    st.session_state.assessment,
                    st.session_state.audit_report,
                    st.session_state.rules_result
                )
                st.session_state.chat_history.append({"role": "assistant", "content": letter})
                st.rerun()

# Main Chat Interface
st.title("Motor Insurance Claim Audit & Dispute Assistant")
st.caption("Ask questions about IRDAI regulations, IMT rules, or your uploaded assessment in English, Hindi, or Marathi.")

# Render Chat History
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Prompt Input
if prompt := st.chat_input("Ask a question, request an explanation in Hindi/Marathi, or dispute an item..."):
    # Render user query
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate Agent response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing regulations and audit data..."):
            reply = generate_chat_response(
                user_query=prompt,
                chat_history=st.session_state.chat_history,
                active_assessment=st.session_state.assessment,
                active_rules_result=st.session_state.rules_result
            )
            st.markdown(reply)
            st.session_state.chat_history.append({"role": "assistant", "content": reply})