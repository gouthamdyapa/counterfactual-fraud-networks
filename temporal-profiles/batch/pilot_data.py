#!/usr/bin/env python3
"""Read-only IBM CSV ingestion and complete induced-context extraction.

Python 3.8+; standard library only.  No solver internals are imported here.
Rows retain their zero-based positions in the original CSV, even when source
timestamps are not chronological.  The duplicate Account headers are parsed
positionally.  Source minutes are naive calendar minutes, not local/UTC times.
"""

from __future__ import annotations

import csv
from datetime import datetime
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import tempfile
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


CACHE_VERSION = 1
_EPOCH = datetime(1970, 1, 1)
_HEADER_PREFIX = ["Timestamp", "From Bank", "Account", "To Bank", "Account"]
_STAMP = re.compile(r"([0-9]{4})([/\-])([0-9]{2})\2([0-9]{2}) ([0-9]{2}):([0-9]{2})\Z")
_BANK = re.compile(r"[0-9]+\Z")
_DIGEST = re.compile(r"[0-9a-fA-F]{64}\Z")
_BATCH_ROWS = 10000
_QUERY_CHUNK = 300


class DataError(ValueError):
    """A controlled input/cache failure or an incomplete resource-limited read."""

    def __init__(self, message: str, code: str = "input_error") -> None:
        super().__init__(message)
        self.code = code


def _emit(progress: Optional[Callable[[str], None]], message: str) -> None:
    if progress is not None:
        progress(message)


def _validate_progress(progress: Optional[Callable[[str], None]]) -> None:
    if progress is not None and not callable(progress):
        raise DataError("progress must be a callable or None")


@lru_cache(maxsize=8192)
def _canonical_bank_text(text: str) -> str:
    if not _BANK.fullmatch(text):
        raise DataError("Bank identifiers must be nonnegative decimal integers")
    # This is equivalent to str(int(text)) for the accepted decimal syntax,
    # without a float conversion or an interpreter decimal-digit limit.
    return text.lstrip("0") or "0"


@lru_cache(maxsize=32768)
def _serialized_node(bank: str, account: str) -> str:
    return json.dumps([bank, account], separators=(",", ":"), ensure_ascii=True)


def node_key(bank: Any, account: Any) -> str:
    """Encode the canonical bank string and unchanged account string safely."""
    if isinstance(bank, bool):
        raise DataError("A Boolean is not a bank identifier")
    if isinstance(bank, int):
        if bank < 0:
            raise DataError("Bank identifiers must be nonnegative")
        bank = str(bank)
    if not isinstance(bank, str) or not bank:
        raise DataError("Bank identifiers must be nonempty decimal strings")
    if not isinstance(account, str) or not account or not account.strip():
        raise DataError("Account identifiers must be nonempty strings")
    return _serialized_node(_canonical_bank_text(bank), account)


@lru_cache(maxsize=32768)
def _parsed_minute_text(text: str) -> int:
    match = _STAMP.fullmatch(text)
    if match is None:
        raise DataError("Timestamp must be YYYY/MM/DD HH:MM or YYYY-MM-DD HH:MM, without a timezone or seconds")
    year, _separator, month, day, hour, minute = match.groups()
    try:
        value = datetime(int(year), int(month), int(day), int(hour), int(minute))
    except ValueError as exc:
        raise DataError("Invalid calendar minute: %s" % exc) from exc
    delta = value - _EPOCH
    return delta.days * 1440 + delta.seconds // 60


def parse_minute(text: Any) -> int:
    """Return an exact naive source-minute index; never round or assign a zone."""
    if not isinstance(text, str):
        raise DataError("Timestamp must be a minute-resolution string")
    return _parsed_minute_text(text)


def _signature(info: os.stat_result) -> Tuple[int, int, int, int, int]:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _source_stat(path: Path) -> os.stat_result:
    try:
        info = path.stat()
    except OSError as exc:
        raise DataError("Cannot inspect the input CSV: %s" % exc) from exc
    if not stat.S_ISREG(info.st_mode):
        raise DataError("The input must be a regular CSV file")
    return info


def _assert_unchanged(path: Path, expected_signature: Tuple[int, int, int, int, int]) -> None:
    if _signature(_source_stat(path)) != expected_signature:
        raise DataError("The source CSV changed while it was being read; no completed cache was accepted")


def _hash_source(path: Path, progress: Optional[Callable[[str], None]], phase: str) -> Tuple[str, Tuple[int, int, int, int, int]]:
    initial = _signature(_source_stat(path))
    total = initial[2]
    _emit(progress, "%s: reading %.1f MiB" % (phase, total / (1024.0 ** 2)))
    digest = hashlib.sha256()
    read_bytes = 0
    last_notice = time.monotonic()
    try:
        with path.open("rb") as stream:
            if _signature(os.fstat(stream.fileno())) != initial:
                raise DataError("The source CSV changed before the read began")
            while True:
                block = stream.read(8 * 1024 * 1024)
                if not block:
                    break
                digest.update(block)
                read_bytes += len(block)
                now = time.monotonic()
                if now - last_notice >= 2.0:
                    _emit(progress, "%s: %.1f / %.1f MiB" % (phase, read_bytes / (1024.0 ** 2), total / (1024.0 ** 2)))
                    last_notice = now
            if _signature(os.fstat(stream.fileno())) != initial:
                raise DataError("The source CSV changed during hashing")
    except OSError as exc:
        raise DataError("Cannot read the input CSV: %s" % exc) from exc
    _assert_unchanged(path, initial)
    if read_bytes != total:
        raise DataError("The source CSV size changed during hashing")
    return digest.hexdigest(), initial


def _database_progress(connection: sqlite3.Connection, progress: Optional[Callable[[str], None]], message: str) -> None:
    """Provide a heartbeat even while SQLite is building a large index."""
    _emit(progress, message)
    last_notice = [time.monotonic()]

    def heartbeat() -> int:
        now = time.monotonic()
        if now - last_notice[0] >= 2.0:
            _emit(progress, message + " (working)")
            last_notice[0] = now
        return 0

    connection.set_progress_handler(heartbeat, 50000)


def _connect_read_only(database: Path) -> sqlite3.Connection:
    try:
        return sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    except (OSError, sqlite3.Error) as exc:
        raise DataError("Cannot open the completed local cache: %s" % exc) from exc


def _metadata(connection: sqlite3.Connection, source_sha256: str) -> Dict[str, Any]:
    try:
        record = connection.execute("SELECT value FROM metadata WHERE key='manifest'").fetchone()
        if record is None:
            raise DataError("Cache has no completed metadata; choose a fresh cache directory")
        manifest = json.loads(record[0])
        if not isinstance(manifest, dict):
            raise DataError("Cache metadata is invalid")
        version = manifest.get("schema_version")
        if not isinstance(version, int) or isinstance(version, bool) or version != CACHE_VERSION or manifest.get("complete") is not True:
            raise DataError("Cache is incomplete or from an incompatible adapter version")
        if manifest.get("source_sha256") != source_sha256:
            raise DataError("Cache source identity does not match the selected CSV")
        count = manifest.get("row_count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise DataError("Cache row count is invalid")
        size = manifest.get("source_size_bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise DataError("Cache source size is invalid")
        if "minimum_minute" not in manifest or "maximum_minute" not in manifest:
            raise DataError("Cache time-range metadata is incomplete")
        minimum, maximum = manifest["minimum_minute"], manifest["maximum_minute"]
        if count == 0:
            if minimum is not None or maximum is not None:
                raise DataError("Empty-cache time-range metadata is invalid")
        elif (not isinstance(minimum, int) or isinstance(minimum, bool)
              or not isinstance(maximum, int) or isinstance(maximum, bool)
              or minimum > maximum):
            raise DataError("Cache time-range metadata is invalid")
        header = manifest.get("header")
        if not isinstance(header, list) or header[:5] != _HEADER_PREFIX or not all(isinstance(x, str) for x in header):
            raise DataError("Cache header is not the required positional IBM schema")
        columns = [row[1] for row in connection.execute("PRAGMA table_info(events)")]
        if columns != ["row_index", "source", "target", "minute"]:
            raise DataError("Cache event table has an incompatible schema")
        indexes = {row[1] for row in connection.execute("PRAGMA index_list(events)")}
        if not {"events_target_minute", "events_minute"} <= indexes:
            raise DataError("Cache indexes are incomplete")
        return manifest
    except (json.JSONDecodeError, TypeError, sqlite3.Error) as exc:
        raise DataError("Invalid or incomplete local cache: %s" % exc) from exc


def _verify_cache_rows(connection: sqlite3.Connection, manifest: Dict[str, Any], progress: Optional[Callable[[str], None]]) -> None:
    _database_progress(connection, progress, "Checking the completed cache row range")
    try:
        row = connection.execute("SELECT COUNT(*), MIN(row_index), MAX(row_index), MIN(minute), MAX(minute) FROM events").fetchone()
        count = manifest["row_count"]
        wanted = (count, 0 if count else None, count - 1 if count else None,
                  manifest.get("minimum_minute"), manifest.get("maximum_minute"))
        if tuple(row) != wanted:
            raise DataError("The cache is incomplete or inconsistent with its stored source metadata")
    finally:
        connection.set_progress_handler(None, 0)


def _cache_result(database: Path, manifest: Dict[str, Any], reused: bool) -> Dict[str, Any]:
    return {
        "database": str(database.resolve()),
        "source_sha256": manifest["source_sha256"],
        "source_size_bytes": manifest["source_size_bytes"],
        "row_count": manifest["row_count"],
        "cache_reused": reused,
        "header": manifest["header"],
        "minimum_minute": manifest["minimum_minute"],
        "maximum_minute": manifest["maximum_minute"],
        "cache_schema_version": CACHE_VERSION,
        "format": "ibm_raw_positional_csv",
        "time_basis": "naive source calendar minutes since 1970-01-01; no timezone assigned",
        "event_id_basis": "row:N; zero-based original CSV data-record position, excluding the header",
    }


def build_cache(csv_path: Any, cache_dir: Any, expected_sha256: Optional[str] = None,
                progress: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Hash the original CSV, stream it to a completed disk cache, or reuse one.

    The CSV is opened read-only. Only this adapter's cache directory is written.
    A failed import leaves no published cache. Existing invalid caches are not
    overwritten: select a new cache directory or move the invalid cache aside.
    """
    _validate_progress(progress)
    try:
        source = Path(csv_path).expanduser().resolve()
        cache_root = Path(cache_dir).expanduser().resolve()
    except (TypeError, OSError) as exc:
        raise DataError("Invalid input or cache path: %s" % exc) from exc
    if expected_sha256 is not None:
        if not isinstance(expected_sha256, str) or not _DIGEST.fullmatch(expected_sha256):
            raise DataError("expected_sha256 must be a complete 64-character SHA-256 value")
        expected_sha256 = expected_sha256.lower()
    source_hash, source_signature = _hash_source(source, progress, "Checking source SHA-256")
    if expected_sha256 is not None and source_hash != expected_sha256:
        raise DataError("Source SHA-256 does not match this preset. Select the original raw CSV, not a sorted or edited copy. Expected %s; received %s" % (expected_sha256, source_hash))
    _emit(progress, "Source SHA-256 checked: " + source_hash)
    try:
        cache_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as exc:
        raise DataError("Cannot create the local cache directory: %s" % exc) from exc
    database = cache_root / ("ibm_raw_v%d_%s.sqlite3" % (CACHE_VERSION, source_hash))
    if database == source:
        raise DataError("The source CSV cannot also be the cache output path")
    if database.exists():
        connection = _connect_read_only(database)
        try:
            manifest = _metadata(connection, source_hash)
            if manifest.get("source_size_bytes") != source_signature[2]:
                raise DataError("Cache source size does not match the input CSV")
            _verify_cache_rows(connection, manifest, progress)
        except sqlite3.Error as exc:
            raise DataError("Cannot verify the completed cache: %s" % exc) from exc
        finally:
            connection.close()
        _assert_unchanged(source, source_signature)
        _emit(progress, "Reusing the completed local cache (%s rows)" % format(manifest["row_count"], ","))
        return _cache_result(database, manifest, True)

    temporary = None  # type: Optional[Path]
    connection = None  # type: Optional[sqlite3.Connection]
    try:
        handle, name = tempfile.mkstemp(prefix=".ibm-import-", suffix=".sqlite3", dir=str(cache_root))
        os.close(handle)
        temporary = Path(name)
        connection = sqlite3.connect(str(temporary))
        # This is an unpublished, disposable cache. It is flushed before its
        # completed metadata is atomically promoted to the final filename.
        connection.execute("PRAGMA journal_mode=OFF")
        connection.execute("PRAGMA synchronous=OFF")
        connection.execute("PRAGMA cache_size=-16384")
        connection.execute("CREATE TABLE events (row_index INTEGER PRIMARY KEY, source TEXT NOT NULL, target TEXT NOT NULL, minute INTEGER NOT NULL)")
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        _emit(progress, "Importing the CSV into a local disk cache; the source file remains unchanged")
        count = 0
        minimum = None  # type: Optional[int]
        maximum = None  # type: Optional[int]
        pending = []  # type: List[Tuple[int, str, str, int]]
        last_notice = time.monotonic()
        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            if _signature(os.fstat(stream.fileno())) != source_signature:
                raise DataError("The source CSV changed before import")
            reader = csv.reader(stream, strict=True)
            header = next(reader, None)
            if header is None or header[:5] != _HEADER_PREFIX:
                raise DataError("Expected IBM columns Timestamp, From Bank, Account, To Bank, Account in the first five positions")
            for row_index, row in enumerate(reader):
                if len(row) != len(header):
                    raise DataError("CSV data record %d has %d columns; expected %d. No records were silently skipped" % (row_index, len(row), len(header)))
                try:
                    minute = parse_minute(row[0])
                    source_node = node_key(row[1], row[2])
                    target_node = node_key(row[3], row[4])
                except DataError as exc:
                    raise DataError("Invalid CSV data record %d: %s" % (row_index, exc)) from exc
                pending.append((row_index, source_node, target_node, minute))
                minimum = minute if minimum is None else min(minimum, minute)
                maximum = minute if maximum is None else max(maximum, minute)
                count += 1
                if len(pending) >= _BATCH_ROWS:
                    connection.executemany("INSERT INTO events VALUES (?,?,?,?)", pending)
                    connection.commit()
                    pending.clear()
                    now = time.monotonic()
                    if count % 100000 == 0 or now - last_notice >= 2.0:
                        _emit(progress, "Imported %s original CSV records" % format(count, ","))
                        last_notice = now
            if pending:
                connection.executemany("INSERT INTO events VALUES (?,?,?,?)", pending)
                connection.commit()
            if _signature(os.fstat(stream.fileno())) != source_signature:
                raise DataError("The source CSV changed during import")
        _assert_unchanged(source, source_signature)
        # The second digest also rejects an in-place modification that happened
        # during parsing; stat checks reject source replacement/metadata change.
        after_hash, after_signature = _hash_source(source, progress, "Verifying the source after import")
        if after_hash != source_hash or after_signature != source_signature:
            raise DataError("The source CSV changed during import; the new cache was discarded")

        _database_progress(connection, progress, "Building the receiver/time cache index")
        connection.execute("CREATE INDEX events_target_minute ON events(target, minute)")
        _database_progress(connection, progress, "Building the window-time cache index")
        connection.execute("CREATE INDEX events_minute ON events(minute)")
        connection.set_progress_handler(None, 0)
        manifest = {
            "schema_version": CACHE_VERSION,
            "complete": True,
            "source_sha256": source_hash,
            "source_size_bytes": source_signature[2],
            "row_count": count,
            "header": header,
            "minimum_minute": minimum,
            "maximum_minute": maximum,
            "format": "ibm_raw_positional_csv",
            "time_basis": "naive source minutes",
            "cost_policy": "unit costs; every event optional",
        }
        connection.execute("INSERT INTO metadata VALUES ('manifest', ?)", (json.dumps(manifest, sort_keys=True),))
        connection.commit()
        connection.close()
        connection = None
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        _assert_unchanged(source, source_signature)
        if database.exists():
            # Another invocation may have completed the same owned cache while
            # this import was running. Preserve and verify that completed copy.
            other = _connect_read_only(database)
            try:
                other_manifest = _metadata(other, source_hash)
                _verify_cache_rows(other, other_manifest, progress)
                if other_manifest != manifest:
                    raise DataError("A concurrent cache has inconsistent source metadata")
            finally:
                other.close()
            temporary.unlink()
            temporary = None
            return _cache_result(database, other_manifest, True)
        os.replace(str(temporary), str(database))
        temporary = None
        _emit(progress, "Completed local cache: %s original records" % format(count, ","))
        return _cache_result(database, manifest, False)
    except DataError:
        raise
    except (OSError, UnicodeError, csv.Error, sqlite3.Error) as exc:
        raise DataError("CSV import did not complete: %s" % exc) from exc
    finally:
        if connection is not None:
            connection.close()
        if temporary is not None:
            # Only files created by this invocation are removed. The original
            # CSV and every published cache/result are untouched on failure.
            for suffix in ("", "-journal", "-wal", "-shm"):
                leftover = Path(str(temporary) + suffix)
                try:
                    if leftover.exists():
                        leftover.unlink()
                except OSError:
                    pass


def _nonnegative_int(value: Any, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise DataError("%s must be a nonnegative integer" % name)
    return value


def _chunks(values: Iterable[str]) -> Iterable[List[str]]:
    ordered = sorted(values)
    for start in range(0, len(ordered), _QUERY_CHUNK):
        yield ordered[start:start + _QUERY_CHUNK]


def _incoming(connection: sqlite3.Connection, targets: Iterable[str], start: int, cutoff: int) -> Iterable[Tuple[int, str, str, int]]:
    for chunk in _chunks(targets):
        placeholders = ",".join("?" for _ in chunk)
        query = "SELECT row_index,source,target,minute FROM events WHERE target IN (%s) AND minute>=? AND minute<?" % placeholders
        for row in connection.execute(query, list(chunk) + [start, cutoff]):
            yield row


def extract_context(cache_info: Dict[str, Any], root_bank: Any, root_account: Any,
                    cutoff_text: str, window_minutes: int = 1440,
                    max_context_events: int = 5000, max_vertices: int = 5000,
                    max_discovery_events: int = 200000,
                    progress: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Extract the complete induced incoming-three-hop context in the window.

    No loop/crossedge/root-outgoing edge is removed to make a graph eligible.
    max_discovery_events counts distinct candidate CSV records examined across
    the BFS and final induced scan. Repeated reads of one record count once.
    Resource caps raise an error and never return a truncated context.
    """
    _validate_progress(progress)
    if not isinstance(cache_info, dict):
        raise DataError("cache_info must be the completed build_cache result")
    try:
        database = Path(cache_info["database"])
        source_hash = cache_info["source_sha256"]
    except (KeyError, TypeError) as exc:
        raise DataError("cache_info lacks a valid database/source identity") from exc
    if not isinstance(source_hash, str) or not _DIGEST.fullmatch(source_hash):
        raise DataError("cache_info has an invalid source SHA-256")
    window_minutes = _nonnegative_int(window_minutes, "window_minutes")
    if window_minutes == 0:
        raise DataError("window_minutes must be positive")
    max_context_events = _nonnegative_int(max_context_events, "max_context_events")
    max_vertices = _nonnegative_int(max_vertices, "max_vertices")
    max_discovery_events = _nonnegative_int(max_discovery_events, "max_discovery_events")
    root = node_key(root_bank, root_account)
    cutoff = parse_minute(cutoff_text)
    start = cutoff - window_minutes
    if start < -(2 ** 63) or cutoff > 2 ** 63 - 1:
        raise DataError("The requested minute range is outside SQLite's signed integer range")
    if max_vertices < 1:
        raise DataError("The extraction vertex cap cannot hold even the root", code="resource_limit")
    connection = _connect_read_only(database)
    try:
        manifest = _metadata(connection, source_hash.lower())
        if cache_info.get("row_count") != manifest["row_count"]:
            raise DataError("cache_info row count does not match the completed cache")
        _database_progress(connection, progress, "Counting all transactions in the declared source-time window")
        window_count = connection.execute("SELECT COUNT(*) FROM events WHERE minute>=? AND minute<?", (start, cutoff)).fetchone()[0]
        connection.set_progress_handler(None, 0)
        seen_candidates = set()  # type: set
        visited = {root}
        frontier = {root}
        last_notice = [time.monotonic()]

        def observe(row_index: int) -> None:
            if row_index not in seen_candidates:
                if len(seen_candidates) >= max_discovery_events:
                    raise DataError("The extraction candidate-event cap was reached; no complete context was returned", code="resource_limit")
                seen_candidates.add(row_index)
            now = time.monotonic()
            if now - last_notice[0] >= 2.0:
                _emit(progress, "Examined %s distinct context candidates" % format(len(seen_candidates), ","))
                last_notice[0] = now

        for depth in range(3):
            if not frontier:
                break
            _emit(progress, "Incoming-neighbor expansion %d of 3" % (depth + 1))
            new_vertices = set()  # type: set
            for row_index, source_node, _target_node, _minute in _incoming(connection, frontier, start, cutoff):
                observe(row_index)
                if source_node not in visited and source_node not in new_vertices:
                    if len(visited) + len(new_vertices) >= max_vertices:
                        raise DataError("The extraction account cap was reached; no complete context was returned", code="resource_limit")
                    new_vertices.add(source_node)
            visited.update(new_vertices)
            frontier = new_vertices

        _emit(progress, "Retaining every original window event internal to the discovered accounts")
        selected = []  # type: List[Tuple[int, str, str, int]]
        for row_index, source_node, target_node, minute in _incoming(connection, visited, start, cutoff):
            observe(row_index)
            if source_node in visited:
                if len(selected) >= max_context_events:
                    raise DataError("The complete induced-context event cap was reached; no truncated context was returned", code="resource_limit")
                selected.append((row_index, source_node, target_node, minute))
        selected.sort(key=lambda row: row[0])
        events = [
            {"id": "row:%d" % row_index, "source": source_node,
             "target": target_node, "time": minute, "cost": 1, "status": "optional"}
            for row_index, source_node, target_node, minute in selected
        ]
        _emit(progress, "Complete context: %d original events, %d accounts; global window: %s events" % (len(events), len(visited), format(window_count, ",")))
        return {
            "root": root,
            "events": events,
            "cutoff_minute": cutoff,
            "window_start_minute": start,
            "window_minutes": window_minutes,
            "global_window_event_count": window_count,
            "vertex_count": len(visited),
            "context_event_count": len(events),
            "discovery_event_count": len(seen_candidates),
            "context_definition": "all window events with both endpoints in the complete incoming-distance-at-most-three vertex set",
            "window_definition": "lower inclusive, cutoff exclusive; all target-minute events excluded",
        }
    except DataError:
        raise
    except (sqlite3.Error, OSError) as exc:
        raise DataError("The local context read did not complete: %s" % exc) from exc
    finally:
        connection.close()
