"""
Deduplicator — tracks seen job external_ids to avoid re-inserting duplicates.
Uses the DB's ON CONFLICT DO NOTHING as primary guard, but this module
provides an in-memory cache for within-run deduplication.
"""
from typing import Set
from shared.db import fetchall
from shared.logger import get_logger

logger = get_logger("deduplicator")


class Deduplicator:
    def __init__(self):
        self._seen: Set[str] = set()
        self._load_from_db()

    def _load_from_db(self) -> None:
        """Pre-load all known external_ids from the DB."""
        try:
            rows = fetchall("SELECT external_id FROM jobs")
            self._seen = {row["external_id"] for row in rows}
            logger.info("Deduplicator loaded", extra={"known_ids": len(self._seen)})
        except Exception as e:
            logger.warning("Could not pre-load external_ids", extra={"error": str(e)})
            self._seen = set()

    def is_seen(self, external_id: str) -> bool:
        return external_id in self._seen

    def mark_seen(self, external_id: str) -> None:
        self._seen.add(external_id)

    def filter_new(self, jobs: list) -> list:
        """Return only jobs whose external_id hasn't been seen."""
        new_jobs = []
        for job in jobs:
            eid = job.get("external_id", "")
            if eid and not self.is_seen(eid):
                new_jobs.append(job)
                self.mark_seen(eid)
        return new_jobs
