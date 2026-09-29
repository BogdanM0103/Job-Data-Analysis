import sqlite3
import pandas as pd
from typing import Any
DB_PATH = "jobs.db"

# Daily run plan:
#   1. get_known_urls()      - URLs already in the DB            (done)
#   2. insert_jobs()         - save newly scraped jobs            (done)
#   3. record_sightings()    - save which URLs were live today    (todo)
#   4. update_status()       - last_seen / is_active + snapshot   (todo)
#   5. hook everything into webscraping.py main()                 (todo)


def init_db() -> None:
    """Create the tables if they don't exist yet."""
    conn = sqlite3.connect(DB_PATH)

    # one row per job ever seen; first_seen/last_seen track how long it stayed up
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            url TEXT PRIMARY KEY NOT NULL,
            title TEXT,
            company TEXT,
            city TEXT,
            salary_min REAL,
            salary_max REAL,
            currency TEXT,
            date_posted TEXT,
            employment_type TEXT,
            experience_months INTEGER,
            education TEXT,
            industry TEXT,
            occupations TEXT,
            valid_through TEXT,
            description TEXT,
            first_seen TEXT,
            last_seen TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)

    # one row per day with that day's totals
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            date TEXT PRIMARY KEY NOT NULL,
            active_jobs INTEGER,
            new_jobs INTEGER,
            closed_jobs INTEGER
        )
    """)

    # one row per job per day it was in the sitemap -> "which jobs were live on day X?"
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_sightings (
            url TEXT NOT NULL,
            date TEXT NOT NULL,
            PRIMARY KEY (url, date)
        )
    """)

    conn.commit()
    conn.close()

def get_known_urls() -> set[str]:
    """Return every job URL already stored in the jobs table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT url FROM jobs")
    rows = cursor.fetchall()
    conn.close()
    return {row[0] for row in rows}

def insert_jobs(rows: list[dict[str, Any]], today: str) -> None:
    """Save newly scraped jobs (dicts from parse_job). Existing URLs are skipped."""
    for row in rows:
        row["first_seen"] = today
        row["last_seen"] = today
    conn = sqlite3.connect(DB_PATH)
    sql = """
        INSERT OR IGNORE INTO jobs (
            url, title, company, city, salary_min, salary_max, currency,
            date_posted, employment_type, experience_months, education,
            industry, occupations, valid_through, description,
            first_seen, last_seen

        ) VALUES (
            :url, :title, :company, :city, :salary_min, :salary_max, :currency,
            :date_posted, :employment_type, :experience_months, :education,
            :industry, :occupations, :valid_through, :description,
            :first_seen, :last_seen
        )
    """
    # Runs the insert once for each dict in rows
    conn.executemany(sql, rows)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    rows = pd.read_csv("jobs.csv").to_dict("records")
    insert_jobs(rows, "2026-09-30")
    print(len(get_known_urls()))
