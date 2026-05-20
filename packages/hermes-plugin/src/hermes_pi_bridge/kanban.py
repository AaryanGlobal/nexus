"""
Hermes Kanban integration for task tracking.

This module provides functions to interact with Hermes' existing
Kanban database for tracking delegated tasks.
"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default Kanban column for delegated tasks
DEFAULT_COLUMN = "in_progress"


def create_task(
    db_path: Path,
    title: str,
    description: str,
    max_runtime_seconds: int = 300,
    metadata: dict | None = None,
) -> str:
    """
    Create a new task in Hermes Kanban.

    Args:
        db_path: Path to kanban.db
        title: Task title
        description: Task description (can include JSON metadata)
        max_runtime_seconds: Expected max runtime
        metadata: Additional metadata

    Returns:
        Task ID (kanban ID)
    """
    task_id = str(uuid.uuid4())
    now = datetime.now()

    # Serialize metadata
    body = description
    if metadata:
        body = json.dumps({
            "description": description,
            "metadata": metadata,
        })

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check if tasks table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='tasks'
        """)

        if cursor.fetchone():
            cursor.execute("""
                INSERT INTO tasks (
                    id, title, body, column_id, created_at,
                    updated_at, last_heartbeat_at, max_runtime_seconds,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task_id,
                title,
                body,
                DEFAULT_COLUMN,
                now.isoformat(),
                now.isoformat(),
                now.isoformat(),
                max_runtime_seconds,
                json.dumps(metadata) if metadata else None,
            ))
        else:
            # Kanban table doesn't exist, use simple approach
            logger.warning("Kanban tasks table not found, using in-memory tracking")

        conn.commit()
        conn.close()

        logger.info(f"Created Kanban task: {task_id}")
        return task_id

    except Exception as e:
        logger.error(f"Failed to create Kanban task: {e}")
        # Return a task ID anyway for tracking
        return task_id


def update_task_status(
    db_path: Path,
    task_id: str,
    status: str,
    notes: str | None = None,
) -> bool:
    """
    Update task status in Kanban.

    Args:
        db_path: Path to kanban.db
        task_id: Task ID
        status: New status
        notes: Optional notes

    Returns:
        True if successful
    """
    now = datetime.now().isoformat()

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE tasks
            SET status = ?, updated_at = ?, notes = ?
            WHERE id = ?
        """, (status, now, notes, task_id))

        conn.commit()
        success = cursor.rowcount > 0
        conn.close()

        return success

    except Exception as e:
        logger.error(f"Failed to update Kanban task: {e}")
        return False


def get_task_result(
    db_path: Path,
    task_id: str,
) -> dict[str, Any] | None:
    """
    Get task result from Kanban.

    Args:
        db_path: Path to kanban.db
        task_id: Task ID

    Returns:
        Task data or None if not found
    """
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM tasks WHERE id = ?
        """, (task_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    except Exception as e:
        logger.error(f"Failed to get Kanban task: {e}")
        return None


def record_task_failure(
    db_path: Path,
    task_id: str,
    error: str,
    failure_limit: int = 3,
) -> bool:
    """
    Record a task failure with circuit breaker.

    Args:
        db_path: Path to kanban.db
        task_id: Task ID
        error: Error message
        failure_limit: Max failures before blocking

    Returns:
        True if task should be retried, False if blocked
    """
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get current failure count
        cursor.execute("""
            SELECT consecutive_failures FROM tasks WHERE id = ?
        """, (task_id,))

        row = cursor.fetchone()
        if not row:
            conn.close()
            return True

        failures = (row[0] or 0) + 1

        # Update failure count and status
        blocked = failures >= failure_limit
        status = "blocked" if blocked else "failed"

        cursor.execute("""
            UPDATE tasks
            SET consecutive_failures = ?, status = ?, error = ?
            WHERE id = ?
        """, (failures, status, error, task_id))

        conn.commit()
        conn.close()

        return not blocked

    except Exception as e:
        logger.error(f"Failed to record task failure: {e}")
        return True  # Allow retry on error
