"""
Jobs runner — processo separado do FastAPI.
Rodar como: python -m jobs.runner

Loop periódico simples (MVP sem pg_cron): cada job roda uma vez por ciclo de 24h.
Erros em um job não interrompem o loop nem os outros jobs.
"""

import asyncio
import logging

LOOP_INTERVAL_SECONDS = 24 * 60 * 60


async def run_all_jobs() -> None:
    """Executa os três jobs em sequência. Erros são capturados por job."""
    from jobs.tasks.cleanup import cleanup_expired_refresh_tokens
    from jobs.tasks.recurrences import generate_recurring_sessions
    from jobs.tasks.whatsapp import renew_whatsapp_tokens

    for job_fn in [
        cleanup_expired_refresh_tokens,
        generate_recurring_sessions,
        renew_whatsapp_tokens,
    ]:
        try:
            await job_fn()
        except Exception:
            logging.exception("Job %s failed", job_fn.__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.info("Jobs runner started")
    while True:
        await run_all_jobs()
        await asyncio.sleep(LOOP_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
