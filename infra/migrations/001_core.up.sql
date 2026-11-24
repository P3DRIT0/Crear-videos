CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
CREATE TABLE brands (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE campaigns (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL REFERENCES brands(id),
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 100),
    objective TEXT NOT NULL CHECK (length(objective) BETWEEN 1 AND 1000),
    created_at TEXT NOT NULL,
    UNIQUE (brand_id, id)
);
CREATE INDEX campaigns_by_brand ON campaigns(brand_id, created_at, id);
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    label TEXT NOT NULL CHECK (length(label) BETWEEN 1 AND 100),
    state TEXT NOT NULL CHECK (state IN ('pending', 'succeeded', 'failed')),
    sha256 TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (brand_id, campaign_id) REFERENCES campaigns(brand_id, id),
    CHECK ((state = 'succeeded' AND sha256 IS NOT NULL AND length(sha256) = 64)
        OR (state <> 'succeeded' AND sha256 IS NULL)),
    CHECK ((state = 'failed') = (error IS NOT NULL))
);
CREATE INDEX jobs_by_campaign ON jobs(brand_id, campaign_id);
CREATE INDEX jobs_by_brand ON jobs(brand_id, created_at, id);
CREATE TABLE creations (
    brand_id TEXT NOT NULL REFERENCES brands(id),
    request_key TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    response TEXT NOT NULL,
    PRIMARY KEY (brand_id, request_key)
);
INSERT INTO brands (id, name) VALUES ('720c761b-64d9-4d3c-9dd5-b1dc2e82edeb', 'Retrobay');
INSERT INTO schema_version (version) VALUES (1);
