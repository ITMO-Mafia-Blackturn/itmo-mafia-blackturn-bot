ALTER TABLE tournaments
    ADD COLUMN IF NOT EXISTS guest_capacity INTEGER;

UPDATE tournaments
SET guest_capacity = CEIL(capacity * 0.1)::INTEGER
WHERE guest_capacity IS NULL;

ALTER TABLE tournaments
    ALTER COLUMN guest_capacity SET DEFAULT 0,
    ALTER COLUMN guest_capacity SET NOT NULL;
