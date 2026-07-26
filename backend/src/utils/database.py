from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Tuple

from utils.api_logger import get_logger

log = get_logger(__name__)

SCHEMA_STATEMENTS: list[str] = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA busy_timeout=60000;",
    "PRAGMA foreign_keys = ON;",

    """CREATE TABLE IF NOT EXISTS Analyses (
        ID             TEXT PRIMARY KEY,
        VideoPath      TEXT    NOT NULL,
        VideoFilename  TEXT    NOT NULL,
        Condition      TEXT    NOT NULL,
        VLMProvider    TEXT,
        Model          TEXT,
        GridRows       INTEGER,
        GridCols       INTEGER,
        SamplingRate   INTEGER,
        VLMDelay       REAL    DEFAULT 0.0,
        VLMQuantization TEXT   DEFAULT 'none',
        MaxRetries     INTEGER DEFAULT 3,
        AudioProvider  TEXT    DEFAULT 'panns',
        AudioModel     TEXT,
        AudioQuantization TEXT DEFAULT 'none',
        Stage          TEXT    NOT NULL    DEFAULT 'queued',
        CreatedAt      TEXT    NOT NULL,
        CompletedAt    TEXT
    );""",

    """CREATE TABLE IF NOT EXISTS VisualPerFrame (
        AnalysisID  TEXT    NOT NULL,
        Frame       INTEGER NOT NULL,
        ClassID     INTEGER NOT NULL,
        Class       TEXT    NOT NULL,
        Block       INTEGER NOT NULL,
        Description TEXT    NOT NULL,
        PRIMARY KEY (AnalysisID, Frame, ClassID, Block)
    );""",
    "CREATE INDEX IF NOT EXISTS idx_VisualPerFrame_aid ON VisualPerFrame (AnalysisID);",
    "CREATE INDEX IF NOT EXISTS idx_VisualPerFrame_frame ON VisualPerFrame (Frame);",

    """CREATE TABLE IF NOT EXISTS VisualRelation (
        AnalysisID   TEXT    NOT NULL,
        Frame        INTEGER NOT NULL,
        RelationID   INTEGER NOT NULL,
        RelationType TEXT    NOT NULL,
        ClassID      INTEGER NOT NULL,
        PRIMARY KEY (AnalysisID, Frame, RelationID, ClassID)
    );""",
    "CREATE INDEX IF NOT EXISTS idx_VisualRelation_aid  ON VisualRelation (AnalysisID);",
    "CREATE INDEX IF NOT EXISTS idx_VisualRelation_frame ON VisualRelation (Frame);",

    """CREATE TABLE IF NOT EXISTS VisualPerInterval (
        RelationID   INTEGER PRIMARY KEY AUTOINCREMENT,
        AnalysisID   TEXT    NOT NULL,
        StartFrame   INTEGER NOT NULL,
        EndFrame     INTEGER NOT NULL,
        RelationType TEXT    NOT NULL
    );""",
    "CREATE INDEX IF NOT EXISTS idx_VisualPerInterval_aid   ON VisualPerInterval (AnalysisID);",
    "CREATE INDEX IF NOT EXISTS idx_VisualPerInterval_start ON VisualPerInterval (StartFrame);",
    "CREATE INDEX IF NOT EXISTS idx_VisualPerInterval_type  ON VisualPerInterval (RelationType);",

    """CREATE TABLE IF NOT EXISTS VisualParticipant (
        RelationID  INTEGER NOT NULL REFERENCES VisualPerInterval(RelationID),
        ClassID     INTEGER NOT NULL,
        Class       TEXT    NOT NULL,
        PRIMARY KEY (RelationID, ClassID)
    );""",

    """CREATE TABLE IF NOT EXISTS SoundPerInterval (
        SoundIntervalID INTEGER PRIMARY KEY AUTOINCREMENT,
        AnalysisID      TEXT    NOT NULL,
        StartFrame      INTEGER NOT NULL,
        EndFrame        INTEGER NOT NULL,
        SoundClass      TEXT    NOT NULL,
        Confidence      REAL    DEFAULT 1.0
    );""",
    "CREATE INDEX IF NOT EXISTS idx_SoundPerInterval_aid   ON SoundPerInterval (AnalysisID);",
    "CREATE INDEX IF NOT EXISTS idx_SoundPerInterval_start ON SoundPerInterval (StartFrame);",
    "CREATE INDEX IF NOT EXISTS idx_SoundPerInterval_end   ON SoundPerInterval (EndFrame);",
    "CREATE INDEX IF NOT EXISTS idx_SoundPerInterval_class ON SoundPerInterval (SoundClass);",
]


def setup_database(db_path: Path) -> Tuple[sqlite3.Connection, sqlite3.Cursor]:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    log.info("Setting up database at %s", db_path)
    conn = sqlite3.connect(str(db_path), timeout=60.0)
    cursor = conn.cursor()
    for stmt in SCHEMA_STATEMENTS:
        cursor.execute(stmt)
    conn.commit()
    return conn, cursor
