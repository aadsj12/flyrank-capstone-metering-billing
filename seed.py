from database import get_connection


def seed_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            api_call_limit INTEGER NOT NULL,
            ai_token_limit INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL UNIQUE,
            plan_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            stripe_customer_id TEXT,
            stripe_subscription_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (plan_id) REFERENCES plans(id)
        );

        CREATE TABLE IF NOT EXISTS usage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id INTEGER NOT NULL,
            usage_type TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            idempotency_key TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            UNIQUE (tenant_id, idempotency_key)
        );

        CREATE TABLE IF NOT EXISTS stripe_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stripe_event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("DELETE FROM stripe_events")
    cursor.execute("DELETE FROM usage_events")
    cursor.execute("DELETE FROM subscriptions")
    cursor.execute("DELETE FROM tenants")
    cursor.execute("DELETE FROM plans")

    cursor.execute("""
        INSERT INTO plans (name, api_call_limit, ai_token_limit)
        VALUES ('Free', 1000, 100000)
    """)

    cursor.execute("""
        INSERT INTO plans (name, api_call_limit, ai_token_limit)
        VALUES ('Pro', 10000, 1000000)
    """)

    cursor.execute("""
        INSERT INTO tenants (name)
        VALUES ('Demo Tenant')
    """)

    tenant_id = cursor.lastrowid

    free_plan_id = cursor.execute(
        "SELECT id FROM plans WHERE name = 'Free'"
    ).fetchone()["id"]

    cursor.execute("""
        INSERT INTO subscriptions (tenant_id, plan_id, status)
        VALUES (?, ?, 'active')
    """, (tenant_id, free_plan_id))

    connection.commit()
    connection.close()

    print(f"Seed complete: demo tenant {tenant_id} on Free plan")


if __name__ == "__main__":
    seed_database()