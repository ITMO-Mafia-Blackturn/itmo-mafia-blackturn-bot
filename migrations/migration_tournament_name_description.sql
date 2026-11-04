DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'tournaments'
          AND column_name = 'description'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'tournaments'
          AND column_name = 'name'
    ) THEN
        ALTER TABLE tournaments RENAME COLUMN description TO name;
    END IF;
END $$;

ALTER TABLE tournaments
    ADD COLUMN IF NOT EXISTS description VARCHAR(700) NOT NULL DEFAULT '';

ALTER TABLE tournaments
    ALTER COLUMN description DROP DEFAULT;
