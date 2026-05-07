"""
Database connection pool and query helpers.
Uses psycopg2 directly (not SQLAlchemy ORM) for simplicity.
"""
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from shared.logger import get_logger
from shared.config import get_config

logger = get_logger("db")
_pool: Optional[ThreadedConnectionPool] = None


def get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        config = get_config()
        _pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=config.DATABASE_URL)
        logger.info("Database connection pool created")
    return _pool


@contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def execute(sql: str, params=None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def fetchone(sql: str, params=None) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None


def fetchall(sql: str, params=None) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


# --- Job queries ---

def insert_job(job: Dict[str, Any]) -> Optional[int]:
    """Insert a job, skip on duplicate external_id. Returns new id or None."""
    sql = """
        INSERT INTO jobs (external_id, platform, title, company, location, salary_range,
                          url, description, is_workday, workday_url)
        VALUES (%(external_id)s, %(platform)s, %(title)s, %(company)s, %(location)s,
                %(salary_range)s, %(url)s, %(description)s, %(is_workday)s, %(workday_url)s)
        ON CONFLICT (external_id) DO NOTHING
        RETURNING id
    """
    row = fetchone(sql, job)
    return row["id"] if row else None


def get_new_jobs() -> List[Dict[str, Any]]:
    return fetchall("SELECT * FROM jobs WHERE status = 'new' ORDER BY scraped_at DESC")


def get_jobs_for_queue() -> List[Dict[str, Any]]:
    return fetchall("""
        SELECT j.*, a.id as application_id, a.status as app_status
        FROM jobs j
        LEFT JOIN applications a ON a.job_id = j.id
        WHERE j.status IN ('new', 'reviewed')
        ORDER BY j.match_score DESC NULLS LAST, j.scraped_at DESC
    """)


def update_job_status(job_id: int, status: str, match_score: int = None, score_reasoning: str = None) -> None:
    if match_score is not None:
        execute("""
            UPDATE jobs SET status = %s, match_score = %s, score_reasoning = %s, reviewed_at = NOW()
            WHERE id = %s
        """, (status, match_score, score_reasoning, job_id))
    else:
        execute("UPDATE jobs SET status = %s WHERE id = %s", (status, job_id))


def get_job(job_id: int) -> Optional[Dict[str, Any]]:
    return fetchone("SELECT * FROM jobs WHERE id = %s", (job_id,))


# --- Application queries ---

def insert_application(app: Dict[str, Any]) -> int:
    sql = """
        INSERT INTO applications (job_id, tailored_resume_url, cover_letter_url,
                                  cover_letter_text, resume_diff, status)
        VALUES (%(job_id)s, %(tailored_resume_url)s, %(cover_letter_url)s,
                %(cover_letter_text)s, %(resume_diff)s, %(status)s)
        RETURNING id
    """
    row = fetchone(sql, app)
    return row["id"]


def get_application(app_id: int) -> Optional[Dict[str, Any]]:
    return fetchone("""
        SELECT a.*, j.title, j.company, j.location, j.salary_range, j.url as job_url,
               j.description, j.match_score, j.score_reasoning, j.platform
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.id = %s
    """, (app_id,))


def update_application_status(app_id: int, status: str, notes: str = None) -> None:
    if notes:
        execute("""
            UPDATE applications SET status = %s, notes = %s, updated_at = NOW() WHERE id = %s
        """, (status, notes, app_id))
    else:
        execute("UPDATE applications SET status = %s, updated_at = NOW() WHERE id = %s", (status, app_id))


def get_pending_review_applications() -> List[Dict[str, Any]]:
    return fetchall("""
        SELECT a.*, j.title, j.company, j.match_score, j.platform
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.status = 'pending_review'
        ORDER BY j.match_score DESC NULLS LAST
    """)


def get_submitted_applications() -> List[Dict[str, Any]]:
    return fetchall("""
        SELECT a.*, j.title, j.company, j.platform, j.url as job_url
        FROM applications a
        JOIN jobs j ON j.id = a.job_id
        WHERE a.status IN ('submitted', 'interview', 'rejected', 'failed')
        ORDER BY a.submitted_at DESC
    """)


# --- Workday account queries ---

def get_workday_account(domain: str) -> Optional[Dict[str, Any]]:
    return fetchone("SELECT * FROM workday_accounts WHERE employer_domain = %s", (domain,))


def save_workday_account(domain: str, email: str, password_ref: str) -> None:
    execute("""
        INSERT INTO workday_accounts (employer_domain, email, password_ref)
        VALUES (%s, %s, %s)
        ON CONFLICT (employer_domain) DO UPDATE SET email = EXCLUDED.email, password_ref = EXCLUDED.password_ref
    """, (domain, email, password_ref))
