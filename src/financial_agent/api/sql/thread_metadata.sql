-- Metadados das threads para a retenção (data-model.md §1). Idempotente: roda a cada subida.
CREATE TABLE IF NOT EXISTS thread_metadata (
    thread_id text PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS thread_metadata_last_activity_at_idx
    ON thread_metadata (last_activity_at);
