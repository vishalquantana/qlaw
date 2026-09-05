-- GST AAR ruling ontology — structured layer over raw rulings
-- Applied to data/aar.db. Every table traces back to rulings.id, which carries
-- the provenance chain (pdf_url → official gazette PDF).

CREATE TABLE IF NOT EXISTS ruling_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruling_id INTEGER NOT NULL REFERENCES rulings(id),
    kind TEXT,                 -- 'good' | 'service' | 'both' | 'unspecified'
    description TEXT,          -- what the applicant supplies / asks about
    hsn_sac TEXT,              -- normalized code (digits only)
    hsn_sac_raw TEXT,          -- as written in the document (may include dashes)
    rate_proposed TEXT,        -- rate claimed by applicant, e.g. '12%'
    rate_held TEXT,            -- rate determined by the Authority
    source TEXT                -- 'brief' | 'llm' | 'regex'
);
CREATE INDEX IF NOT EXISTS idx_subjects_ruling ON ruling_subjects(ruling_id);
CREATE INDEX IF NOT EXISTS idx_subjects_hsn ON ruling_subjects(hsn_sac);

CREATE TABLE IF NOT EXISTS ruling_citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruling_id INTEGER NOT NULL REFERENCES rulings(id),
    kind TEXT NOT NULL,        -- 'notification' | 'section' | 'rule' | 'schedule_entry' | 'precedent' | 'circular'
    identifier TEXT NOT NULL,  -- normalized: '13/2020-CT', 'CGST s.2(93)', 'Rule 89', 'Raj/AAR/2026-27/10'
    raw_text TEXT,             -- as it appeared
    description TEXT,          -- what it concerns, when available
    source TEXT                -- 'brief' | 'llm' | 'regex'
);
CREATE INDEX IF NOT EXISTS idx_citations_ruling ON ruling_citations(ruling_id);
CREATE INDEX IF NOT EXISTS idx_citations_ident ON ruling_citations(identifier);

CREATE TABLE IF NOT EXISTS ruling_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruling_id INTEGER NOT NULL REFERENCES rulings(id),
    q_no TEXT,                 -- '1', '2(a)'… as numbered in the application
    question TEXT NOT NULL,
    outcome TEXT,              -- 'answered' | 'withdrawn' | 'rejected' | 'no_ruling' | NULL
    held_summary TEXT,         -- what the Authority actually decided on this question
    source TEXT                -- 'brief' | 'llm'
);
CREATE INDEX IF NOT EXISTS idx_questions_ruling ON ruling_questions(ruling_id);

CREATE TABLE IF NOT EXISTS ruling_tags (
    ruling_id INTEGER NOT NULL REFERENCES rulings(id),
    tag TEXT NOT NULL,         -- sector/topic: 'education', 'construction', 'it-services', 'classification'…
    source TEXT,               -- 'llm' | 'brief'
    PRIMARY KEY (ruling_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON ruling_tags(tag);

-- outcome + entity facts live as columns on rulings (added if missing)
