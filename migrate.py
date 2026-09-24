from pathlib import Path

from database import get_connection


MIGRATIONS_DIR = Path("migrations")


def run_migrations():
    connection = get_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        applied = {
            row["filename"]
            for row in connection.execute(
                "SELECT filename FROM schema_migrations"
            ).fetchall()
        }

        for migration_path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if migration_path.name in applied:
                continue

            sql = migration_path.read_text()

            connection.executescript(sql)

            connection.execute(
                """
                INSERT INTO schema_migrations (filename)
                VALUES (?)
                """,
                (migration_path.name,),
            )

            connection.commit()
            print(f"Applied {migration_path.name}")

    finally:
        connection.close()


if __name__ == "__main__":
    run_migrations()