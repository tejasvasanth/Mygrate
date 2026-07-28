"""Agent 6 — Report Writer: explains the migration outcome to the user.

Consumes the outputs of every upstream agent (schema snapshot, data profile,
migration plan, execution report, validation report) and produces a final
narrative report: why the confidence score is what it is, which flags the
user should manually check, and actionable recommendations.

Uses Gemini when configured; otherwise a deterministic fallback derives the
explanation directly from the ValidationAuditor's scoring weights
(60% row counts, 30% sample-hash match, 10% FK integrity).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from ..config import get_settings
from ..utils.logger import job_logger

AGENT_NAME = "report_writer"

SYSTEM_PROMPT = """
You are a database migration auditor writing a post-migration report for a
non-expert user. You receive the full outputs of a migration pipeline:
schema snapshot, data profile, AI migration plan, execution report, and a
validation report containing a confidence score (0-100).

The confidence score was computed per table as:
  0.6 * row-count-match + 0.3 * sample-hash-match-ratio + 0.1 * FK-integrity,
averaged across tables and scaled to 100.

Output valid JSON only. No prose outside JSON. Exact shape:
{
  "executive_summary": "<2-4 sentences: what was migrated, overall outcome>",
  "confidence_explanation": {
    "narrative": "<plain-English explanation of WHY the score is what it is>",
    "breakdown": [
      {"component": "<e.g. Row counts>", "weight": "<e.g. 60%>",
       "score": <0-100>, "reason": "<why this component scored this way>"}
    ]
  },
  "flags": [
    {"severity": "high" | "medium" | "low",
     "table": "<table name or null>",
     "title": "<short title>",
     "detail": "<what happened>",
     "what_to_check": "<concrete manual check the user should perform>"}
  ],
  "recommendations": ["<actionable next step>"]
}
Every flagged table, execution error, plan warning, and PII column MUST appear
as a flag. If everything is clean, say so and include only low-severity
advisory flags (e.g. spot-check PII columns).
"""


class ReportWriter:
    def __init__(self, schema_snapshot: dict[str, Any], data_profile: dict[str, Any],
                 plan: dict[str, Any], execution_report: dict[str, Any],
                 validation_report: dict[str, Any], job_id: str, log_sink=None):
        self.schema = schema_snapshot or {}
        self.profile = data_profile or {}
        self.plan = plan or {}
        self.execution = execution_report or {}
        self.validation = validation_report or {}
        self.job_id = job_id
        self.log = job_logger(__name__, job_id, AGENT_NAME)
        self.log_sink = log_sink
        self.settings = get_settings()

    async def _emit(self, level: str, message: str, metadata: dict[str, Any] | None = None):
        self.log.info(message)
        if self.log_sink:
            await self.log_sink(level, AGENT_NAME, message, metadata or {})

    async def run(self) -> dict[str, Any]:
        await self._emit("info", "Writing final migration report…")
        if self.settings.gemini_api_key:
            try:
                report = await self._generate_with_gemini()
                report = self._finalise(report, ai_generated=True)
                await self._emit("success", "Final report written by Gemini.",
                                 {"model": self.settings.gemini_model})
                return report
            except Exception as e:  # noqa: BLE001 — always fall back, never silently
                await self._emit("warning",
                                 f"Gemini report failed ({e}); using deterministic report.")
        else:
            await self._emit("warning",
                             "GEMINI_API_KEY not configured — using deterministic report.")
        report = self._finalise(self.fallback_report(), ai_generated=False)
        await self._emit("success", "Deterministic final report written.")
        return report

    # ── Gemini call ────────────────────────────────────────────────
    async def _generate_with_gemini(self) -> dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.settings.gemini_api_key)
        user_message = f"""
VALIDATION REPORT (contains the confidence score):
{json.dumps(self.validation, indent=2, default=str)}

EXECUTION REPORT:
{json.dumps(self.execution, indent=2, default=str)}

MIGRATION PLAN (warnings matter):
{json.dumps(self._plan_digest(), indent=2, default=str)}

DATA PROFILE DIGEST (PII / quality issues):
{json.dumps(self._profile_digest(), indent=2, default=str)}

Write the report now. Output JSON only.
"""
        response = await client.aio.models.generate_content(
            model=self.settings.gemini_model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                max_output_tokens=8096,
            ),
        )
        raw = (response.text or "").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

    def _plan_digest(self) -> dict[str, Any]:
        """Plan minus the bulky column mappings — warnings and rules only."""
        return {
            "summary": self.plan.get("summary"),
            "global_warnings": self.plan.get("global_warnings", []),
            "tables": [{
                "source_table": t.get("source_table"),
                "target_table_name": t.get("target_table_name"),
                "warnings": t.get("warnings", []),
                "transformation_rules": t.get("transformation_rules", []),
            } for t in self.plan.get("tables", [])],
        }

    def _profile_digest(self) -> dict[str, Any]:
        """Only columns with something worth flagging."""
        out: dict[str, Any] = {}
        for table, info in self.profile.get("tables", {}).items():
            cols = {name: c for name, c in info.get("columns", {}).items()
                    if c.get("pii_suspected") or c.get("implicit_boolean")
                    or c.get("implicit_enum") or c.get("null_pct", 0) > 50}
            if cols:
                out[table] = cols
        return out

    # ── Deterministic fallback ─────────────────────────────────────
    def fallback_report(self) -> dict[str, Any]:
        v = self.validation
        tables = v.get("tables", {})
        flagged = set(v.get("flagged_tables", []))
        n = max(len(tables), 1)

        count_score = round(100 * sum(
            1 if t.get("row_count_ok") else max(0.0, 1 - t.get("mismatch_pct", 100) / 100)
            for t in tables.values()) / n)
        hash_score = round(100 * sum(
            t.get("sample_hash", {}).get("match_ratio", 0) for t in tables.values()) / n)
        fk_score = round(100 * sum(
            1 if t.get("fk_integrity_ok") else 0 for t in tables.values()) / n)

        breakdown = [
            {"component": "Row counts", "weight": "60%", "score": count_score,
             "reason": ("All tables have matching source/target row counts."
                        if not flagged else
                        f"Row count mismatch above 0.1% in: {', '.join(sorted(flagged))}.")},
            {"component": "Sample data integrity", "weight": "30%", "score": hash_score,
             "reason": "Random source rows were hashed column-by-column and looked up "
                       "in the target; this is the share that matched exactly."},
            {"component": "Referential integrity", "weight": "10%", "score": fk_score,
             "reason": ("All sampled foreign-key values resolve to a referenced row."
                        if fk_score == 100 else
                        "Some sampled foreign-key values did not resolve.")},
        ]

        flags: list[dict[str, Any]] = []
        for name in sorted(flagged):
            t = tables.get(name, {})
            flags.append({
                "severity": "high", "table": name,
                "title": "Row count mismatch",
                "detail": f"Source has {t.get('source_rows')} rows, target has "
                          f"{t.get('target_rows')} ({t.get('mismatch_pct')}% off).",
                "what_to_check": f"Run a COUNT(*) on both sides of '{name}' and diff "
                                 "primary keys to find the missing/extra rows.",
            })
        for name, t in tables.items():
            ratio = t.get("sample_hash", {}).get("match_ratio", 1.0)
            if ratio < 1.0:
                flags.append({
                    "severity": "medium" if ratio >= 0.9 else "high", "table": name,
                    "title": "Sampled rows differ between source and target",
                    "detail": f"Only {ratio:.0%} of sampled rows matched exactly — "
                              "values may have been transformed or lost precision.",
                    "what_to_check": f"Manually compare a few rows of '{name}' by primary "
                                     "key, paying attention to dates, decimals and encodings.",
                })
            if not t.get("fk_integrity_ok", True):
                flags.append({
                    "severity": "high", "table": name,
                    "title": "Foreign-key integrity issue",
                    "detail": "Sampled FK values did not all resolve to referenced rows.",
                    "what_to_check": f"Check orphaned references in '{name}' before "
                                     "enabling constraints on the target.",
                })
        for err in self.execution.get("errors", []):
            flags.append({
                "severity": "high", "table": (err.get("table") if isinstance(err, dict) else None),
                "title": "Execution error",
                "detail": str(err), "what_to_check":
                    "Review the migration logs for this chunk and re-run if needed.",
            })
        for t in self.plan.get("tables", []):
            for w in t.get("warnings", []):
                flags.append({
                    "severity": "low", "table": t.get("source_table"),
                    "title": "Planner warning", "detail": str(w),
                    "what_to_check": "Confirm the migrated values look correct for this column.",
                })
        for w in self.plan.get("global_warnings", []):
            flags.append({"severity": "low", "table": None, "title": "Planner warning",
                          "detail": str(w),
                          "what_to_check": "Review the migration plan for this warning."})
        for table, cols in self._profile_digest().items():
            pii = [c for c, v_ in cols.items() if v_.get("pii_suspected")]
            if pii:
                flags.append({
                    "severity": "low", "table": table,
                    "title": "PII columns migrated",
                    "detail": f"Columns that look like PII: {', '.join(pii)}.",
                    "what_to_check": "Verify access controls/encryption on the target "
                                     "cover these columns.",
                })

        score = v.get("confidence_score", 0)
        rows = self.execution.get("rows_migrated", 0)
        recommendations = []
        if flagged:
            recommendations.append("Re-run the migration for the flagged tables after "
                                   "putting the source in read-only mode.")
        if hash_score < 100:
            recommendations.append("Spot-check transformed columns (dates, decimals, "
                                   "booleans) on a sample of rows.")
        if not flags or all(f["severity"] == "low" for f in flags):
            recommendations.append("No blocking issues found — safe to switch reads to "
                                   "the target after your own spot checks.")
        recommendations.append("Keep the source database until you have verified the "
                               "target in your application.")

        return {
            "executive_summary": (
                f"{rows} rows across {len(tables)} table(s) were migrated. "
                f"The validation auditor scored the migration {score}/100 — the score "
                "is a weighted blend of row-count parity (60%), sampled row-level data "
                "integrity (30%) and referential integrity (10%). "
                + ("All checks passed." if v.get("passed")
                   else "Some checks need your attention — see flags.")),
            "confidence_explanation": {
                "narrative": (
                    f"The confidence score of {score}% comes from three checks: row counts "
                    f"scored {count_score}/100 (worth 60% of the total), sampled data "
                    f"integrity scored {hash_score}/100 (worth 30%), and referential "
                    f"integrity scored {fk_score}/100 (worth 10%)."),
                "breakdown": breakdown,
            },
            "flags": flags,
            "recommendations": recommendations,
        }

    # ── Shared post-processing ─────────────────────────────────────
    def _finalise(self, report: dict[str, Any], ai_generated: bool) -> dict[str, Any]:
        report.setdefault("flags", [])
        report.setdefault("recommendations", [])
        report["confidence_score"] = self.validation.get("confidence_score", 0)
        report["passed"] = self.validation.get("passed", False)
        report["ai_generated"] = ai_generated
        report["generated_at"] = datetime.now(timezone.utc).isoformat()
        return report
