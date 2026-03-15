-- Add last_active_at to users for 24h window tracking
ALTER TABLE users ADD COLUMN last_active_at timestamptz;

-- Remove Berlin default from users.city (multi-city from day one)
ALTER TABLE users ALTER COLUMN city DROP DEFAULT;

-- Pending notifications queue for the "one knock" strategy
CREATE TABLE pending_notifications (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid REFERENCES users(id) ON DELETE CASCADE,
    notification_type text NOT NULL,  -- 'match_interest', 'mutual_match'
    payload         jsonb NOT NULL,   -- flexible payload per notification type
    created_at      timestamptz DEFAULT now()
);

CREATE INDEX idx_pending_notifications_user ON pending_notifications(user_id, created_at);

-- Prevent duplicate matches for the same listing+seeker pair
ALTER TABLE matches ADD CONSTRAINT uq_matches_listing_seeker UNIQUE (listing_id, seeker_id);
