create schema tg_bot;

CREATE table IF NOT EXISTS tg_bot.chat_schedule (
	id serial primary key , 
    time TIME WITH TIME ZONE,  
    days VARCHAR(20),                
    user_id BIGINT,            
    chat_id BIGINT             
);

CREATE TABLE tg_bot.status (
	id serial4 NOT NULL,
	user_id bigint NULL,
	username text NULL,
	status text NULL,
	"date" date NULL,
	tech_load_ts timestamp NULL DEFAULT now(),
	is_daily int4 NULL,
	CONSTRAINT status_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS tg_bot.users (        
    user_id bigint primary key,
    username TEXT,
    real_name text,
    is_user integer,
    in_team int
);

CREATE TABLE IF NOT exists tg_bot.teams (
    team_id serial PRIMARY KEY,
    team_name text NOT NULL
);

CREATE table IF NOT EXISTS tg_bot.role_team (                
    user_id BIGINT,            
    team_id int,
    team_role int
);