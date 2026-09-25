from datetime import datetime, date
from typing import List, Optional, Set, Tuple
# To this:
from src.schemas import (
    ClaimAssessment, 
    ItemRuleViolation, 
    TATDelayViolation, 
    RulesAuditResult
)   

# Standard RBI Bank Rate baseline for statutory penal interest (Bank Rate + 2%)
DEFAULT_RBI_BANK_RATE_PCT = 5.50

def get_metal_depreciation_rate(age_in_months: int) -> float:
    """
    India Motor Tariff (IMT) Section 1 Rule 3 Metal Depreciation Slabs.
    """
    if age_in_months <= 6:
        return 0.0
    elif age_in_months <= 12:
        return 0.05
    elif age_in_months <= 24:
        return 0.10
    elif age_in_months <= 36:
        return 0.15
    elif age_in_months <= 48:
        return 0.25
    elif age_in_months <= 60:
        return 0.35
    elif age_in_months <= 120:
        return 0.40
    else:
        return 0.50

def calculate_statutory_depreciation_rate(material: str, has_zero_dep: bool, vehicle_age_months: int = 12) -> tuple[float, str]:
    """
    Calculates statutory depreciation rate and identifies applicable RAG topic.
    Returns: (rate: float, rag_topic: str)
    """
    mat = material.strip().lower()

    # Rule 1: Zero-Depreciation endorsement waives all depreciation
    if has_zero_dep:
        return 0.0, "zero_depreciation_waiver"

    # Rule 2: Glass is strictly 0% under all standard tariffs
    if "glass" in mat or "windshield" in mat:
        return 0.0, "depreciation_glass"

    # Rule 3: Rubber, Nylon, Plastic, Tyres, Batteries = 50%
    if any(k in mat for k in ["plastic", "rubber", "nylon", "tyre", "battery", "airbag"]):
        return 0.50, "depreciation_rubber_plastic"

    # Rule 4: Fiberglass = 30%
    if "fiber" in mat:
        return 0.30, "depreciation_fiberglass"

    # Rule 5: Metal parts based on vehicle age slab
    if "metal" in mat or "sheet" in mat or "steel" in mat:
        return get_metal_depreciation_rate(vehicle_age_months), "depreciation_metal_parts"

    # Default fallback to 0% if unspecified to avoid ungrounded deductions
    return 0.0, "claim_deduction_fair_practice"

def audit_compulsory_excess(engine_cc: int, excess_deducted: float, is_two_wheeler: bool = False) -> tuple[float, float, Optional[str]]:
    """
    India Motor Tariff Compulsory Deductible Audit.
    Returns: (statutory_allowed_excess, unfair_overcharge, rag_topic)
    """
    if is_two_wheeler:
        allowed = 100.0
    elif engine_cc <= 1500:
        allowed = 1000.0
    else:
        allowed = 2000.0

    if excess_deducted > allowed:
        overcharge = excess_deducted - allowed
        return allowed, overcharge, "compulsory_excess_slabs"
    
    return excess_deducted, 0.0, None

def audit_claim_tat(
    intimation_date: Optional[date],
    surveyor_assigned_date: Optional[date],
    survey_report_date: Optional[date],
    settlement_date: Optional[date],
    approved_amount: float,
    rbi_bank_rate: float = DEFAULT_RBI_BANK_RATE_PCT
) -> List[TATDelayViolation]:
    """
    Audits adherence to 2024 IRDAI Master Circular Turnaround Times.
    Calculates penal interest (Bank Rate + 2%) for unapproved delays.
    """
    violations = []
    penal_rate = rbi_bank_rate + 2.0

    # 1. Surveyor Assignment TAT (Max 48 hours / 2 days)
    if intimation_date and surveyor_assigned_date:
        days_to_assign = (surveyor_assigned_date - intimation_date).days
        if days_to_assign > 2:
            delayed = days_to_assign - 2
            violations.append(TATDelayViolation(
                delay_type="Surveyor Assignment Delay",
                statutory_limit_days=2,
                actual_days=days_to_assign,
                days_delayed=delayed,
                penal_interest_rate_pct=penal_rate,
                penal_interest_amount=0.0,
                rag_topic_needed="tat_surveyor_appointment"
            ))

    # 2. Survey Report Submission TAT (Max 30 days)
    if surveyor_assigned_date and survey_report_date:
        days_to_report = (survey_report_date - surveyor_assigned_date).days
        if days_to_report > 30:
            delayed = days_to_report - 30
            violations.append(TATDelayViolation(
                delay_type="Survey Report Submission Delay",
                statutory_limit_days=30,
                actual_days=days_to_report,
                days_delayed=delayed,
                penal_interest_rate_pct=penal_rate,
                penal_interest_amount=0.0,
                rag_topic_needed="tat_surveyor_report"
            ))

    # 3. Final Settlement TAT (Max 7 working days as per 2024 Master Circular)
    if survey_report_date and settlement_date:
        days_to_settle = (settlement_date - survey_report_date).days
        if days_to_settle > 7:
            delayed = days_to_settle - 7
            interest = approved_amount * (penal_rate / 100.0) * (delayed / 365.0)
            violations.append(TATDelayViolation(
                delay_type="Claim Settlement Delay",
                statutory_limit_days=7,
                actual_days=days_to_settle,
                days_delayed=delayed,
                penal_interest_rate_pct=penal_rate,
                penal_interest_amount=round(interest, 2),
                rag_topic_needed="tat_penal_interest"
            ))

    return violations

def run_deterministic_rules_audit(
    assessment: ClaimAssessment, 
    vehicle_age_months: int = 12,
    engine_cc: int = 1200,
    intimation_date: Optional[date] = None,
    surveyor_assigned_date: Optional[date] = None,
    survey_report_date: Optional[date] = None,
    settlement_date: Optional[date] = None
) -> RulesAuditResult:
    """
    Main entry point for Layer 2.
    Evaluates ClaimAssessment purely via arithmetic and statutory rules.
    """

    item_violations: List[ItemRuleViolation] = []
    required_topics: set = set()
    
    # Safe extraction of labor amounts
    labor_claimed_val = float(getattr(assessment, 'labor_claimed', None) or getattr(assessment, 'labor_estimated', 0.0))
    labor_approved_val = float(getattr(assessment, 'labor_approved', None) or getattr(assessment, 'labor_settled', 0.0))

    total_claimed = labor_claimed_val
    total_approved = labor_approved_val
    total_unfair_cuts = 0.0
    total_legitimate_cuts = 0.0

    # 1. Audit Labor deductions
    labor_cut = labor_claimed_val - labor_approved_val
    if labor_cut > 0:
        total_unfair_cuts += labor_cut
        required_topics.add("claim_deduction_fair_practice")
        item_violations.append(ItemRuleViolation(
            item_name="Workshop Labor Charges",
            material="labor",
            amount_claimed=labor_claimed_val,
            amount_approved=labor_approved_val,
            amount_deducted=labor_cut,
            statutory_allowable_cut=0.0,
            unfair_deduction=labor_cut,
            violation_code="UNSUPPORTED_LABOR_CUT",
            rag_topic_needed="claim_deduction_fair_practice",
            reason="Arbitrary disallowance of labor hours without recorded technical schedule."
        ))

    # 2. Audit Replacement Parts
    for part in assessment.parts:
        # Dynamically read attribute names regardless of schema naming differences
        claimed_val = float(getattr(part, 'claimed_cost', None) or getattr(part, 'claimed_amount', None) or getattr(part, 'estimated_cost', 0.0))
        approved_val = float(getattr(part, 'approved_cost', None) or getattr(part, 'approved_amount', None) or getattr(part, 'settled_cost', 0.0))
        dep_cut = float(getattr(part, 'depreciation_deducted', None) or getattr(part, 'depreciation_amount', None) or (claimed_val - approved_val))
        mat = str(getattr(part, 'material', '') or getattr(part, 'part_type', 'plastic'))
        name = str(getattr(part, 'part_name', '') or getattr(part, 'description', 'Unnamed Part'))

        total_claimed += claimed_val
        total_approved += approved_val

        actual_cut = dep_cut
        statutory_rate, topic = calculate_statutory_depreciation_rate(
            mat, 
            assessment.has_zero_dep, 
            vehicle_age_months
        )
        allowed_cut = round(claimed_val * statutory_rate, 2)
        unfair_cut = max(0.0, actual_cut - allowed_cut)

        if unfair_cut > 0:
            total_unfair_cuts += unfair_cut
            required_topics.add(topic)
            code = "UNFAIR_ZERO_DEP_VIOLATION" if assessment.has_zero_dep else "EXCESS_TARIFF_DEPRECIATION"
            
            item_violations.append(ItemRuleViolation(
                item_name=name,
                material=mat,
                amount_claimed=claimed_val,
                amount_approved=approved_val,
                amount_deducted=actual_cut,
                statutory_allowable_cut=allowed_cut,
                unfair_deduction=unfair_cut,
                violation_code=code,
                rag_topic_needed=topic,
                reason=(
                    f"Nil-Depreciation endorsement violated: {statutory_rate*100}% allowable vs {actual_cut} cut."
                    if assessment.has_zero_dep else
                    f"Tariff rate exceeded: Statutory {statutory_rate*100}% allowable vs {actual_cut} cut."
                )
            ))
        else:
            total_legitimate_cuts += actual_cut

    # 3. Audit Compulsory Excess
    compulsory_excess_val = float(getattr(assessment, 'compulsory_excess', None) or getattr(assessment, 'deductible', 1000.0))
    allowed_excess, unfair_excess, excess_topic = audit_compulsory_excess(
        engine_cc=engine_cc, 
        excess_deducted=compulsory_excess_val
    )
    total_legitimate_cuts += allowed_excess
    if unfair_excess > 0:
        total_unfair_cuts += unfair_excess
        if excess_topic:
            required_topics.add(excess_topic)
        item_violations.append(ItemRuleViolation(
            item_name="Compulsory Excess / Deductible",
            material="statutory_fee",
            amount_claimed=compulsory_excess_val,
            amount_approved=allowed_excess,
            amount_deducted=compulsory_excess_val,
            statutory_allowable_cut=allowed_excess,
            unfair_deduction=unfair_excess,
            violation_code="EXCESS_OVERCHARGE_VIOLATION",
            rag_topic_needed="compulsory_excess_slabs",
            reason=f"Exceeded IMT statutory limit of ₹{allowed_excess} for engine capacity {engine_cc}cc."
        ))

    # 4. Audit TAT Timelines
    tat_violations = audit_claim_tat(
        intimation_date,
        surveyor_assigned_date,
        survey_report_date,
        settlement_date,
        approved_amount=total_approved
    )
    for tv in tat_violations:
        required_topics.add(tv.rag_topic_needed)

    total_shortfall = total_claimed - total_approved

    return RulesAuditResult(
        total_claimed=round(total_claimed, 2),
        total_approved=round(total_approved, 2),
        total_shortfall=round(total_shortfall, 2),
        recoverable_unfair_amount=round(total_unfair_cuts, 2),
        legitimate_statutory_amount=round(total_legitimate_cuts, 2),
        has_unfair_cuts=(len(item_violations) > 0 or len(tat_violations) > 0),
        item_violations=item_violations,
        tat_violations=tat_violations,
        required_rag_topics=sorted(list(required_topics))
    )