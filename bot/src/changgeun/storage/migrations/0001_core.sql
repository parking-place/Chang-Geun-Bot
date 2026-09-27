CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, checksum TEXT NOT NULL);
CREATE TABLE guild_settings(guild_id TEXT PRIMARY KEY, version INTEGER NOT NULL DEFAULT 0,
 settings_json TEXT NOT NULL DEFAULT '{}');
CREATE TABLE tracks(guild_id TEXT NOT NULL, id TEXT NOT NULL, source_type TEXT NOT NULL,
 external_id TEXT NOT NULL, title TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}',
 annotations_json TEXT NOT NULL DEFAULT '{}', metadata_updated_at REAL NOT NULL DEFAULT 0,
 PRIMARY KEY(guild_id,id), UNIQUE(guild_id,source_type,external_id),
 FOREIGN KEY(guild_id) REFERENCES guild_settings(guild_id));
CREATE TABLE playlists(guild_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL,
 normalized_name TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0, deleted_at REAL,
 PRIMARY KEY(guild_id,id), FOREIGN KEY(guild_id) REFERENCES guild_settings(guild_id));
CREATE UNIQUE INDEX active_playlist_name ON playlists(guild_id,normalized_name)
 WHERE deleted_at IS NULL;
CREATE TABLE playlist_entries(guild_id TEXT NOT NULL, playlist_id TEXT NOT NULL,
 id TEXT NOT NULL, track_id TEXT NOT NULL, position INTEGER NOT NULL CHECK(position>=0),
 PRIMARY KEY(guild_id,id), UNIQUE(guild_id,playlist_id,position),
 FOREIGN KEY(guild_id,playlist_id) REFERENCES playlists(guild_id,id),
 FOREIGN KEY(guild_id,track_id) REFERENCES tracks(guild_id,id));
CREATE TABLE sessions(guild_id TEXT PRIMARY KEY, version INTEGER NOT NULL DEFAULT 0,
 generation INTEGER NOT NULL DEFAULT 0, desired_state TEXT NOT NULL DEFAULT 'disconnected',
 voice_channel_id TEXT,
 current_entry_id TEXT, current_track_id TEXT, volume INTEGER NOT NULL DEFAULT 30,
 repeat_mode TEXT NOT NULL DEFAULT 'off', shuffle INTEGER NOT NULL DEFAULT 0,
 failed_tracks INTEGER NOT NULL DEFAULT 0, retry_count INTEGER NOT NULL DEFAULT 0,
 FOREIGN KEY(guild_id) REFERENCES guild_settings(guild_id),
 FOREIGN KEY(guild_id,current_track_id) REFERENCES tracks(guild_id,id));
CREATE TABLE queue_entries(guild_id TEXT NOT NULL, id TEXT NOT NULL, track_id TEXT NOT NULL,
 position INTEGER NOT NULL CHECK(position>=0), PRIMARY KEY(guild_id,id),
 UNIQUE(guild_id,position), FOREIGN KEY(guild_id) REFERENCES sessions(guild_id),
 FOREIGN KEY(guild_id,track_id) REFERENCES tracks(guild_id,id));
CREATE TABLE command_requests(guild_id TEXT NOT NULL, request_id TEXT NOT NULL,
 actor_id TEXT NOT NULL, body_hash TEXT NOT NULL, result_json TEXT NOT NULL,
 created_at REAL NOT NULL, PRIMARY KEY(guild_id,request_id));
CREATE TABLE confirmations(token_hash TEXT PRIMARY KEY, guild_id TEXT NOT NULL,
 actor_id TEXT NOT NULL, plan_hash TEXT NOT NULL, expires_at REAL NOT NULL,
 consumed INTEGER NOT NULL DEFAULT 0 CHECK(consumed IN (0,1)));
CREATE TABLE change_events(id TEXT PRIMARY KEY, guild_id TEXT NOT NULL,
 actor_id TEXT NOT NULL, request_id TEXT NOT NULL, action TEXT NOT NULL,
 before_json TEXT NOT NULL, after_json TEXT NOT NULL, created_at REAL NOT NULL,
 UNIQUE(guild_id,request_id));
CREATE TABLE proposals(guild_id TEXT NOT NULL, id TEXT NOT NULL, actor_id TEXT NOT NULL,
 playlist_id TEXT NOT NULL, track_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 created_at REAL NOT NULL, PRIMARY KEY(guild_id,id),
 FOREIGN KEY(guild_id,playlist_id) REFERENCES playlists(guild_id,id),
 FOREIGN KEY(guild_id,track_id) REFERENCES tracks(guild_id,id));
CREATE TABLE playback_history(guild_id TEXT NOT NULL, entry_id TEXT NOT NULL,
 track_id TEXT NOT NULL, played_at REAL NOT NULL,
 FOREIGN KEY(guild_id,track_id) REFERENCES tracks(guild_id,id));
CREATE TABLE external_effects(guild_id TEXT NOT NULL, request_id TEXT NOT NULL,
 generation INTEGER NOT NULL, status TEXT NOT NULL,
 PRIMARY KEY(guild_id,request_id));
