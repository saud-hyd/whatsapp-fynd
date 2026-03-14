-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Users
CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    wa_id           text UNIQUE NOT NULL,
    name            text,
    role            text CHECK (role IN ('lister', 'seeker', 'both')),
    city            text DEFAULT 'Berlin',
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- 2. Listings (hybrid: structured fields + embedding)
CREATE TABLE listings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid REFERENCES users(id),
    raw_text        text NOT NULL,
    city            text NOT NULL,
    neighborhood    text,
    rent_amount     integer,
    rooms           numeric(3,1),
    available_from  date,
    available_to    date,
    listing_type    text CHECK (listing_type IN ('sublet', 'rent', 'wg_room')),
    amenities       text[],
    summary         text,
    embedding       vector(768),
    is_active       boolean DEFAULT true,
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- 3. Matches (double opt-in connections)
CREATE TABLE matches (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id      uuid REFERENCES listings(id),
    seeker_id       uuid REFERENCES users(id),
    lister_id       uuid REFERENCES users(id),
    similarity      float,
    seeker_status   text DEFAULT 'pending' CHECK (seeker_status IN ('pending', 'accepted', 'rejected')),
    lister_status   text DEFAULT 'pending' CHECK (lister_status IN ('pending', 'accepted', 'rejected')),
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX idx_listings_embedding ON listings USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_listings_city ON listings(city) WHERE is_active = true;
CREATE INDEX idx_listings_rent ON listings(rent_amount) WHERE is_active = true;
CREATE INDEX idx_listings_active ON listings(is_active, city);
CREATE INDEX idx_users_wa_id ON users(wa_id);
CREATE INDEX idx_matches_seeker ON matches(seeker_id, created_at DESC);
CREATE INDEX idx_matches_lister ON matches(lister_id, created_at DESC);

-- Auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_users
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_updated_at_listings
    BEFORE UPDATE ON listings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER set_updated_at_matches
    BEFORE UPDATE ON matches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
