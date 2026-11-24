CREATE TABLE model_records (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL REFERENCES brands(id),
    sha256 TEXT NOT NULL,
    document TEXT NOT NULL,
    UNIQUE(brand_id,sha256)
);
INSERT INTO schema_version VALUES (3);
