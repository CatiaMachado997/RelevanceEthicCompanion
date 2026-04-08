-- Tool Marketplace migration

CREATE TABLE IF NOT EXISTS tool_definitions (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT,
    auth_type     TEXT NOT NULL CHECK (auth_type IN ('oauth', 'apikey', 'mcp')),
    oauth_scopes  TEXT[] DEFAULT '{}',
    actions       JSONB NOT NULL DEFAULT '[]',
    icon_url      TEXT,
    enabled       BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_tool_connections (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tool_id        TEXT NOT NULL REFERENCES tool_definitions(id),
    enabled        BOOLEAN DEFAULT true,
    credentials    JSONB DEFAULT '{}',
    mcp_url        TEXT,
    connected_at   TIMESTAMPTZ DEFAULT now(),
    last_used_at   TIMESTAMPTZ,
    UNIQUE (user_id, tool_id)
);

CREATE TABLE IF NOT EXISTS tool_permissions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tool_id      TEXT NOT NULL,
    action_name  TEXT NOT NULL,
    trust_level  TEXT NOT NULL CHECK (trust_level IN ('ask', 'allow', 'deny')),
    granted_at   TIMESTAMPTZ DEFAULT now(),
    expires_at   TIMESTAMPTZ,
    UNIQUE (user_id, tool_id, action_name)
);

-- Seed catalogue
INSERT INTO tool_definitions (id, name, description, auth_type, oauth_scopes, actions, icon_url) VALUES
(
    'google_calendar_write',
    'Google Calendar',
    'Read and create calendar events',
    'oauth',
    ARRAY['https://www.googleapis.com/auth/calendar'],
    '[
        {"name": "create_event", "description": "Create a calendar event", "risk_level": "low"},
        {"name": "update_event", "description": "Update an existing event", "risk_level": "medium"}
    ]'::jsonb,
    '/icons/google-calendar.svg'
),
(
    'gmail_write',
    'Gmail',
    'Read emails and send replies',
    'oauth',
    ARRAY['https://www.googleapis.com/auth/gmail.send'],
    '[
        {"name": "create_draft", "description": "Create an email draft", "risk_level": "low"},
        {"name": "send_reply", "description": "Send an email reply", "risk_level": "high"}
    ]'::jsonb,
    '/icons/gmail.svg'
),
(
    'notion',
    'Notion',
    'Read pages and databases, create notes',
    'oauth',
    ARRAY[''],
    '[
        {"name": "search_pages", "description": "Search Notion pages", "risk_level": "low"},
        {"name": "create_page", "description": "Create a Notion page", "risk_level": "medium"},
        {"name": "append_block", "description": "Append content to a page", "risk_level": "low"}
    ]'::jsonb,
    '/icons/notion.svg'
),
(
    'slack',
    'Slack',
    'Read messages and send replies',
    'oauth',
    ARRAY['channels:read', 'chat:write'],
    '[
        {"name": "read_channel", "description": "Read recent messages from a channel", "risk_level": "low"},
        {"name": "send_message", "description": "Send a message to a channel", "risk_level": "high"}
    ]'::jsonb,
    '/icons/slack.svg'
),
(
    'github',
    'GitHub',
    'Read issues and PRs, create issues',
    'oauth',
    ARRAY['repo', 'read:user'],
    '[
        {"name": "list_issues", "description": "List open issues in a repo", "risk_level": "low"},
        {"name": "create_issue", "description": "Create a GitHub issue", "risk_level": "medium"},
        {"name": "add_comment", "description": "Add a comment to an issue or PR", "risk_level": "medium"}
    ]'::jsonb,
    '/icons/github.svg'
),
(
    'mcp_custom',
    'Custom MCP Server',
    'Connect any Model Context Protocol server',
    'mcp',
    ARRAY[]::TEXT[],
    '[]'::jsonb,
    '/icons/mcp.svg'
)
ON CONFLICT (id) DO NOTHING;
