CREATE TABLE audio_admissions(
 guild_id TEXT NOT NULL,entry_id TEXT NOT NULL,actor_id TEXT NOT NULL,
 text_channel_id TEXT NOT NULL,request_id TEXT NOT NULL,created_at REAL NOT NULL,
 PRIMARY KEY(guild_id,entry_id));
