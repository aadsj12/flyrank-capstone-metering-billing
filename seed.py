from database import get_connection
from migrate import run_migrations


def seed_database():
    run_migrations()

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("DELETE FROM stripe_events")
    cursor.execute("DELETE FROM usage_events")
    cursor.execute("DELETE FROM subscriptions")
    cursor.execute("DELETE FROM tenants")
    cursor.execute("DELETE FROM plans")

    cursor.execute("""
        INSERT INTO plans (
            name,
            api_call_limit,
            ai_token_limit
        )
        VALUES ('Free', 1000, 100000)
    """)

    cursor.execute("""
        INSERT INTO plans (
            name,
            api_call_limit,
            ai_token_limit
        )
        VALUES ('Pro', 10000, 1000000)
    """)

    cursor.execute("""
        INSERT INTO tenants (name)
        VALUES ('Demo Tenant')
    """)

    tenant_id = cursor.lastrowid

    free_plan_id = cursor.execute(
        """
        SELECT id
        FROM plans
        WHERE name = 'Free'
        """
    ).fetchone()["id"]

    cursor.execute(
        """
        INSERT INTO subscriptions (
            tenant_id,
            plan_id,
            status
        )
        VALUES (?, ?, 'active')
        """,
        (tenant_id, free_plan_id),
    )

    connection.commit()
    connection.close()

    print(
        f"Seed complete: demo tenant {tenant_id} "
        "on Free plan"
    )


if __name__ == "__main__":
    seed_database()