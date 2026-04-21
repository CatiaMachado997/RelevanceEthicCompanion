-- Migration 008: Unique folder name per user.
-- Prevents accidental duplicates like two "Work" folders.
-- Case-insensitive via LOWER() so "Work" and "work" collide.

CREATE UNIQUE INDEX IF NOT EXISTS uniq_folders_user_lower_name
    ON folders (user_id, LOWER(name));
