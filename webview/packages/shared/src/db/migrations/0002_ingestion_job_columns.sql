-- Add columns for tracking latest ingestion job per public project
ALTER TABLE "public_projects"
ADD COLUMN IF NOT EXISTS "latest_job_id" text,
ADD COLUMN IF NOT EXISTS "latest_job_status" text;

