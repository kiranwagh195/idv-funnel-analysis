-- PostgreSQL schema + load (the Python pipeline uses SQLite; queries 01-04 are portable)
CREATE TABLE verification_sessions (
    session_id        INT PRIMARY KEY,
    doc_type          TEXT,
    device_type       TEXT,
    city_tier         TEXT,
    app_version       TEXT,
    started_at        TIMESTAMP,
    reached_upload    SMALLINT,
    upload_ok         SMALLINT,
    ocr_ok            SMALLINT,
    face_ok           SMALLINT,
    approved          SMALLINT,
    failure_stage     TEXT,
    failure_reason    TEXT,
    ocr_latency_ms    NUMERIC,
    total_latency_ms  NUMERIC
);
-- \copy verification_sessions FROM 'data/verification_sessions.csv' CSV HEADER
