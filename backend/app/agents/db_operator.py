"""Agent 7 — DB Operator: natural-language database operations.

Given a user instruction (and optionally a parsed spreadsheet), the target
database schema, and the db type, produces an OperationPlan that is shown to
the user for approval BEFORE anything is executed — the same trust model as
migrations. v1 supports: inserting rows (from a file or from the instruction)
into an existing table, and creating a new table for the data.

Gemini decides the target table, header→column mapping, and value coercions;
a deterministic fallback matches headers to the best-overlapping table.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..config import get_settings
from ..utils.logger import get_logger
from ..utils.type_mapper import target_type

AGENT_NAME = "db_operator"

SYSTEM_PROMPT = """
You are a database operations assistant. You receive a database schema, the
database type, a user instruction, and optionally spreadsheet data (headers +
sample rows). Plan the requested operation. Output valid JSON only — no prose.

Supported operation kinds (v1): "insert" (add rows to an existing table) and
"create_and_insert" (create a new table, then add the rows).

Output shape:
{
  "kind": "insert" | "create_and_insert",
  "target_table": "<existing table name, or new table name>",
  "new_table_columns": [   // only for create_and_insert
    {"name": "...", "canonical_type": "integer|bigint|float|decimal|boolean|string|text|date|datetime|json", "nullable": true}
  ],
  "primary_key": ["<column>"] | [],
  "column_mapping": [      // spreadsheet header (or synthetic field) -> db column
    {"source": "<header>", "target": "<db column>", "transform": null | "<description>"}
  ],
  "inline_rows": [ {..} ], // rows extracted from the INSTRUCTION itself when no file given
  "summary": "<1-2 sentence human-readable description of what will happen>",
  "warnings": ["<anything risky: type mismatches, missing required columns, PII>"]
}
Rules:
- Prefer an existing table whose columns overlap the data; only create a new
  table when nothing fits or the user asks for one.
- Never invent data. inline_rows only from values explicitly in the instruction.
- Unmapped spreadsheet headers must be listed in warnings.
- If the instruction asks for updates or deletes, set kind to "insert" ONLY if
  inserting is what was asked; otherwise return
  {"kind": "unsupported", "summary": "...", "warnings": ["updates/deletes are not supported yet"]}.
"""


class DBOperator:
    def __init__(self, schema_snapshot: dict[str, Any], db_type: str,
                 instruction: str, headers: list[str] | None = None,
                 sample_rows: list[dict[str, Any]] | None = None):
        self.schema = schema_snapshot
        self.db_type = db_type
        self.instruction = instruction
        self.headers = headers or []
        self.sample_rows = sample_rows or []
        self.settings = get_settings()
        self.log = get_logger(__name__)

    async def plan(self) -> dict[str, Any]:
        if self.settings.gemini_api_key:
            try:
                plan = await self._plan_with_gemini()
                return self._sanity_check(plan, ai_generated=True)
            except Exception as e:  # noqa: BLE001
                self.log.warning(f"Gemini operation planning failed: {e}; using fallback")
        return self._sanity_check(self._fallback_plan(), ai_generated=False)

    # ── Gemini ─────────────────────────────────────────────────────
    async def _plan_with_gemini(self) -> dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.settings.gemini_api_key)
        schema_digest = {
            name: {"columns": [{"name": c["name"], "type": c["type"],
                                "nullable": c.get("nullable", True)}
                               for c in info.get("columns", [])],
                   "primary_key": info.get("primary_key", []),
                   "row_count": info.get("row_count", 0)}
            for name, info in self.schema.get("tables", {}).items()}
        user_message = f"""
Database type: {self.db_type}

DATABASE SCHEMA:
{json.dumps(schema_digest, indent=2, default=str)}

USER INSTRUCTION:
{self.instruction or "(none — infer intent from the uploaded data)"}

SPREADSHEET HEADERS: {json.dumps(self.headers)}
SPREADSHEET SAMPLE ROWS (first 10 of {len(self.sample_rows)}):
{json.dumps(self.sample_rows[:10], indent=2, default=str)}

Plan the operation now. Output JSON only.
"""
        response = await client.aio.models.generate_content(
            model=self.settings.gemini_model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                max_output_tokens=4096,
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

    # ── Deterministic fallback ─────────────────────────────────────
    def _fallback_plan(self) -> dict[str, Any]:
        if not self.headers:
            return {"kind": "unsupported",
                    "summary": "Without AI planning, only spreadsheet uploads are "
                               "supported — upload a file with a header row.",
                    "warnings": ["GEMINI_API_KEY not configured or AI planning failed."]}
        tables = self.schema.get("tables", {})
        lower_headers = {h.lower() for h in self.headers}
        best, best_overlap = None, 0
        for name, info in tables.items():
            cols = {c["name"].lower() for c in info.get("columns", [])}
            overlap = len(lower_headers & cols)
            if overlap > best_overlap:
                best, best_overlap = name, overlap
        if best and best_overlap >= max(1, len(self.headers) // 2):
            col_names = {c["name"].lower(): c["name"]
                         for c in tables[best].get("columns", [])}
            mapping = [{"source": h, "target": col_names[h.lower()], "transform": None}
                       for h in self.headers if h.lower() in col_names]
            unmapped = [h for h in self.headers if h.lower() not in col_names]
            return {
                "kind": "insert", "target_table": best,
                "column_mapping": mapping, "inline_rows": [],
                "summary": f"Insert {len(self.sample_rows)} row(s) into existing "
                           f"table '{best}' ({best_overlap}/{len(self.headers)} "
                           f"headers matched).",
                "warnings": ([f"Unmapped headers (will be skipped): {', '.join(unmapped)}"]
                             if unmapped else []),
            }
        # No decent match — create a new table from the headers.
        new_table = re.sub(r"\W+", "_", (self.instruction or "uploaded_data")
                           .strip().lower())[:40] or "uploaded_data"
        return {
            "kind": "create_and_insert", "target_table": new_table,
            "new_table_columns": [
                {"name": re.sub(r"\W+", "_", h.strip().lower()) or f"col_{i}",
                 "canonical_type": self._guess_type(h), "nullable": True}
                for i, h in enumerate(self.headers)],
            "primary_key": [],
            "column_mapping": [
                {"source": h,
                 "target": re.sub(r"\W+", "_", h.strip().lower()) or f"col_{i}",
                 "transform": None}
                for i, h in enumerate(self.headers)],
            "inline_rows": [],
            "summary": f"No existing table matches the upload — create new table "
                       f"'{new_table}' with {len(self.headers)} columns and insert "
                       f"{len(self.sample_rows)} row(s).",
            "warnings": ["Table chosen by fallback header matching, not AI — review "
                         "the column types before executing."],
        }

    def _guess_type(self, header: str) -> str:
        values = [r.get(header) for r in self.sample_rows[:100]
                  if r.get(header) is not None]
        if not values:
            return "string"
        if all(isinstance(v, bool) for v in values):
            return "boolean"
        if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            return "bigint"
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            return "float"
        return "string"

    # ── Validation ─────────────────────────────────────────────────
    def _sanity_check(self, plan: dict[str, Any], ai_generated: bool) -> dict[str, Any]:
        plan.setdefault("kind", "unsupported")
        plan.setdefault("warnings", [])
        plan.setdefault("column_mapping", [])
        plan.setdefault("inline_rows", [])
        plan["ai_generated"] = ai_generated
        if plan["kind"] == "insert":
            tables = self.schema.get("tables", {})
            if plan.get("target_table") not in tables:
                plan["warnings"].append(
                    f"Target table '{plan.get('target_table')}' not found in schema — "
                    "switching to create_and_insert.")
                plan["kind"] = "create_and_insert"
                plan.setdefault("new_table_columns", [
                    {"name": m["target"], "canonical_type": "string", "nullable": True}
                    for m in plan["column_mapping"]])
        if plan["kind"] == "create_and_insert":
            plan.setdefault("primary_key", [])
            for c in plan.get("new_table_columns", []):
                c["ddl_type"] = target_type(self.db_type, c.get("canonical_type", "string"))
        plan["row_count"] = len(self.sample_rows) or len(plan.get("inline_rows", []))
        return plan
