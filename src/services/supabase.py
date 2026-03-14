import asyncpg


async def get_user_by_wa_id(conn: asyncpg.Connection, wa_id: str) -> dict | None:
    """Look up a user by WhatsApp ID."""
    row = await conn.fetchrow(
        "SELECT id, wa_id, name, role, city FROM users WHERE wa_id = $1",
        wa_id,
    )
    return dict(row) if row else None


async def create_user(conn: asyncpg.Connection, wa_id: str, name: str | None = None) -> dict:
    """Create a new user and return their record."""
    row = await conn.fetchrow(
        """INSERT INTO users (wa_id, name)
           VALUES ($1, $2)
           RETURNING id, wa_id, name, role, city""",
        wa_id,
        name,
    )
    return dict(row)


async def update_user_role(conn: asyncpg.Connection, user_id: str, role: str) -> None:
    """Update a user's role."""
    await conn.execute(
        "UPDATE users SET role = $1 WHERE id = $2",
        role,
        user_id,
    )


async def insert_listing(conn: asyncpg.Connection, listing_data: dict) -> dict:
    """Insert a new listing and return its record."""
    row = await conn.fetchrow(
        """INSERT INTO listings (
               user_id, raw_text, city, neighborhood, rent_amount, rooms,
               available_from, available_to, listing_type, amenities, summary, embedding
           ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
           RETURNING id""",
        listing_data["user_id"],
        listing_data["raw_text"],
        listing_data["city"],
        listing_data.get("neighborhood"),
        listing_data.get("rent_amount"),
        listing_data.get("rooms"),
        listing_data.get("available_from"),
        listing_data.get("available_to"),
        listing_data.get("listing_type"),
        listing_data.get("amenities"),
        listing_data.get("summary"),
        listing_data.get("embedding"),
    )
    return dict(row)


async def find_matches(
    conn: asyncpg.Connection,
    embedding: list[float],
    city: str,
    max_rent: int | None = None,
    min_rooms: float | None = None,
    limit: int = 3,
) -> list[dict]:
    """Find matching listings using hard filters + semantic ranking."""
    rows = await conn.fetch(
        """SELECT l.*, u.wa_id, u.name as lister_name,
                  1 - (l.embedding <=> $1::vector) AS similarity
           FROM listings l
           JOIN users u ON l.user_id = u.id
           WHERE l.is_active = true
             AND l.city = $2
             AND ($3::int IS NULL OR l.rent_amount <= $3)
             AND ($4::numeric IS NULL OR l.rooms >= $4)
           ORDER BY l.embedding <=> $1::vector
           LIMIT $5""",
        str(embedding),
        city,
        max_rent,
        min_rooms,
        limit,
    )
    return [dict(r) for r in rows]
