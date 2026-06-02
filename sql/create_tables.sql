-- DDL for the racial equity grantmaking SQLite database.
-- Run once to initialize; re-run after dropping tables to reset.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------
-- foundations: one row per funder per tax year
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS foundations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    ein               TEXT    NOT NULL,
    name              TEXT,
    tax_year          INTEGER,
    state             TEXT,
    total_assets      REAL,
    total_revenue     REAL,
    total_grants_paid REAL,
    source            TEXT,           -- 'irs_990pf' | 'candid'
    created_at        TEXT DEFAULT (datetime('now')),
    UNIQUE (ein, tax_year)
);

CREATE INDEX IF NOT EXISTS idx_foundations_ein      ON foundations (ein);
CREATE INDEX IF NOT EXISTS idx_foundations_tax_year ON foundations (tax_year);
CREATE INDEX IF NOT EXISTS idx_foundations_state    ON foundations (state);

-- ---------------------------------------------------------
-- recipients: one row per recipient org (deduplicated by EIN)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS recipients (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ein          TEXT    UNIQUE,
    name         TEXT,
    ntee_code    TEXT,   -- full NTEE code e.g. 'R20'
    ntee_major   TEXT,   -- single letter major category e.g. 'R'
    state        TEXT,
    city         TEXT,
    total_revenue REAL,
    source       TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_recipients_ein        ON recipients (ein);
CREATE INDEX IF NOT EXISTS idx_recipients_ntee_major ON recipients (ntee_major);
CREATE INDEX IF NOT EXISTS idx_recipients_state      ON recipients (state);

-- ---------------------------------------------------------
-- grants: one row per individual grant payment
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS grants (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    funder_ein       TEXT    NOT NULL,
    recipient_ein    TEXT,
    recipient_name   TEXT,   -- raw name when EIN unavailable
    recipient_city   TEXT,
    recipient_state  TEXT,
    grant_amount     REAL    NOT NULL,
    tax_year         INTEGER,
    grant_purpose    TEXT,
    is_racial_equity INTEGER NOT NULL DEFAULT 0,  -- 0/1 boolean
    source           TEXT,           -- 'irs_990pf' | 'candid'
    object_id        TEXT,           -- IRS filing ObjectId for traceability
    created_at       TEXT DEFAULT (datetime('now'))
    -- Logical relationship: grants.funder_ein -> foundations.ein
    -- (not enforced as a SQL FK: foundations.ein is not unique on its own,
    --  and bulk loads span tables; joins use the indexes below)
);

CREATE INDEX IF NOT EXISTS idx_grants_funder_ein      ON grants (funder_ein);
CREATE INDEX IF NOT EXISTS idx_grants_recipient_ein   ON grants (recipient_ein);
CREATE INDEX IF NOT EXISTS idx_grants_tax_year        ON grants (tax_year);
CREATE INDEX IF NOT EXISTS idx_grants_is_racial_equity ON grants (is_racial_equity);
CREATE INDEX IF NOT EXISTS idx_grants_recipient_state ON grants (recipient_state);

-- ---------------------------------------------------------
-- demographics: Candid Demographics API data per org
-- (populated after Candid API access is granted)
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS demographics (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    ein                    TEXT    NOT NULL UNIQUE,
    leader_race_ethnicity  TEXT,   -- JSON array of reported categories
    board_poc_pct          REAL,   -- % board members who are people of color
    staff_poc_pct          REAL,
    leader_gender          TEXT,
    data_year              INTEGER,
    source                 TEXT DEFAULT 'candid_demographics',
    created_at             TEXT DEFAULT (datetime('now'))
    -- Logical relationship: demographics.ein -> recipients.ein
);

CREATE INDEX IF NOT EXISTS idx_demographics_ein ON demographics (ein);
