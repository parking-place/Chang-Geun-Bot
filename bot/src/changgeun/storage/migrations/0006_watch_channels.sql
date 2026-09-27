CREATE TABLE watch_settings(
 guild_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
 revision INTEGER NOT NULL DEFAULT 0, enable_generation INTEGER NOT NULL DEFAULT 1,
 seed_applied INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL);
CREATE TABLE watch_channels(
 guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, registered INTEGER NOT NULL,
 channel_generation INTEGER NOT NULL DEFAULT 1, healthy INTEGER NOT NULL DEFAULT 1,
 updated_at REAL NOT NULL, PRIMARY KEY(guild_id,channel_id));
CREATE TABLE request_sources(
 guild_id TEXT NOT NULL, request_id TEXT NOT NULL, actor_id TEXT NOT NULL,
 channel_id TEXT NOT NULL, origin TEXT NOT NULL, enable_generation INTEGER,
 channel_generation INTEGER, revision INTEGER, revoked INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(guild_id,request_id));
CREATE TABLE watch_change_requests(
 guild_id TEXT NOT NULL, interaction_id TEXT NOT NULL, actor_id TEXT NOT NULL,
 body_hash TEXT NOT NULL, result_json TEXT NOT NULL, created_at REAL NOT NULL,
 PRIMARY KEY(guild_id,interaction_id));
CREATE TABLE watch_change_events(
 id TEXT PRIMARY KEY, guild_id TEXT NOT NULL, actor_id TEXT NOT NULL,
 action TEXT NOT NULL, channel_id TEXT, previous_revision INTEGER NOT NULL,
 revision INTEGER NOT NULL, requests_cancelled INTEGER NOT NULL,
 admissions_revoked INTEGER NOT NULL, created_at REAL NOT NULL);
ALTER TABLE audio_admissions ADD COLUMN origin TEXT NOT NULL DEFAULT 'legacy_unknown';
ALTER TABLE audio_admissions ADD COLUMN enable_generation INTEGER;
ALTER TABLE audio_admissions ADD COLUMN channel_generation INTEGER;
ALTER TABLE audio_admissions ADD COLUMN revoked INTEGER NOT NULL DEFAULT 1;
ALTER TABLE audio_admissions ADD COLUMN started INTEGER NOT NULL DEFAULT 0;
CREATE INDEX watch_registered ON watch_channels(guild_id,registered);
CREATE INDEX source_channel ON request_sources(guild_id,channel_id,origin,revoked);
CREATE INDEX admission_channel ON audio_admissions(guild_id,text_channel_id,origin,revoked);
