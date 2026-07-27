#!/usr/bin/env python3
"""Refresh the credit union DuckDB dataset from NCUA 5300 call report quarterly files.

The NCUA publishes one zip per cycle at a predictable URL and silently re-publishes
revised zips at the same URL, so this script tracks a content hash per cycle in
``data/source_manifest.json`` and can detect both new quarters and revisions.

Typical use::

    # what's available upstream that we don't already have?
    python scripts/refresh_data.py check

    # ingest a zip already on disk
    python scripts/refresh_data.py ingest --zip call-report-data-2026-03.zip

    # download the newest cycle(s) and ingest them
    python scripts/refresh_data.py sync
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import duckdb

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "cu_data.duckdb"
VIEW_SQL_PATH = BASE_DIR / "scripts" / "rebuild_cu_with_ratios.sql"
MANIFEST_PATH = BASE_DIR / "data" / "source_manifest.json"
DOWNLOAD_DIR = BASE_DIR / "data" / "source_zips"

# Distinct exit codes so a scheduled `check` can tell "work to do" from "it broke".
EXIT_CURRENT = 0
EXIT_PENDING = 1
EXIT_ERROR = 2

NCUA_URL_TEMPLATE = "https://www.ncua.gov/files/publications/analysis/call-report-data-{cycle}.zip"
USER_AGENT = "cu-mcp-refresh/1.0 (+https://github.com/kylelegare/cu_MCP)"

# Financial schedule suffixes carried in the database. The NCUA zip also ships
# FS220D and FS220S, which the dataset has never included; adding them here is
# all that is required if that changes.
FS_SUFFIXES = ["", "a", "b", "c", "g", "h", "i", "j", "k", "l", "m", "n", "p", "q", "r"]

# Quarterly tables: appended to, one cycle at a time.
QUARTERLY_TABLES: Dict[str, str] = {"foicu": "FOICU.txt"}
QUARTERLY_TABLES.update({f"fs220{s}": f"FS220{s.upper()}.txt" for s in FS_SUFFIXES})

# Reference tables: not cycle-scoped, replaced wholesale with the newest copy.
REFERENCE_TABLES: Dict[str, str] = {"acctdesc": "AcctDesc.txt"}

# NCUA writes dates as M/D/YYYY with an optional 12- or 24-hour time component.
DATE_FORMATS = ["%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"]


# ---------------------------------------------------------------------------
# Cycle helpers
# ---------------------------------------------------------------------------
def note(message: str) -> None:
    """Diagnostic aside. Goes to stderr so `check --json` keeps stdout parseable."""
    print(message, file=sys.stderr)


def cycle_to_date(cycle: str) -> _dt.date:
    """Turn a ``YYYY-MM`` cycle label into the quarter-end date."""
    year, month = (int(part) for part in cycle.split("-"))
    if month not in (3, 6, 9, 12):
        raise ValueError(f"{cycle}: NCUA cycles end in month 03, 06, 09, or 12")
    last_day = 31 if month in (3, 12) else 30
    return _dt.date(year, month, last_day)


def date_to_cycle(value: _dt.date) -> str:
    return f"{value.year}-{value.month:02d}"


def recent_cycles(count: int, today: Optional[_dt.date] = None) -> List[str]:
    """Return the ``count`` most recent cycle labels, newest first."""
    today = today or _dt.date.today()
    quarter_month = ((today.month - 1) // 3) * 3 or 12
    year = today.year if quarter_month != 12 or today.month >= 12 else today.year - 1
    cycles: List[str] = []
    while len(cycles) < count:
        cycles.append(f"{year}-{quarter_month:02d}")
        quarter_month -= 3
        if quarter_month < 3:
            quarter_month = 12
            year -= 1
    return cycles


# ---------------------------------------------------------------------------
# Manifest + download
# ---------------------------------------------------------------------------
def load_manifest() -> Dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text())


def save_manifest(manifest: Dict[str, Any]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_cycle(cycle: str) -> Optional[Dict[str, Any]]:
    """HEAD the NCUA zip for a cycle. Returns None when it is not published yet."""
    url = NCUA_URL_TEMPLATE.format(cycle=cycle)
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {
                "url": url,
                "bytes": int(response.headers.get("Content-Length") or 0),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
            }
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def fingerprint(meta: Dict[str, Any]) -> Optional[str]:
    """Cheap change signal for a published zip.

    NCUA's CDN omits Content-Length and ETag on HEAD responses, so Last-Modified
    is the only header that reliably moves when a cycle is revised in place.
    """
    for key in ("last_modified", "etag"):
        if meta.get(key):
            return f"{key}:{meta[key]}"
    if meta.get("bytes"):
        return f"bytes:{meta['bytes']}"
    return None


def db_cycles() -> Optional[List[str]]:
    """Cycle labels already loaded into the database.

    Returns None when the database cannot be read — notably on a CI checkout
    that skipped Git LFS, where the file on disk is a pointer stub. Callers
    fall back to the manifest so a scheduled `check` costs no LFS bandwidth.
    """
    if not DB_PATH.exists():
        return None
    try:
        with duckdb.connect(str(DB_PATH), read_only=True) as con:
            rows = con.execute("SELECT DISTINCT cycle_date FROM foicu ORDER BY 1").fetchall()
    except duckdb.Error:
        return None
    return [date_to_cycle(row[0]) for row in rows]


def loaded_cycles(manifest: Dict[str, Any]) -> List[str]:
    """Cycles we already hold, preferring the database and falling back to the manifest."""
    from_db = db_cycles()
    if from_db is not None:
        return from_db
    note(f"  ({DB_PATH.name} unreadable — using {MANIFEST_PATH.name} to decide what is loaded)")
    return [cycle for cycle, entry in manifest.items() if entry.get("in_database")]


def download_cycle(cycle: str, destination: Optional[Path] = None) -> Path:
    url = NCUA_URL_TEMPLATE.format(cycle=cycle)
    destination = destination or DOWNLOAD_DIR / f"call-report-data-{cycle}.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    print(f"  downloading {url}")
    with urllib.request.urlopen(request, timeout=300) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    print(f"  saved {destination} ({destination.stat().st_size:,} bytes)")
    return destination


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------
def table_columns(con: duckdb.DuckDBPyConnection, table: str) -> Dict[str, str]:
    rows = con.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = ? ORDER BY ordinal_position",
        [table],
    ).fetchall()
    return {name: dtype for name, dtype in rows}


def staged_columns(con: duckdb.DuckDBPyConnection, staging: str) -> List[str]:
    """Column names of a staged CSV, lowercased to match the database convention."""
    return [str(row[0]).lower() for row in con.execute(f"DESCRIBE {staging}").fetchall()]


def cast_expression(column: str, dtype: str) -> str:
    """SQL that converts an all-VARCHAR staged column into the destination type."""
    quoted = f'"{column}"'
    trimmed = f"NULLIF(TRIM({quoted}), '')"
    if dtype == "DATE":
        return f"CAST(TRY_STRPTIME({trimmed}, {_format_list()}) AS DATE)"
    if dtype.startswith("TIMESTAMP"):
        return f"TRY_STRPTIME({trimmed}, {_format_list()})"
    if dtype == "VARCHAR":
        return quoted
    return f"TRY_CAST({trimmed} AS {dtype})"


def _format_list() -> str:
    return "[" + ", ".join(f"'{fmt}'" for fmt in DATE_FORMATS) + "]"


def infer_type(con: duckdb.DuckDBPyConnection, staging: str, column: str) -> str:
    """Pick the narrowest type that loses no values for a column new to the schema."""
    for candidate in ("BIGINT", "DOUBLE"):
        failures = con.execute(
            f"SELECT COUNT(*) FROM {staging} "
            f"WHERE NULLIF(TRIM(\"{column}\"), '') IS NOT NULL "
            f"AND TRY_CAST(NULLIF(TRIM(\"{column}\"), '') AS {candidate}) IS NULL"
        ).fetchone()[0]
        if failures == 0:
            return candidate
    return "VARCHAR"


def coercion_failures(
    con: duckdb.DuckDBPyConnection, staging: str, columns: Dict[str, str], present: Iterable[str]
) -> List[Tuple[str, int]]:
    """Columns where a non-empty source value cast to NULL — i.e. silent data loss."""
    present = set(present)
    checked = [
        col for col, dtype in columns.items() if col in present and dtype != "VARCHAR"
    ]
    if not checked:
        return []
    checks = ", ".join(
        f"SUM(CASE WHEN NULLIF(TRIM(\"{col}\"), '') IS NOT NULL "
        f"AND ({cast_expression(col, columns[col])}) IS NULL THEN 1 ELSE 0 END)"
        for col in checked
    )
    row = con.execute(f"SELECT {checks} FROM {staging}").fetchone()
    return [(col, int(count)) for col, count in zip(checked, row) if count]


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
def stage_file(con: duckdb.DuckDBPyConnection, path: Path, name: str) -> None:
    # CREATE VIEW cannot be prepared, so the path is inlined as an escaped literal.
    literal = str(path).replace("'", "''")
    con.execute(
        f"CREATE OR REPLACE TEMP VIEW {name} AS "
        f"SELECT * FROM read_csv('{literal}', header = true, all_varchar = true, "
        "quote = '\"', escape = '\"', strict_mode = false)"
    )


def ingest_table(
    con: duckdb.DuckDBPyConnection,
    table: str,
    path: Path,
    cycle_date: _dt.date,
    replace: bool,
) -> None:
    staging = "staging_src"
    stage_file(con, path, staging)

    dest = table_columns(con, table)
    source = staged_columns(con, staging)

    added = [col for col in source if col not in dest]
    for column in added:
        dtype = infer_type(con, staging, column)
        con.execute(f'ALTER TABLE {table} ADD COLUMN "{column}" {dtype}')
        dest[column] = dtype
        print(f"    + new column {table}.{column} {dtype}")

    losses = coercion_failures(con, staging, dest, source)
    if losses:
        detail = ", ".join(f"{col} ({count} rows)" for col, count in losses)
        raise RuntimeError(f"{table}: values failed to convert cleanly: {detail}")

    file_cycles = con.execute(
        f"SELECT DISTINCT {cast_expression('cycle_date', 'DATE')} FROM {staging}"
    ).fetchall()
    file_cycles = [row[0] for row in file_cycles if row[0] is not None]
    if file_cycles != [cycle_date]:
        raise RuntimeError(
            f"{table}: expected only cycle {cycle_date}, file contains {file_cycles}"
        )

    existing = con.execute(
        f"SELECT COUNT(*) FROM {table} WHERE cycle_date = ?", [cycle_date]
    ).fetchone()[0]
    if existing:
        if not replace:
            raise RuntimeError(
                f"{table}: cycle {cycle_date} already has {existing:,} rows (pass --replace to overwrite)"
            )
        con.execute(f"DELETE FROM {table} WHERE cycle_date = ?", [cycle_date])

    select_list = ", ".join(
        cast_expression(col, dtype) if col in source else f"CAST(NULL AS {dtype})"
        for col, dtype in dest.items()
    )
    column_list = ", ".join(f'"{col}"' for col in dest)
    con.execute(f"INSERT INTO {table} ({column_list}) SELECT {select_list} FROM {staging}")

    inserted = con.execute(
        f"SELECT COUNT(*) FROM {table} WHERE cycle_date = ?", [cycle_date]
    ).fetchone()[0]
    print(f"    {table}: {inserted:,} rows{' (replaced)' if existing else ''}")


def replace_reference_table(con: duckdb.DuckDBPyConnection, table: str, path: Path) -> None:
    staging = "staging_ref"
    stage_file(con, path, staging)
    dest = table_columns(con, table)
    source = staged_columns(con, staging)
    select_list = ", ".join(
        (f'"{col}"' if col in source else "CAST(NULL AS VARCHAR)") + f' AS "{col}"'
        for col in dest
    )
    con.execute(f"DELETE FROM {table}")
    con.execute(f"INSERT INTO {table} SELECT {select_list} FROM {staging}")
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"    {table}: {count:,} rows (replaced)")


def rebuild_view(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(VIEW_SQL_PATH.read_text())
    print(f"    cu_with_ratios rebuilt from {VIEW_SQL_PATH.name}")


def compact_database(expected_rows: int) -> None:
    """Rewrite the database into a fresh file so replaced pages are reclaimed.

    DuckDB never shrinks a file in place, so without this the LFS-tracked
    database grows faster than the data it holds.
    """
    before = DB_PATH.stat().st_size
    target = DB_PATH.with_suffix(".duckdb.compact")
    target.unlink(missing_ok=True)

    con = duckdb.connect()
    try:
        con.execute(f"ATTACH '{str(DB_PATH).replace(chr(39), chr(39) * 2)}' AS src (READ_ONLY)")
        con.execute(f"ATTACH '{str(target).replace(chr(39), chr(39) * 2)}' AS out")
        con.execute("COPY FROM DATABASE src TO out")
    finally:
        con.close()

    with duckdb.connect(str(target), read_only=True) as check:
        rows = check.execute("SELECT COUNT(*) FROM cu_with_ratios").fetchone()[0]
    if rows != expected_rows:
        target.unlink(missing_ok=True)
        raise RuntimeError(
            f"compaction produced {rows:,} rows, expected {expected_rows:,}; original left untouched"
        )

    target.replace(DB_PATH)
    after = DB_PATH.stat().st_size
    print(f"  compacted database {before / 1e6:.0f} MB -> {after / 1e6:.0f} MB")


def verify(con: duckdb.DuckDBPyConnection, cycle_date: _dt.date) -> None:
    quarters, low, high = con.execute(
        "SELECT COUNT(DISTINCT cycle_date), MIN(cycle_date), MAX(cycle_date) FROM foicu"
    ).fetchone()
    print(f"\n  {quarters} quarters, {low} through {high}")

    rows = con.execute(
        """
        SELECT cycle_date,
               COUNT(*) AS credit_unions,
               SUM(assets) AS total_assets,
               ROUND(MEDIAN(roa), 3) AS median_roa,
               ROUND(MEDIAN(efficiency_ratio), 2) AS median_efficiency,
               ROUND(MEDIAN(net_worth_ratio), 2) AS median_net_worth,
               COUNT(*) FILTER (WHERE roa IS NULL) AS null_roa
        FROM cu_with_ratios
        WHERE cycle_date >= ?
        GROUP BY cycle_date ORDER BY cycle_date
        """,
        [cycle_date - _dt.timedelta(days=200)],
    ).fetchall()
    print("  cycle       CUs    total assets  med ROA  med eff  med NW  null ROA")
    for cyc, cus, assets, roa, eff, net_worth, null_roa in rows:
        print(
            f"  {cyc}  {cus:>5,}  ${assets / 1e12:>10.3f}T  {roa:>7}  {eff:>7}  {net_worth:>6}  {null_roa:>8,}"
        )

    growth = con.execute(
        """
        SELECT COUNT(*) FILTER (WHERE asset_growth_yoy IS NOT NULL)
        FROM cu_with_ratios WHERE cycle_date = ?
        """,
        [cycle_date],
    ).fetchone()[0]
    print(f"  {growth:,} credit unions have YOY growth ratios for {cycle_date}")


def ingest_zip(zip_path: Path, *, replace: bool, backup: bool, compact: bool = True) -> str:
    """Load one NCUA cycle zip into the database. Returns the cycle label."""
    print(f"\nIngesting {zip_path.name}")
    if backup and DB_PATH.exists():
        backup_path = DB_PATH.with_suffix(".duckdb.bak")
        shutil.copy2(DB_PATH, backup_path)
        print(f"  backed up database to {backup_path.name}")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(tmp_dir)

        missing = [
            filename
            for filename in list(QUARTERLY_TABLES.values()) + list(REFERENCE_TABLES.values())
            if not (tmp_dir / filename).exists()
        ]
        if missing:
            raise RuntimeError(f"{zip_path.name} is missing expected files: {missing}")

        con = duckdb.connect(str(DB_PATH))
        try:
            cycle_date = con.execute(
                f"SELECT DISTINCT {cast_expression('cycle_date', 'DATE')} "
                "FROM read_csv(?, header = true, all_varchar = true)",
                [str(tmp_dir / QUARTERLY_TABLES['foicu'])],
            ).fetchone()[0]
            print(f"  cycle detected: {cycle_date}")

            con.execute("BEGIN TRANSACTION")
            try:
                for table, filename in QUARTERLY_TABLES.items():
                    ingest_table(con, table, tmp_dir / filename, cycle_date, replace)
                for table, filename in REFERENCE_TABLES.items():
                    replace_reference_table(con, table, tmp_dir / filename)
                rebuild_view(con)
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
            verify(con, cycle_date)
            row_count = con.execute("SELECT COUNT(*) FROM cu_with_ratios").fetchone()[0]
        finally:
            con.close()

    if compact:
        compact_database(row_count)

    return date_to_cycle(cycle_date)


def record_ingest(cycle: str, zip_path: Optional[Path], remote: Optional[Dict[str, Any]]) -> None:
    """Store the upstream fingerprint for a cycle so revisions can be detected later."""
    if remote is None:
        try:
            remote = probe_cycle(cycle)
        except urllib.error.URLError as exc:  # offline ingest of a local zip
            note(f"  could not reach NCUA to record a revision baseline: {exc}")
    remote = remote or {}
    manifest = load_manifest()
    # Every caller reaches here only for a cycle the database already holds.
    entry: Dict[str, Any] = {
        "source": remote.get("url", NCUA_URL_TEMPLATE.format(cycle=cycle)),
        "fingerprint": fingerprint(remote),
        "last_modified": remote.get("last_modified"),
        "in_database": True,
        "checked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
    }
    if zip_path is not None:
        entry["sha256"] = sha256_of(zip_path)
        entry["bytes"] = zip_path.stat().st_size
        entry["ingested_at"] = entry["checked_at"]
    else:
        # Baselining a cycle loaded before this script existed; keep any prior detail.
        entry = {**manifest.get(cycle, {}), **entry}
    manifest[cycle] = entry
    save_manifest(manifest)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cycle_status(cycle: str, remote: Dict[str, Any], loaded: Iterable[str], manifest: Dict[str, Any]) -> Tuple[str, bool]:
    """Classify a published cycle. Returns (human status, needs_ingest)."""
    if cycle not in loaded:
        return "NEW — not in database", True

    known = manifest.get(cycle) or {}
    current = fingerprint(remote)
    if not known.get("fingerprint"):
        # Loaded before revision tracking started: adopt the current upstream
        # state as the baseline so a later revision stands out.
        record_ingest(cycle, None, remote)
        return "in database (baseline recorded)", False
    if not known.get("in_database"):
        record_ingest(cycle, None, remote)  # self-heal a manifest predating this flag
    if current and known["fingerprint"] != current:
        return f"REVISED — upstream changed {known.get('last_modified')} -> {remote.get('last_modified')}", True
    return f"up to date (published {remote.get('last_modified')})", False


def cmd_check(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    loaded = loaded_cycles(manifest)
    pending: List[str] = []
    lines: List[str] = []
    for cycle in recent_cycles(args.lookback):
        remote = probe_cycle(cycle)
        if remote is None:
            lines.append(f"  {cycle}  not published yet")
            continue
        status, needs_ingest = cycle_status(cycle, remote, loaded, manifest)
        if needs_ingest:
            pending.append(cycle)
        lines.append(f"  {cycle}  {status}")

    if args.json:
        print(json.dumps({"pending": pending, "detail": [line.strip() for line in lines]}))
        return EXIT_PENDING if pending else EXIT_CURRENT

    print(f"Checking the {args.lookback} most recent NCUA cycles against {DB_PATH.name}\n")
    print("\n".join(lines))
    if pending:
        print(f"\n{len(pending)} cycle(s) need ingest: {', '.join(pending)}")
        print(f"Run: python scripts/{Path(__file__).name} sync")
    else:
        print("\nDatabase is current with NCUA.")
    return EXIT_PENDING if pending else EXIT_CURRENT


def cmd_ingest(args: argparse.Namespace) -> int:
    zip_path = Path(args.zip).resolve()
    if not zip_path.exists():
        raise SystemExit(f"zip not found: {zip_path}")
    cycle = ingest_zip(
        zip_path, replace=args.replace, backup=not args.no_backup, compact=not args.no_compact
    )
    record_ingest(cycle, zip_path, None)
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    manifest = load_manifest()
    loaded = loaded_cycles(manifest)
    cycles = args.cycles or list(reversed(recent_cycles(args.lookback)))
    ingested: List[str] = []
    for cycle in cycles:
        remote = probe_cycle(cycle)
        if remote is None:
            continue
        _, needs_ingest = cycle_status(cycle, remote, loaded, manifest)
        if not needs_ingest and not args.force:
            continue

        print(f"\n=== {cycle} ===")
        zip_path = download_cycle(cycle)
        known = manifest.get(cycle, {})
        if known.get("sha256") == sha256_of(zip_path) and not args.force:
            print("  byte-identical to the copy already ingested; recording and skipping")
            record_ingest(cycle, zip_path, remote)
            continue
        ingest_zip(zip_path, replace=True, backup=not args.no_backup, compact=not args.no_compact)
        record_ingest(cycle, zip_path, remote)
        ingested.append(cycle)

    if ingested:
        print(f"\nIngested {len(ingested)} cycle(s): {', '.join(ingested)}")
        print("Commit data/cu_data.duckdb and data/source_manifest.json to deploy.")
    else:
        print("\nNothing to do — database is current with NCUA.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="report which NCUA cycles are new or revised")
    check.add_argument("--lookback", type=int, default=4, help="how many recent cycles to probe")
    check.add_argument("--json", action="store_true", help="emit a machine-readable summary")
    check.set_defaults(func=cmd_check)

    ingest = sub.add_parser("ingest", help="ingest a call report zip already on disk")
    ingest.add_argument("--zip", required=True)
    ingest.add_argument("--replace", action="store_true", help="overwrite a cycle already present")
    ingest.add_argument("--no-backup", action="store_true")
    ingest.add_argument("--no-compact", action="store_true", help="skip the file-shrinking rewrite")
    ingest.set_defaults(func=cmd_ingest)

    sync = sub.add_parser("sync", help="download and ingest any new or revised cycles")
    sync.add_argument("--cycles", nargs="*", help="specific cycles, e.g. 2026-06")
    sync.add_argument("--lookback", type=int, default=4)
    sync.add_argument("--force", action="store_true", help="re-ingest even if unchanged")
    sync.add_argument("--no-backup", action="store_true")
    sync.add_argument("--no-compact", action="store_true", help="skip the file-shrinking rewrite")
    sync.set_defaults(func=cmd_sync)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # keep exit 1 meaning "work pending", never "it broke"
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
