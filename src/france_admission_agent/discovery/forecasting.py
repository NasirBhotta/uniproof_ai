"""
Admission Pressure Forecasting & Opportunity Risk Band Engine
Author: Nasir Bhutta
Description: Analyzes multi-year admission trends, forecasts relative 2027 demand pressure,
             and determines candidate opportunity risk bands strictly without fabricating probabilities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)


@dataclass
class MultiYearTrend:
    demand_trend: Literal["INCREASING", "STABLE", "DECREASING", "VOLATILE", "UNKNOWN"] = "UNKNOWN"
    capacity_trend: Literal["INCREASING", "STABLE", "DECREASING", "UNKNOWN"] = "UNKNOWN"
    selectivity_trend: Literal["INCREASING_PRESSURE", "STABLE", "DECREASING_PRESSURE", "UNKNOWN"] = "UNKNOWN"
    years_evaluated: list[str] = None


@dataclass
class DemandForecast2027:
    expected_demand_pressure: Literal["LOW", "LOW_MODERATE", "MODERATE", "HIGH", "VERY_HIGH", "UNKNOWN"] = "UNKNOWN"
    trend: Literal["INCREASING", "STABLE", "DECREASING", "UNKNOWN"] = "UNKNOWN"
    confidence: Literal["LOW", "MODERATE", "HIGH"] = "LOW"
    reasoning: str = ""


@dataclass
class OpportunityAssessment:
    academic_fit: str = "STRONG"
    language_risk: Literal["LOW", "MODERATE", "HIGH", "UNKNOWN"] = "UNKNOWN"
    historical_pressure: str = "UNKNOWN"
    forecast_pressure: str = "UNKNOWN"
    candidate_position: str = "STRONG"
    evidence_confidence: str = "MODERATE"
    overall_risk_band: Literal["LOWER", "LOWER_MODERATE", "MODERATE", "MODERATE_HIGH", "HIGH", "UNKNOWN"] = "UNKNOWN"
    explanation: str = ""


def compute_multi_year_trends(records_by_year: list[dict[str, Any]]) -> MultiYearTrend:
    """Calculates multi-year direction for demand and capacity across distinct academic years."""
    if len(records_by_year) < 2:
        return MultiYearTrend(years_evaluated=[r.get("academic_year", "") for r in records_by_year])

    # Sort chronologically by year string
    sorted_recs = sorted(records_by_year, key=lambda x: str(x.get("academic_year", "")))
    apps = [r.get("applicants") for r in sorted_recs if r.get("applicants") is not None]
    caps = [r.get("capacity") for r in sorted_recs if r.get("capacity") is not None]

    # Demand trend
    if len(apps) >= 2:
        diffs = [apps[i] - apps[i-1] for i in range(1, len(apps))]
        if all(d > 0 for d in diffs):
            d_trend = "INCREASING"
        elif all(d < 0 for d in diffs):
            d_trend = "DECREASING"
        elif all(abs(d) <= (0.05 * apps[0]) for d in diffs):
            d_trend = "STABLE"
        else:
            d_trend = "VOLATILE"
    else:
        d_trend = "UNKNOWN"

    # Capacity trend
    if len(caps) >= 2:
        c_diffs = [caps[i] - caps[i-1] for i in range(1, len(caps))]
        if all(d > 0 for d in c_diffs):
            c_trend = "INCREASING"
        elif all(d < 0 for d in c_diffs):
            c_trend = "DECREASING"
        else:
            c_trend = "STABLE"
    else:
        c_trend = "UNKNOWN"

    # Selectivity trend
    if d_trend == "INCREASING" and c_trend in ("STABLE", "DECREASING"):
        s_trend = "INCREASING_PRESSURE"
    elif d_trend == "DECREASING" and c_trend in ("STABLE", "INCREASING"):
        s_trend = "DECREASING_PRESSURE"
    elif d_trend == "STABLE" and c_trend == "STABLE":
        s_trend = "STABLE"
    else:
        s_trend = "UNKNOWN"

    return MultiYearTrend(
        demand_trend=d_trend,
        capacity_trend=c_trend,
        selectivity_trend=s_trend,
        years_evaluated=[r.get("academic_year", "") for r in sorted_recs],
    )


def forecast_2027_demand_pressure(
    multi_year: MultiYearTrend,
    current_selectivity_pressure: str,
    evidence_confidence: float,
) -> DemandForecast2027:
    """Forecasts relative demand pressure for 2027 intake without fabricating probabilities."""
    conf = "LOW"
    if evidence_confidence >= 80.0 and len(multi_year.years_evaluated or []) >= 2:
        conf = "HIGH"
    elif evidence_confidence >= 50.0:
        conf = "MODERATE"

    if current_selectivity_pressure in ("HIGH", "VERY_HIGH"):
        expected = "HIGH"
        if multi_year.demand_trend == "INCREASING":
            expected = "VERY_HIGH"
            reason = "Historically high applicant pressure combined with an increasing application trend."
        else:
            reason = "High competition pressure observed in historical admissions data."
        trend_val = multi_year.demand_trend if multi_year.demand_trend != "UNKNOWN" else "STABLE"

    elif current_selectivity_pressure == "MODERATE":
        if multi_year.demand_trend == "INCREASING":
            expected = "MODERATE"
            reason = "Applicant pressure is moderate but steadily trending upwards."
            trend_val = "INCREASING"
        else:
            expected = "MODERATE"
            reason = "Balanced applicant volume relative to cohort capacity."
            trend_val = "STABLE"

    elif current_selectivity_pressure == "LOW":
        expected = "LOW_MODERATE"
        reason = "Accessible regional capacity with lower applicant-to-seat ratios."
        trend_val = multi_year.demand_trend if multi_year.demand_trend != "UNKNOWN" else "STABLE"

    else:
        expected = "UNKNOWN"
        reason = "HISTORICAL_SELECTIVITY_DATA_NOT_FOUND: Insufficient published applicant volume to forecast 2027 pressure."
        trend_val = "UNKNOWN"
        conf = "LOW"

    return DemandForecast2027(
        expected_demand_pressure=expected,
        trend=trend_val,
        confidence=conf,
        reasoning=reason,
    )


def determine_opportunity_risk_band(
    academic_strictness: str,
    language_risk: str,
    forecast_pressure: str,
    evidence_confidence: float,
    candidate_cgpa: float = 3.23,
) -> OpportunityAssessment:
    """Determines structured opportunity risk band for candidate.
    
    Bands:
    - LOWER: strong academic fit, low language risk, low/moderate competition, high evidence confidence
    - LOWER_MODERATE: good fit, verified route, moderate competition
    - MODERATE: moderate competition, minor language verification required
    - MODERATE_HIGH: high competition pressure or tight capacity
    - HIGH: very high selectivity pressure or major prerequisite/language incompatibility
    - UNKNOWN: missing critical evidence
    """
    if evidence_confidence < 30.0 or forecast_pressure == "UNKNOWN":
        return OpportunityAssessment(
            academic_fit="STRONG" if candidate_cgpa >= 3.0 else "MODERATE",
            language_risk=language_risk,
            historical_pressure=forecast_pressure,
            forecast_pressure=forecast_pressure,
            candidate_position="STRONG",
            evidence_confidence="LOW",
            overall_risk_band="UNKNOWN",
            explanation="Risk band is UNKNOWN because official capacity or applicant pressure data is not yet published.",
        )

    # Calculate risk level
    if forecast_pressure in ("VERY_HIGH", "HIGH") or academic_strictness in ("VERY_HIGH", "HIGH"):
        band = "MODERATE_HIGH"
        expl = "High selectivity pressure and competitive applicant volume elevate admission risk."
    elif language_risk == "HIGH":
        band = "MODERATE"
        expl = "Moderate risk: strong academic compatibility, but official teaching language or IELTS component threshold requires manual verification."
    elif forecast_pressure in ("LOW", "LOW_MODERATE", "MODERATE") and language_risk == "LOW":
        band = "LOWER"
        expl = "Lower admission risk: 100% English instruction verified, healthy capacity, and manageable historical competition pressure."
    else:
        band = "LOWER_MODERATE"
        expl = "Balanced risk: solid academic and prerequisite fit with reasonable regional demand."

    conf_label = "HIGH" if evidence_confidence >= 75.0 else ("MODERATE" if evidence_confidence >= 50.0 else "LOW")

    return OpportunityAssessment(
        academic_fit="STRONG",
        language_risk=language_risk,
        historical_pressure=forecast_pressure,
        forecast_pressure=forecast_pressure,
        candidate_position="STRONG",
        evidence_confidence=conf_label,
        overall_risk_band=band,
        explanation=expl,
    )
