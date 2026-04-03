"""
AI Engine — trend detection, anomaly detection, health alerts.
Uses scikit-learn Z-score anomaly detection + rolling window trend analysis.
"""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

import statistics
import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.models import Vital, AIInsight, Patient, Notification, NotificationType, InsightSeverity
from app.core.config import settings


# ── Metric Configuration ──────────────────────────────────────────────────────

VITAL_CONFIGS = {
    "heart_rate": {
        "label": "Resting Heart Rate",
        "unit": "bpm",
        "normal_range": (60, 100),
        "critical_low": 40,
        "critical_high": 150,
        "category": "cardiovascular",
    },
    "systolic_bp": {
        "label": "Systolic Blood Pressure",
        "unit": "mmHg",
        "normal_range": (90, 120),
        "critical_low": 70,
        "critical_high": 180,
        "category": "cardiovascular",
    },
    "diastolic_bp": {
        "label": "Diastolic Blood Pressure",
        "unit": "mmHg",
        "normal_range": (60, 80),
        "critical_low": 40,
        "critical_high": 120,
        "category": "cardiovascular",
    },
    "blood_glucose": {
        "label": "Blood Glucose",
        "unit": "mg/dL",
        "normal_range": (70, 100),
        "critical_low": 50,
        "critical_high": 250,
        "category": "metabolic",
    },
    "oxygen_saturation": {
        "label": "Oxygen Saturation (SpO₂)",
        "unit": "%",
        "normal_range": (95, 100),
        "critical_low": 88,
        "critical_high": 100,
        "category": "respiratory",
    },
    "temperature": {
        "label": "Body Temperature",
        "unit": "°C",
        "normal_range": (36.1, 37.2),
        "critical_low": 35.0,
        "critical_high": 39.5,
        "category": "general",
    },
    "weight_kg": {
        "label": "Body Weight",
        "unit": "kg",
        "normal_range": None,   # relative — use trend detection
        "critical_low": None,
        "critical_high": None,
        "category": "metabolic",
    },
}


class AIInsightEngine:
    """
    Core AI analysis engine.
    
    Algorithms:
    1. Z-score anomaly detection on vital series
    2. Rolling window linear trend estimation
    3. Range violation alerts (critical + warning)
    4. Multi-metric correlation hints
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Public Entry Point ────────────────────────────────────────────────────

    async def run_analysis_for_patient(self, patient_id: UUID) -> List[AIInsight]:
        """
        Full pipeline: fetch vitals → analyze → persist insights.
        Returns newly created AIInsight objects.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.AI_TREND_WINDOW_DAYS)
        result = await self.db.execute(
            select(Vital)
            .where(and_(Vital.patient_id == patient_id, Vital.recorded_at >= cutoff))
            .order_by(Vital.recorded_at.asc())
        )
        vitals: List[Vital] = result.scalars().all()

        if len(vitals) < settings.AI_MIN_DATA_POINTS:
            return []

        insights = []
        for metric, config in VITAL_CONFIGS.items():
            series = self._extract_series(vitals, metric)
            if len(series) < settings.AI_MIN_DATA_POINTS:
                continue

            # 1. Range violations
            range_insight = self._check_range_violations(patient_id, metric, config, series)
            if range_insight:
                insights.append(range_insight)

            # 2. Anomaly detection (Z-score)
            anomaly_insight = self._detect_anomalies(patient_id, metric, config, series)
            if anomaly_insight:
                insights.append(anomaly_insight)

            # 3. Trend detection
            trend_insight = self._detect_trend(patient_id, metric, config, series)
            if trend_insight:
                insights.append(trend_insight)

        # Persist new insights
        saved = []
        for insight_data in insights:
            self.db.add(insight_data)
            saved.append(insight_data)

        await self.db.flush()
        return saved

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _extract_series(self, vitals: List[Vital], metric: str) -> List[Tuple[datetime, float]]:
        """Extract (timestamp, value) pairs, skipping nulls."""
        series = []
        for v in vitals:
            val = getattr(v, metric, None)
            if val is not None:
                series.append((v.recorded_at, float(val)))
        return series

    def _check_range_violations(
        self,
        patient_id: UUID,
        metric: str,
        config: dict,
        series: List[Tuple[datetime, float]],
    ) -> Optional[AIInsight]:
        """Alert if recent readings are outside critical thresholds."""
        recent = series[-3:]   # last 3 readings
        values = [v for _, v in recent]

        critical_low  = config.get("critical_low")
        critical_high = config.get("critical_high")
        normal_range  = config.get("normal_range")

        if not normal_range:
            return None

        avg_recent = sum(values) / len(values)

        if critical_low and avg_recent < critical_low:
            return AIInsight(
                patient_id=patient_id,
                title=f"⚠️ Critical Low: {config['label']}",
                description=(
                    f"Your recent {config['label']} readings average {avg_recent:.1f} {config['unit']}, "
                    f"which is critically below the safe threshold of {critical_low} {config['unit']}. "
                    "Please consult a healthcare provider immediately."
                ),
                severity=InsightSeverity.CRITICAL,
                category=config["category"],
                metric=metric,
                data_points=[{"timestamp": str(ts), "value": val} for ts, val in recent],
                recommendation="Seek immediate medical attention. Do not ignore this alert.",
            )

        if critical_high and avg_recent > critical_high:
            return AIInsight(
                patient_id=patient_id,
                title=f"⚠️ Critical High: {config['label']}",
                description=(
                    f"Your recent {config['label']} readings average {avg_recent:.1f} {config['unit']}, "
                    f"which is critically above the safe threshold of {critical_high} {config['unit']}."
                ),
                severity=InsightSeverity.CRITICAL,
                category=config["category"],
                metric=metric,
                data_points=[{"timestamp": str(ts), "value": val} for ts, val in recent],
                recommendation="Consult your doctor as soon as possible.",
            )

        low, high = normal_range
        if avg_recent < low or avg_recent > high:
            return AIInsight(
                patient_id=patient_id,
                title=f"📊 {config['label']} Outside Normal Range",
                description=(
                    f"Your recent {config['label']} averages {avg_recent:.1f} {config['unit']}. "
                    f"Normal range is {low}–{high} {config['unit']}."
                ),
                severity=InsightSeverity.WARNING,
                category=config["category"],
                metric=metric,
                data_points=[{"timestamp": str(ts), "value": val} for ts, val in recent],
                recommendation="Monitor closely and discuss with your doctor at your next visit.",
            )

        return None

    def _detect_anomalies(
        self,
        patient_id: UUID,
        metric: str,
        config: dict,
        series: List[Tuple[datetime, float]],
    ) -> Optional[AIInsight]:
        """Z-score based anomaly detection on the full series."""
        values = [v for _, v in series]

        if len(values) < 5:
            return None

        mean  = statistics.mean(values)
        stdev = statistics.pstdev(values)

        if stdev == 0:
            return None

        # Check last reading
        last_ts, last_val = series[-1]
        z_score = abs((last_val - mean) / stdev)

        if z_score >= settings.AI_ANOMALY_THRESHOLD:
            direction = "elevated" if last_val > mean else "lower than usual"
            pct_diff  = abs((last_val - mean) / mean) * 100

            return AIInsight(
                patient_id=patient_id,
                title=f"🔍 Anomaly Detected: {config['label']}",
                description=(
                    f"Your latest {config['label']} reading ({last_val:.1f} {config['unit']}) "
                    f"is significantly {direction} — {pct_diff:.0f}% from your {settings.AI_TREND_WINDOW_DAYS}-day average "
                    f"of {mean:.1f} {config['unit']} (Z-score: {z_score:.2f})."
                ),
                severity=InsightSeverity.WARNING if z_score < 3 else InsightSeverity.CRITICAL,
                category=config["category"],
                metric=metric,
                data_points=[{"timestamp": str(ts), "value": val} for ts, val in series[-10:]],
                recommendation=(
                    "This could be a one-time variation or a meaningful change. "
                    "Track your next few readings and consult your doctor if it persists."
                ),
            )

        return None

    def _detect_trend(
        self,
        patient_id: UUID,
        metric: str,
        config: dict,
        series: List[Tuple[datetime, float]],
    ) -> Optional[AIInsight]:
        """
        Linear regression on timestamp vs value to detect significant upward/downward trends.
        Uses simple least-squares slope calculation.
        """
        values = [v for _, v in series]
        n = len(values)

        if n < settings.AI_MIN_DATA_POINTS:
            return None

        # Normalize x to [0, n-1]
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(values) / n

        numerator   = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values))
        denominator = sum((x - x_mean) ** 2 for x in xs)

        if denominator == 0:
            return None

        slope = numerator / denominator

        # Slope significance: express as % change per week (7 readings approx)
        pct_per_week = (slope * 7 / (y_mean or 1)) * 100

        TREND_THRESHOLD_PCT = 8.0  # >8% per week = notable trend

        if abs(pct_per_week) < TREND_THRESHOLD_PCT:
            return None

        direction   = "increasing" if slope > 0 else "decreasing"
        first_val   = values[0]
        last_val    = values[-1]
        total_change = ((last_val - first_val) / (first_val or 1)) * 100

        severity = InsightSeverity.INFO
        if abs(total_change) > 20:
            severity = InsightSeverity.WARNING
        if abs(total_change) > 40:
            severity = InsightSeverity.CRITICAL

        return AIInsight(
            patient_id=patient_id,
            title=f"📈 {config['label']} Trend: {direction.capitalize()}",
            description=(
                f"Your {config['label']} has been {direction} over the past "
                f"{settings.AI_TREND_WINDOW_DAYS} days. "
                f"Changed from {first_val:.1f} to {last_val:.1f} {config['unit']} "
                f"({total_change:+.1f}%)."
            ),
            severity=severity,
            category=config["category"],
            metric=metric,
            data_points=[{"timestamp": str(ts), "value": val} for ts, val in series],
            recommendation=(
                f"Your {config['label']} shows a consistent {direction} trend. "
                "Consider discussing this with your doctor to determine if any lifestyle changes or tests are needed."
            ),
        )

    # ── Quick Single-Patient Summary ──────────────────────────────────────────

    async def get_health_score(self, patient_id: UUID) -> dict:
        """
        Compute a simple 0-100 health score based on recent vitals
        within normal range. Used by the dashboard summary card.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        result = await self.db.execute(
            select(Vital)
            .where(and_(Vital.patient_id == patient_id, Vital.recorded_at >= cutoff))
            .order_by(Vital.recorded_at.desc())
            .limit(50)
        )
        vitals: List[Vital] = result.scalars().all()

        if not vitals:
            return {"score": None, "label": "Insufficient data", "color": "gray"}

        scores = []
        for metric, config in VITAL_CONFIGS.items():
            normal_range = config.get("normal_range")
            if not normal_range:
                continue
            values = [getattr(v, metric) for v in vitals if getattr(v, metric) is not None]
            if not values:
                continue
            avg = sum(values) / len(values)
            low, high = normal_range
            mid = (low + high) / 2
            span = (high - low) / 2
            dist = abs(avg - mid)
            metric_score = max(0, 100 - (dist / span * 50))
            scores.append(metric_score)

        if not scores:
            return {"score": None, "label": "Insufficient data", "color": "gray"}

        final_score = round(sum(scores) / len(scores))
        label = (
            "Excellent" if final_score >= 90 else
            "Good"      if final_score >= 75 else
            "Fair"      if final_score >= 55 else
            "Poor"
        )
        color = (
            "green"  if final_score >= 90 else
            "blue"   if final_score >= 75 else
            "yellow" if final_score >= 55 else
            "red"
        )
        return {"score": final_score, "label": label, "color": color}
