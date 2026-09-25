from typing import List, Optional
from pydantic import BaseModel, Field

# Represents a single replaced part or repair item from the PDF
class LineItem(BaseModel):
    part_name: str = Field(description="Name or description of the part")
    material: str = Field(description="Material type: plastic, glass, rubber, metal, or fiber")
    estimated_cost: float = Field(description="Amount estimated/claimed by workshop")
    approved_cost: float = Field(description="Amount approved by the insurance surveyor")
    depreciation_deducted: float = Field(default=0.0, description="Depreciation amount subtracted")
    remarks: Optional[str] = Field(default="", description="Surveyor's justification or remarks")

# Extracted metadata and high-level totals from the assessment PDF
class ClaimAssessment(BaseModel):
    insurer_name: str = Field(description="Name of the insurance company")
    policy_number: str = Field(description="Policy number")
    claim_number: str = Field(description="Claim reference number")
    vehicle_number: str = Field(description="Vehicle registration number")
    has_zero_dep: bool = Field(description="True if Zero-Depreciation add-on is active, False otherwise")
    compulsory_excess: float = Field(default=1000.0, description="Compulsory deductible amount applied")
    parts: List[LineItem] = Field(description="List of all replacement parts assessed")
    labor_claimed: float = Field(default=0.0, description="Total labor claimed")
    labor_approved: float = Field(default=0.0, description="Total labor approved")
    net_payable_approved: float = Field(description="Final net amount payable to the garage/insured")

# Individual item analysis after cross-referencing with RAG rules
class ItemAudit(BaseModel):
    item_name: str = Field(description="Part or charge name")
    amount_cut: float = Field(description="Total reduction on this item")
    is_valid_deduction: bool = Field(description="True if deduction complies with rules/policy, False if unfair")
    explanation_simple: str = Field(description="Plain-English explanation without confusing jargon")

# Final audit result explaining the entire claim to the garage owner
class ClaimAuditReport(BaseModel):
    total_claimed: float
    total_approved: float
    total_shortfall: float
    overall_verdict: str = Field(description="'Compliant' if all cuts are legally valid, or 'Dispute Recommended'")
    summary_explanation: str = Field(description="High-level plain English summary of what happened to the claim")
    items_breakdown: List[ItemAudit] = Field(description="Line-by-line explanation of every deduction")
    statutory_rules_applied: List[str] = Field(description="Relevant IRDAI / IMT sections or policy conditions referenced")
    action_advice: str = Field(description="Clear next steps for the garage owner")

class ItemRuleViolation(BaseModel):
    item_name: str
    material: str
    amount_claimed: float
    amount_approved: float
    amount_deducted: float
    statutory_allowable_cut: float
    unfair_deduction: float
    violation_code: str
    rag_topic_needed: str
    reason: str

class TATDelayViolation(BaseModel):
    delay_type: str
    statutory_limit_days: int
    actual_days: int
    days_delayed: int
    penal_interest_rate_pct: float
    penal_interest_amount: float
    rag_topic_needed: str

class RulesAuditResult(BaseModel):
    total_claimed: float
    total_approved: float
    total_shortfall: float
    recoverable_unfair_amount: float
    legitimate_statutory_amount: float
    has_unfair_cuts: bool
    item_violations: List[ItemRuleViolation]
    tat_violations: List[TATDelayViolation]
    required_rag_topics: List[str]    