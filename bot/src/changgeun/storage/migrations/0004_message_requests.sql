CREATE TABLE message_requests(
 guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, message_id TEXT NOT NULL,
 request_id TEXT NOT NULL UNIQUE, actor_id TEXT NOT NULL, body_hash TEXT NOT NULL,
 policy_hash TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'running',
 created_at REAL NOT NULL, expires_at REAL NOT NULL,
 confirmation_hash TEXT, response_id TEXT, response_state TEXT NOT NULL DEFAULT 'new',
 PRIMARY KEY(guild_id,channel_id,message_id));
CREATE INDEX message_request_owner ON message_requests(guild_id,request_id);
