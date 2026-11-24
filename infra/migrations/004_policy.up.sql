CREATE TABLE brand_policy (
    brand_id TEXT PRIMARY KEY REFERENCES brands(id),
    document TEXT NOT NULL
);
INSERT INTO schema_version VALUES (4);
