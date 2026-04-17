-- Migration: Add is_published column to schedule table
-- This enables Draft Mode for schedule changes

ALTER TABLE schedule
ADD COLUMN IF NOT EXISTS is_published BOOLEAN NOT NULL DEFAULT FALSE;

-- Create index for faster filtering
CREATE INDEX IF NOT EXISTS idx_schedule_is_published ON schedule(is_published);

-- Set existing schedule changes to published (for backwards compatibility)
-- UPDATE schedule SET is_published = TRUE WHERE is_change = TRUE;
