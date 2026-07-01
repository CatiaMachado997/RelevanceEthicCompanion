-- Migration 007: Folders for organizing conversations
-- Users can create folders to group their chat conversations.

CREATE TABLE IF NOT EXISTS folders (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    color       TEXT,                                        -- optional tag colour, e.g. '#4a7c59'
    position    INT         NOT NULL DEFAULT 0,              -- display order within user's folder list
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_folders_user_id ON folders (user_id, position, created_at);

-- Add folder_id to conversations. NULL = unfoldered ("root").
ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS folder_id UUID REFERENCES folders(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_conversations_folder_id ON conversations (folder_id);
