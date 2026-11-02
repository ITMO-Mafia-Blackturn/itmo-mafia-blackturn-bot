CREATE TABLE IF NOT EXISTS tournaments (
    id SERIAL PRIMARY KEY,
    description VARCHAR(700) NOT NULL,
    place VARCHAR(150) NOT NULL,
    date TIMESTAMP NOT NULL,
    expired BOOLEAN NOT NULL DEFAULT FALSE,
    registry_deadline TIMESTAMP NOT NULL,
    capacity INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tournament_players (
    id SERIAL PRIMARY KEY,
    user_profile_id INTEGER NOT NULL REFERENCES user_profiles(id),
    polemica_id INTEGER NOT NULL,
    polemica_nickname VARCHAR(100) NOT NULL,
    photo BYTEA
);

ALTER TABLE tournament_players
    ADD COLUMN IF NOT EXISTS polemica_id INTEGER;
ALTER TABLE tournament_players
    ADD COLUMN IF NOT EXISTS polemica_nickname VARCHAR(100);
ALTER TABLE tournament_players
    ADD COLUMN IF NOT EXISTS photo BYTEA;
ALTER TABLE tournament_players
    ALTER COLUMN polemica_nickname TYPE VARCHAR(100)
    USING polemica_nickname::text;

CREATE TABLE IF NOT EXISTS tournament_registries (
    id SERIAL PRIMARY KEY,
    tournament_player_id INTEGER NOT NULL REFERENCES tournament_players(id),
    tournament_id INTEGER REFERENCES tournaments(id),
    approved BOOLEAN NOT NULL DEFAULT FALSE,
    rejected BOOLEAN NOT NULL DEFAULT FALSE,
    rejection_reason VARCHAR(500)
);

ALTER TABLE tournament_registries
    ADD COLUMN IF NOT EXISTS tournament_id INTEGER REFERENCES tournaments(id);
ALTER TABLE tournament_registries
    ADD COLUMN IF NOT EXISTS approved BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE tournament_registries
    ADD COLUMN IF NOT EXISTS rejected BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE tournament_registries
    ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR(500);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'tournament_registries'
          AND column_name = 'tournament'
    ) THEN
        ALTER TABLE tournament_registries
            ALTER COLUMN tournament SET DEFAULT FALSE;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_tournament_registries_tournament_id
    ON tournament_registries(tournament_id);
