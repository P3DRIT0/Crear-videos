CREATE TABLE productions (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    state TEXT NOT NULL,
    revision INTEGER NOT NULL,
    document TEXT NOT NULL,
    FOREIGN KEY (brand_id, campaign_id) REFERENCES campaigns(brand_id, id)
);
CREATE INDEX production_queue ON productions(state, id);
CREATE TABLE production_events (
    production_id TEXT NOT NULL REFERENCES productions(id),
    revision INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    message TEXT NOT NULL,
    PRIMARY KEY(production_id, revision)
);
CREATE TABLE characters (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL REFERENCES brands(id),
    name TEXT NOT NULL,
    version INTEGER NOT NULL,
    document TEXT NOT NULL,
    UNIQUE(brand_id, name, version)
);
CREATE TABLE publications (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id),
    brand_id TEXT NOT NULL REFERENCES brands(id),
    artifact_hash TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    local_day TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('scheduled','dry_run','cancelled')),
    copy TEXT NOT NULL,
    UNIQUE(production_id, artifact_hash)
);
INSERT INTO schema_version VALUES (2);
