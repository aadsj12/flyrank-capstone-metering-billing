import logging
import time

from database import get_connection


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


def reconcile_usage():
    connection = get_connection()

    try:
        tenants = connection.execute(
            """
            SELECT id, name
            FROM tenants
            ORDER BY id
            """
        ).fetchall()

        results = []

        for tenant in tenants:
            totals = connection.execute(
                """
                SELECT
                    usage_type,
                    COUNT(*) AS event_count,
                    COALESCE(SUM(quantity), 0) AS quantity,
                    COALESCE(SUM(cost_microdollars), 0)
                        AS cost_microdollars
                FROM usage_events
                WHERE tenant_id = ?
                  AND strftime('%Y-%m', created_at)
                      = strftime('%Y-%m', 'now')
                GROUP BY usage_type
                """,
                (tenant["id"],),
            ).fetchall()

            tenant_result = {
                "tenant_id": tenant["id"],
                "tenant_name": tenant["name"],
                "usage": [dict(row) for row in totals],
            }

            results.append(tenant_result)

        return results

    finally:
        connection.close()


def run_reconciliation_job():
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            results = reconcile_usage()

            logger.info(
                "Usage reconciliation completed for %s tenant(s)",
                len(results),
            )

            for result in results:
                logger.info("%s", result)

            return results

        except Exception:
            logger.exception(
                "Usage reconciliation attempt %s/%s failed",
                attempt,
                MAX_RETRIES,
            )

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SECONDS)

    logger.critical(
        "ALERT: usage reconciliation failed after %s attempts",
        MAX_RETRIES,
    )

    raise RuntimeError(
        "Usage reconciliation failed after maximum retries"
    )


if __name__ == "__main__":
    run_reconciliation_job()