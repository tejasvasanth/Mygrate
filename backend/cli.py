"""Migrate CLI — audit, plan, run and drift-check databases from the terminal.

    migrate audit --source "mysql://user:pass@host/db"
    migrate plan  --source "mysql://..." --target "postgres://..."
    migrate run   --source "mysql://..." --target "postgres://..."
    migrate drift --source "postgres://..." --baseline-id job_abc123

`audit` is the free, commitment-free entry point: it profiles the source,
prints the semantic mismatch report and data quality score, then discards the
job. Nothing is ever written to the audited database.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any
from urllib.parse import urlparse

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="Migrate — agentic database migration")

# Windows consoles default to cp1252, which cannot encode the arrows and box
# characters this output uses. Force UTF-8 before Rich captures the streams.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover — exotic terminals
            pass

console = Console()

API_OPT = typer.Option("http://localhost:8000", "--api", envvar="MIGRATE_API_URL",
                       help="FastAPI backend base URL")
TOKEN_OPT = typer.Option(None, "--token", envvar="MIGRATE_TOKEN",
                         help="Supabase JWT (not required in development)")

LEVEL_STYLE = {"info": "cyan", "warning": "yellow", "error": "bold red",
               "success": "green"}

SCHEME_TO_DB_TYPE = {
    "postgres": "postgres", "postgresql": "postgres",
    "mysql": "mysql", "mariadb": "mariadb",
    "mongodb": "mongodb", "mongodb+srv": "mongodb",
    "sqlite": "sqlite", "file": "sqlite",
    "mssql": "sqlserver", "sqlserver": "sqlserver",
    "bigquery": "bigquery", "dynamodb": "dynamodb",
    "neo4j": "neo4j", "bolt": "neo4j",
}

TERMINAL = {"completed", "failed", "cancelled"}


def score_style(score: float) -> str:
    return "green" if score >= 85 else "yellow" if score >= 60 else "red"


def _db_type(connection_string: str, override: str | None) -> str:
    if override:
        return override
    scheme = urlparse(connection_string).scheme.lower()
    if scheme in SCHEME_TO_DB_TYPE:
        return SCHEME_TO_DB_TYPE[scheme]
    if not scheme or connection_string.endswith((".db", ".sqlite", ".sqlite3")):
        return "sqlite"
    raise typer.BadParameter(
        f"Cannot infer database type from scheme {scheme!r} — pass --source-type")


class Client:
    def __init__(self, api: str, token: str | None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.http = httpx.Client(base_url=f"{api.rstrip('/')}/api/v1",
                                 headers=headers, timeout=60)

    def request(self, method: str, path: str, **kw: Any) -> Any:
        try:
            r = self.http.request(method, path, **kw)
        except httpx.ConnectError as e:
            console.print(Panel(
                f"Could not reach the Migrate backend.\n\n{e}\n\n"
                f"Start it with:  [bold]uvicorn main:app --reload[/bold]\n"
                f"or point at another instance with [bold]--api[/bold].",
                title="Connection failed", border_style="red"))
            raise typer.Exit(1) from e
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:  # noqa: BLE001
                detail = r.text
            console.print(f"[bold red]API error {r.status_code}:[/bold red] {detail}")
            raise typer.Exit(1)
        return r.json() if r.content else None

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, json=body)


def _create_and_start(client: Client, name: str, source: str, target: str | None,
                      source_type: str | None, target_type: str | None) -> str:
    src_type = _db_type(source, source_type)
    # An audit still needs a syntactically valid target; the source is reused
    # as a placeholder. Nothing is written before a plan is approved.
    tgt = target or source
    tgt_type = _db_type(tgt, target_type)
    job = client.post("/migrations", {
        "name": name, "source_db_type": src_type, "target_db_type": tgt_type,
        "source_connection_string": source, "target_connection_string": tgt,
        "options": {"dry_run": True},
    })
    client.post(f"/migrations/{job['id']}/start")
    console.print(f"[dim]job {job['id']} · {src_type} → {tgt_type}[/dim]")
    return job["id"]


def _stream(client: Client, job_id: str, until: set[str],
            poll_s: float = 1.2) -> dict[str, Any]:
    """Poll job + logs, printing new log lines live until a wanted status."""
    seen: set[str] = set()
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                  BarColumn(), TextColumn("{task.percentage:>3.0f}%"),
                  console=console, transient=True) as progress:
        task = progress.add_task("starting…", total=100)
        while True:
            job = client.get(f"/migrations/{job_id}")
            for log in client.get(f"/migrations/{job_id}/logs") or []:
                if log["id"] in seen:
                    continue
                seen.add(log["id"])
                style = LEVEL_STYLE.get(log["level"], "white")
                progress.console.print(
                    f"[dim]{log['agent']:>18}[/dim] "
                    f"[{style}]{log['message']}[/{style}]")
            progress.update(task, completed=job.get("progress_pct", 0),
                            description=job["status"])
            if job["status"] in until:
                return job
            time.sleep(poll_s)


def _ellipsis(text: str, limit: int) -> str:
    """Truncate on a word boundary so evidence never breaks mid-word."""
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",") + "…"


def _print_semantic(report: dict[str, Any]) -> None:
    score = report["schema_trust_score"]
    style = score_style(score)
    console.print(Panel(
        f"[bold {style}]{score}/100[/bold {style}]  schema trust score\n"
        f"{report['summary']['total_mismatches']} mismatch(es) across "
        f"{report['summary']['total_columns_profiled']} profiled columns",
        title="Semantic Mismatch Report", border_style=style))

    rows: list[tuple[str, str, str, str, str]] = []
    for b in report.get("implicit_booleans", []):
        rows.append((f"{b['table']}.{b['column']}", "implicit boolean",
                     str(b.get("declared_type")),
                     ", ".join(map(str, b.get("sample_values", [])[:4])),
                     f"{b.get('confidence', 0)}%"))
    for e in report.get("implicit_enums", []):
        rows.append((f"{e['table']}.{e['column']}", "implicit enum",
                     str(e.get("declared_type")),
                     ", ".join(e.get("distinct_values", [])[:4]),
                     f"{e.get('confidence', 0)}%"))
    for d in report.get("semantic_detections", []):
        rows.append((f"{d['table']}.{d['column']}",
                     d["inferred_semantic_type"], str(d.get("declared_type")),
                     _ellipsis(d.get("evidence_summary", ""), 52),
                     f"{d.get('confidence_pct', 0)}%"))
    for n in report.get("never_null_nullables", []):
        rows.append((f"{n['table']}.{n['column']}", "never null",
                     str(n.get("declared_type")),
                     f"0 nulls in {n.get('sample_size', 0)} rows", "—"))
    if rows:
        table = Table(show_header=True, header_style="bold")
        for col in ("Column", "Migrate infers", "Declared", "Evidence", "Conf."):
            table.add_column(col, overflow="fold")
        for r in rows:
            table.add_row(*r)
        console.print(table)

    dangerous = report.get("dangerous_type_mismatches", [])
    if dangerous:
        console.print("\n[bold red]Dangerous mismatches — data loss risk[/bold red]")
        for d in dangerous:
            console.print(f"  [red]![/red] {d['table']}.{d['column']} "
                          f"({d.get('declared_type')}): {d['risk']}")

    fks = report.get("implicit_foreign_keys", [])
    if fks:
        console.print("\n[bold]Undeclared relationships[/bold]")
        for f in fks:
            console.print(f"  {f['table']}.{f['column']} → "
                          f"{f['likely_references']} "
                          f"({f['match_pct']}% of sampled rows)")

    pii = report.get("pii_columns", [])
    if pii:
        console.print("\n[bold magenta]PII detected[/bold magenta] " +
                      ", ".join(f"{p['table']}.{p['column']} ({p['pii_type']})"
                                for p in pii))


def _print_quality(quality: dict[str, Any]) -> None:
    score = quality["quality_score"]
    style = score_style(score)
    console.print(Panel(
        f"[bold {style}]{score}/100[/bold {style}]  data quality score\n"
        f"{len(quality['issues'])} issue(s) across "
        f"{quality.get('tables_checked', 0)} table(s)",
        title="Data Quality Report", border_style=style))
    if not quality["issues"]:
        console.print("[green]No data quality issues found in the sample.[/green]")
        return
    table = Table(show_header=True, header_style="bold")
    for col in ("Severity", "Where", "Issue"):
        table.add_column(col, overflow="fold")
    colour = {"high": "red", "medium": "yellow", "low": "cyan"}
    for i in quality["issues"]:
        where = f"{i['table']}.{i['column']}" if i.get("column") else i["table"]
        sev = i["severity"]
        table.add_row(f"[{colour.get(sev, 'white')}]{sev.upper()}"
                      f"[/{colour.get(sev, 'white')}]", where, i["detail"])
    console.print(table)


@app.command()
def audit(source: str = typer.Option(..., "--source", help="Source connection string"),
          source_type: str = typer.Option(None, "--source-type"),
          as_json: bool = typer.Option(False, "--json", help="Print raw JSON"),
          api: str = API_OPT, token: str = TOKEN_OPT):
    """Audit any database — semantic mismatches + data quality. No migration."""
    client = Client(api, token)
    job_id = _create_and_start(client, "cli-audit", source, None,
                               source_type, None)
    job = _stream(client, job_id,
                  {"planning", "awaiting_approval"} | TERMINAL)
    if job["status"] == "failed":
        console.print("[bold red]Audit failed.[/bold red]")
        raise typer.Exit(1)

    semantic = client.get(f"/migrations/{job_id}/semantic-report")
    quality = client.get(f"/migrations/{job_id}/quality-report")
    if as_json:
        console.print_json(json.dumps({"semantic": semantic, "quality": quality}))
    else:
        _print_semantic(semantic)
        console.print()
        _print_quality(quality)
        console.print("\n[dim]Nothing was written to your database. "
                      "Run `migrate plan` to see how Migrate would move it.[/dim]")

    # Commitment-free: discard the job once the report is in hand.
    if job["status"] not in TERMINAL:
        client.post(f"/migrations/{job_id}/cancel")


@app.command()
def plan(source: str = typer.Option(..., "--source"),
         target: str = typer.Option(..., "--target"),
         source_type: str = typer.Option(None, "--source-type"),
         target_type: str = typer.Option(None, "--target-type"),
         name: str = typer.Option("cli-plan", "--name"),
         api: str = API_OPT, token: str = TOKEN_OPT):
    """Dry run: analyze, profile and print the AI migration plan. No execution."""
    client = Client(api, token)
    job_id = _create_and_start(client, name, source, target,
                               source_type, target_type)
    job = _stream(client, job_id, {"awaiting_approval"} | TERMINAL)
    if job["status"] != "awaiting_approval":
        raise typer.Exit(1)

    semantic = client.get(f"/migrations/{job_id}/semantic-report")
    _print_semantic(semantic)

    diff = client.get(f"/migrations/{job_id}/preview-diff")
    table = Table(title=f"Preview diff — {diff['differing_count']} of "
                        f"{diff['total_count']} columns disagree",
                  show_header=True, header_style="bold")
    for col in ("Column", "Schema says", "Data means", "Recommendation", "Conf."):
        table.add_column(col, overflow="fold")
    for row in diff["rows"]:
        marker = "[red]●[/red] " if row["differs"] else "[green]●[/green] "
        table.add_row(
            marker + f"{row['table']}.{row['column']}",
            f"{row['declared']['type']} "
            f"{'NULL' if row['declared']['nullable'] else 'NOT NULL'}",
            row["inferred"]["semantic_type"], row["recommendation"],
            f"{row['confidence']}%")
    console.print(table)
    console.print(f"\n[dim]Plan stored for job {job_id}. "
                  f"Approve it in the UI or run `migrate run` to execute.[/dim]")


@app.command()
def run(source: str = typer.Option(..., "--source"),
        target: str = typer.Option(..., "--target"),
        source_type: str = typer.Option(None, "--source-type"),
        target_type: str = typer.Option(None, "--target-type"),
        name: str = typer.Option("cli-run", "--name"),
        yes: bool = typer.Option(False, "--yes", "-y",
                                 help="Approve the plan without prompting"),
        api: str = API_OPT, token: str = TOKEN_OPT):
    """Full migration: plan, approve, execute, validate."""
    client = Client(api, token)
    job_id = _create_and_start(client, name, source, target,
                               source_type, target_type)
    job = _stream(client, job_id, {"awaiting_approval"} | TERMINAL)
    if job["status"] != "awaiting_approval":
        raise typer.Exit(1)

    semantic = client.get(f"/migrations/{job_id}/semantic-report")
    _print_semantic(semantic)
    dangerous = semantic.get("dangerous_type_mismatches", [])
    if dangerous and not yes:
        console.print(f"\n[bold red]{len(dangerous)} dangerous mismatch(es) "
                      f"detected.[/bold red] Review them before continuing.")
    if not yes:
        typer.confirm("\nApprove this plan and execute?", abort=True)

    client.post(f"/migrations/{job_id}/approve")
    job = _stream(client, job_id, TERMINAL)
    if job["status"] != "completed":
        console.print(f"[bold red]Migration {job['status']}.[/bold red] "
                      f"Run `migrate` again with --resume once fixed.")
        raise typer.Exit(1)

    validation = job.get("validation_report") or {}
    score = validation.get("confidence_score", 0)
    console.print(Panel(
        f"[bold {score_style(score)}]{score}%[/bold {score_style(score)}] confidence\n"
        f"{job.get('rows_migrated', 0)} rows migrated",
        title="Migration complete", border_style="green"))
    if validation.get("flagged_tables"):
        console.print("[yellow]Flagged tables:[/yellow] "
                      + ", ".join(validation["flagged_tables"]))


@app.command()
def drift(baseline_id: str = typer.Option(..., "--baseline-id",
                                          help="Monitor id from `migrate` enrollment"),
          as_json: bool = typer.Option(False, "--json"),
          api: str = API_OPT, token: str = TOKEN_OPT):
    """Check a monitored database for schema drift against its baseline."""
    client = Client(api, token)
    result = client.post(f"/monitoring/{baseline_id}/check")
    if as_json:
        console.print_json(json.dumps(result))
        raise typer.Exit(0 if not result["has_drift"] else 2)

    score = result["health_score"]
    style = score_style(score)
    if not result["has_drift"]:
        console.print(Panel(
            f"[bold green]No drift.[/bold green] Health score {score}/100.\n"
            f"The schema matches its baseline.",
            title="Drift check", border_style="green"))
        raise typer.Exit(0)

    counts = result["counts"]
    console.print(Panel(
        f"[bold {style}]{score}/100[/bold {style}] health score\n"
        f"{counts.get('critical', 0)} critical · {counts.get('warning', 0)} warning "
        f"· {counts.get('info', 0)} info",
        title="Schema drift detected", border_style=style))
    table = Table(show_header=True, header_style="bold")
    for col in ("Severity", "Where", "What changed"):
        table.add_column(col, overflow="fold")
    colour = {"critical": "red", "warning": "yellow", "info": "cyan"}
    for e in result["events"]:
        where = f"{e['table']}.{e['column']}" if e.get("column") else e["table"]
        c = colour.get(e["severity"], "white")
        table.add_row(f"[{c}]{e['severity'].upper()}[/{c}]", where, e["detail"])
    console.print(table)
    # Non-zero exit so CI pipelines can gate on drift.
    raise typer.Exit(2)


@app.command()
def templates(api: str = API_OPT):
    """List the built-in migration templates for common stacks."""
    client = Client(api, None)
    table = Table(show_header=True, header_style="bold")
    for col in ("Slug", "Stack", "Path"):
        table.add_column(col, overflow="fold")
    for t in client.get("/templates")["templates"]:
        table.add_row(t["slug"], t["stack"],
                      f"{t['source_db_type']} → {t['target_db_type']}")
    console.print(table)


if __name__ == "__main__":
    sys.exit(app())
