"""SQLite storage for incidents, their work notes and the deploy log."""
import sqlite3

INCIDENT_COLUMNS = ["number", "short_description", "description", "source", "opened_at", "resolved_at",
                    "priority_at_open", "priority", "service", "assignment_group", "root_cause_category",
                    "pattern_id", "duplicate_of", "state", "resolution", "close_code", "is_vague", "split"]

SCHEMA = """
DROP TABLE IF EXISTS work_note;
DROP TABLE IF EXISTS incident;
DROP TABLE IF EXISTS deploy;
CREATE TABLE incident (
  number TEXT PRIMARY KEY, short_description TEXT NOT NULL, description TEXT NOT NULL, source TEXT NOT NULL,
  opened_at TEXT NOT NULL, resolved_at TEXT, priority_at_open INTEGER, priority INTEGER, service TEXT,
  assignment_group TEXT, root_cause_category TEXT, pattern_id TEXT, duplicate_of TEXT, state TEXT NOT NULL,
  resolution TEXT, close_code TEXT, is_vague INTEGER NOT NULL DEFAULT 0, split TEXT NOT NULL);
CREATE INDEX incident_opened ON incident(opened_at);
CREATE TABLE work_note (
  id INTEGER PRIMARY KEY, number TEXT NOT NULL REFERENCES incident(number), at TEXT NOT NULL,
  author TEXT NOT NULL, role TEXT NOT NULL DEFAULT '', text TEXT NOT NULL, via_api INTEGER NOT NULL DEFAULT 0);
CREATE INDEX work_note_number ON work_note(number);
CREATE TABLE deploy (
  id TEXT PRIMARY KEY, service TEXT NOT NULL, deployed_at TEXT NOT NULL, version TEXT NOT NULL,
  summary TEXT NOT NULL, author TEXT NOT NULL);
CREATE INDEX deploy_service ON deploy(service, deployed_at);
"""


def connect(path: str = "data/timetravel.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def load(conn: sqlite3.Connection, incidents: list[dict], deploys: list[dict]) -> None:
    conn.executescript(SCHEMA)
    marks = ", ".join("?" for _ in INCIDENT_COLUMNS)
    conn.executemany(f"INSERT INTO incident ({', '.join(INCIDENT_COLUMNS)}) VALUES ({marks})",
                     [[int(i[c]) if c == "is_vague" else i[c] for c in INCIDENT_COLUMNS] for i in incidents])
    conn.executemany("INSERT INTO work_note (number, at, author, role, text) VALUES (?, ?, ?, ?, ?)",
                     [(i["number"], n["at"], n["author"], n["role"], n["text"]) for i in incidents for n in i["work_notes"]])
    conn.executemany("INSERT INTO deploy VALUES (:id, :service, :deployed_at, :version, :summary, :author)", deploys)
    conn.commit()
