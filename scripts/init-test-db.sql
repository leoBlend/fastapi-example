-- Runs automatically the first time the Postgres container initializes its data
-- volume. Creates the separate database the pytest suite uses, so tests never
-- touch your real `todoapp` data.
CREATE DATABASE todoapp_test;
