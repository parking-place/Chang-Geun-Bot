CREATE TABLE edit_undos(guild_id TEXT NOT NULL, event_id TEXT NOT NULL,
 request_id TEXT NOT NULL, created_at REAL NOT NULL,
 PRIMARY KEY(guild_id,event_id), UNIQUE(guild_id,request_id),
 FOREIGN KEY(guild_id) REFERENCES guild_settings(guild_id),
 FOREIGN KEY(event_id) REFERENCES change_events(id));
