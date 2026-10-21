-- Миграция для добавления поля passes_sent в таблицу events
-- Дата: 2025-09-16
-- Описание: Добавляет поле для отслеживания статуса отправки проходок

-- Добавить новое поле в таблицу events
ALTER TABLE events ADD COLUMN passes_sent BOOLEAN DEFAULT FALSE;

-- Обновить существующие записи (по умолчанию проходки не отправлены)
UPDATE events SET passes_sent = FALSE WHERE passes_sent IS NULL;

-- Добавить комментарий к полю для документации
COMMENT ON COLUMN events.passes_sent IS 'Флаг, указывающий, были ли отправлены проходки для мероприятия';

-- Триггер для обновления поля nickname при изменении поля nickname в user_profiles

-- CREATE OR REPLACE FUNCTION sync_event_signup()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     UPDATE event_singup
--     SET
--         full_name = NEW.nickname
--     WHERE chat_id = NEW.chat_id;

--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql;

-- CREATE TRIGGER user_profiles_sync
-- AFTER UPDATE OF nickname
-- ON user_profiles
-- FOR EACH ROW
-- EXECUTE FUNCTION sync_event_signup();