"""TradingAgents SQLite loader with UPSERT support."""
import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "tradingagents.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables with proper schema and unique constraints."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS portfolio_basic_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code VARCHAR(32) UNIQUE NOT NULL,
            product_name VARCHAR(128) NOT NULL,
            latest_nav DECIMAL(10,6),
            latest_share DECIMAL(18,2),
            latest_aum DECIMAL(18,2),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS portfolio_nav (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nav_date DATE NOT NULL,
            product_code VARCHAR(32) NOT NULL,
            nav DECIMAL(10,6),
            aum DECIMAL(18,2),
            share DECIMAL(18,2),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(nav_date, product_code)
        );

        CREATE TABLE IF NOT EXISTS portfolio_position (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            position_date DATE NOT NULL,
            product_code VARCHAR(32) NOT NULL,
            asset_wind_code VARCHAR(32) NOT NULL,
            asset_name VARCHAR(128),
            holding_ratio DECIMAL(10,4),
            shares BIGINT,
            market_value DECIMAL(18,2),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(position_date, product_code, asset_wind_code)
        );
    """)
    conn.commit()


def upsert_basic_info(conn: sqlite3.Connection, records: list[dict]) -> int:
    """Insert or replace basic info records by product_code.

    Args:
        conn: SQLite connection.
        records: List of basic info dicts.

    Returns:
        Number of records upserted.
    """
    count = 0
    for rec in records:
        conn.execute("""
            INSERT OR REPLACE INTO portfolio_basic_info
                (product_code, product_name, latest_nav, latest_share, latest_aum, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            rec.get("product_code"),
            rec.get("product_name"),
            rec.get("latest_nav"),
            rec.get("latest_share"),
            rec.get("latest_aum"),
        ))
        count += 1
    conn.commit()
    return count


def upsert_nav(conn: sqlite3.Connection, records: list[dict]) -> int:
    """Insert or replace NAV records by (nav_date, product_code).

    Args:
        conn: SQLite connection.
        records: List of NAV dicts.

    Returns:
        Number of records upserted.
    """
    count = 0
    for rec in records:
        conn.execute("""
            INSERT OR REPLACE INTO portfolio_nav
                (nav_date, product_code, nav, aum, share)
            VALUES (?, ?, ?, ?, ?)
        """, (
            rec.get("nav_date"),
            rec.get("product_code"),
            rec.get("nav"),
            rec.get("aum"),
            rec.get("share"),
        ))
        count += 1
    conn.commit()
    return count


def upsert_position(conn: sqlite3.Connection, records: list[dict]) -> int:
    """Insert or replace position records by (position_date, product_code, asset_wind_code).

    Args:
        conn: SQLite connection.
        records: List of position dicts.

    Returns:
        Number of records upserted.
    """
    count = 0
    for rec in records:
        conn.execute("""
            INSERT OR REPLACE INTO portfolio_position
                (position_date, product_code, asset_wind_code, asset_name,
                 holding_ratio, shares, market_value)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            rec.get("position_date"),
            rec.get("product_code"),
            rec.get("asset_wind_code"),
            rec.get("asset_name"),
            rec.get("holding_ratio"),
            rec.get("shares"),
            rec.get("market_value"),
        ))
        count += 1
    conn.commit()
    return count


def load_all(
    basic_info: list[dict],
    nav: list[dict],
    positions: list[dict],
    db_path: str | None = None,
) -> dict[str, int]:
    """Load all record types into SQLite.

    Args:
        basic_info: Basic info records.
        nav: NAV records.
        positions: Position records.
        db_path: Optional path to database file.

    Returns:
        Dict with counts of upserted records per type.
    """
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = _connect()
    create_tables(conn)

    counts = {
        "basic_info": upsert_basic_info(conn, basic_info),
        "nav": upsert_nav(conn, nav),
        "position": upsert_position(conn, positions),
    }

    conn.close()
    return counts


if __name__ == "__main__":
    import json

    # Load mock data
    with open("examples/mock_3days_decoded.json") as f:
        decoded = json.load(f)

    # Normalize
    from transformers.image_portfolio_normalizer import normalize_all
    normalized = normalize_all(decoded)

    # Validate
    from validators.portfolio_validator import validate_all
    result = validate_all(normalized)
    print(f"Validation valid={result.valid}, errors={len(result.errors)}")

    # Load into DB
    counts = load_all(
        normalized["basic_info"],
        normalized["nav"],
        normalized["position"],
    )

    print("=== Database Load Summary ===")
    print(f"basic_info : {counts['basic_info']} upserted")
    print(f"nav        : {counts['nav']} upserted")
    print(f"position   : {counts['position']} upserted")

    # Verify
    conn = _connect()
    for table, col in [
        ("portfolio_basic_info", "product_code"),
        ("portfolio_nav", "nav_date, product_code"),
        ("portfolio_position", "position_date, product_code, asset_wind_code"),
    ]:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cur.fetchone()[0]} rows")
    conn.close()