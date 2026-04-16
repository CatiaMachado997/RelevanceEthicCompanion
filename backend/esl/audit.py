"""
ESL Audit & Logging System

Every ESL decision MUST be logged for:
1. Transparency to users
2. Ethical research
3. System improvement
4. Accountability
"""

from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta, UTC
import json
import logging

from .models import ProposedAction, ESLDecision, ESLAuditLog

logger = logging.getLogger(__name__)


class ESLAuditLogger:
    """
    Audit logger for all ESL decisions

    Supports both in-memory storage (for development/testing) and
    PostgreSQL persistence (for production).

    Usage:
        # In-memory (default):
        audit_logger = ESLAuditLogger()

        # With database persistence:
        from utils.db import get_db_connection
        audit_logger = ESLAuditLogger(db_connection_factory=get_db_connection)
    """

    def __init__(self, db_connection_factory: Optional[Callable] = None):
        """
        Initialize audit logger.

        Args:
            db_connection_factory: Optional callable that returns a context manager
                                   for database connections. If None, uses in-memory storage.
        """
        self._db_connection_factory = db_connection_factory
        self._in_memory_logs: List[ESLAuditLog] = []

        if db_connection_factory:
            logger.info("ESLAuditLogger initialized with database persistence")
        else:
            logger.info("ESLAuditLogger initialized with in-memory storage")

    @property
    def _use_database(self) -> bool:
        """Check if database persistence is enabled."""
        return self._db_connection_factory is not None

    async def log_decision(
        self,
        user_id: str,
        proposed_action: ProposedAction,
        decision: ESLDecision,
        context_snapshot: Dict[str, Any],
    ) -> None:
        """
        Log an ESL decision.

        Args:
            user_id: User ID
            proposed_action: The action that was proposed
            decision: The ESL's decision
            context_snapshot: Snapshot of user context at decision time
        """
        audit_log = ESLAuditLog(
            user_id=str(user_id),
            proposed_action=proposed_action,
            decision=decision,
            context_snapshot=context_snapshot,
            timestamp=datetime.now(UTC),
        )

        if self._use_database:
            await self._log_to_database(audit_log)
        else:
            self._in_memory_logs.append(audit_log)

    async def _log_to_database(self, audit_log: ESLAuditLog) -> None:
        """Persist audit log to PostgreSQL."""
        try:
            with self._db_connection_factory() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO esl_audit_log (
                            user_id, timestamp, proposed_action,
                            decision_status, decision_reason,
                            violated_values, applied_rules,
                            confidence, context_snapshot
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            audit_log.user_id,
                            audit_log.timestamp,
                            json.dumps(
                                audit_log.proposed_action.model_dump(), default=str
                            ),
                            audit_log.decision.status.value,
                            audit_log.decision.reason,
                            audit_log.decision.violated_values,
                            audit_log.decision.applied_rules,
                            audit_log.decision.confidence,
                            json.dumps(audit_log.context_snapshot, default=str),
                        ),
                    )
            logger.debug(
                "Audit log persisted to database for user %s", audit_log.user_id
            )
        except Exception as e:
            logger.error("Failed to persist audit log to database: %s", e)
            # Fallback to in-memory storage
            self._in_memory_logs.append(audit_log)

    async def get_user_logs(
        self, user_id: str, days: int = 7, status_filter: Optional[str] = None
    ) -> List[ESLAuditLog]:
        """
        Retrieve audit logs for a user.

        Args:
            user_id: User ID
            days: Number of days to retrieve (for filtering)
            status_filter: Optional filter by decision status

        Returns:
            List of ESLAuditLog entries
        """
        if self._use_database:
            return await self._get_logs_from_database(user_id, days, status_filter)

        # In-memory retrieval
        cutoff_time = datetime.now(UTC) - timedelta(days=days)
        logs = [
            log
            for log in self._in_memory_logs
            if log.user_id == user_id and log.timestamp >= cutoff_time
        ]

        if status_filter:
            logs = [log for log in logs if log.decision.status.value == status_filter]

        return logs

    async def _get_logs_from_database(
        self, user_id: str, days: int, status_filter: Optional[str]
    ) -> List[ESLAuditLog]:
        """Retrieve audit logs from PostgreSQL."""
        try:
            with self._db_connection_factory() as conn:
                with conn.cursor() as cur:
                    query = """
                        SELECT
                            id, user_id, timestamp, proposed_action,
                            decision_status, decision_reason,
                            violated_values, applied_rules,
                            confidence, context_snapshot
                        FROM esl_audit_log
                        WHERE user_id = %s
                          AND timestamp >= NOW() - (INTERVAL '1 day' * %s)
                    """
                    params = [user_id, days]

                    if status_filter:
                        query += " AND decision_status = %s"
                        params.append(status_filter)

                    query += " ORDER BY timestamp DESC"

                    cur.execute(query, params)
                    rows = cur.fetchall()

                    logs = []
                    for row in rows:
                        # rows are dicts due to dict_row cursor factory
                        proposed_action_data = (
                            row["proposed_action"]
                            if isinstance(row["proposed_action"], dict)
                            else json.loads(row["proposed_action"])
                        )
                        context_snapshot = (
                            row["context_snapshot"]
                            if isinstance(row["context_snapshot"], dict)
                            else json.loads(row["context_snapshot"])
                        )

                        proposed_action = ProposedAction(**proposed_action_data)
                        decision = ESLDecision(
                            status=row["decision_status"],
                            reason=row["decision_reason"],
                            violated_values=row["violated_values"] or [],
                            applied_rules=row["applied_rules"] or [],
                            confidence=row["confidence"],
                            timestamp=row["timestamp"],
                        )

                        logs.append(
                            ESLAuditLog(
                                id=str(row["id"]),
                                user_id=str(row["user_id"]),
                                timestamp=row["timestamp"],
                                proposed_action=proposed_action,
                                decision=decision,
                                context_snapshot=context_snapshot,
                            )
                        )

                    return logs
        except Exception as e:
            logger.error("Failed to retrieve audit logs from database: %s", e)
            # Fallback to in-memory logs
            return await self._get_in_memory_logs(user_id, days, status_filter)

    async def _get_in_memory_logs(
        self, user_id: str, days: int, status_filter: Optional[str]
    ) -> List[ESLAuditLog]:
        """Fallback in-memory retrieval."""
        cutoff_time = datetime.now(UTC) - timedelta(days=days)
        logs = [
            log
            for log in self._in_memory_logs
            if log.user_id == user_id and log.timestamp >= cutoff_time
        ]

        if status_filter:
            logs = [log for log in logs if log.decision.status.value == status_filter]

        return logs

    async def get_statistics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get statistical summary of ESL decisions for a user.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dictionary with statistics
        """
        logs = await self.get_user_logs(user_id, days=days)

        if not logs:
            return {
                "total_decisions": 0,
                "approval_rate": 0.0,
                "veto_rate": 0.0,
                "modification_rate": 0.0,
                "most_common_violations": [],
                "most_active_rules": [],
            }

        total = len(logs)
        approved = sum(1 for log in logs if log.decision.status.value == "APPROVED")
        vetoed = sum(1 for log in logs if log.decision.status.value == "VETOED")
        modified = sum(1 for log in logs if log.decision.status.value == "MODIFIED")

        # Count violated values
        violation_counts: Dict[str, int] = {}
        for log in logs:
            for value_id in log.decision.violated_values:
                violation_counts[value_id] = violation_counts.get(value_id, 0) + 1

        # Count applied rules
        rule_counts: Dict[str, int] = {}
        for log in logs:
            for rule in log.decision.applied_rules:
                rule_counts[rule] = rule_counts.get(rule, 0) + 1

        return {
            "total_decisions": total,
            "approval_rate": approved / total,
            "veto_rate": vetoed / total,
            "modification_rate": modified / total,
            "most_common_violations": sorted(
                violation_counts.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "most_active_rules": sorted(
                rule_counts.items(), key=lambda x: x[1], reverse=True
            )[:5],
            "period_days": days,
        }
