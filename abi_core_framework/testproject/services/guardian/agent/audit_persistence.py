"""
Audit Persistence System for Guardial Agent

This module implements audit report persistence with cryptographic integrity
and traceability for compliance requirements.
"""

import json
import logging
import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from agent.models.agent_models import GuardialEvaluationResponse, AuditReport

logger = logging.getLogger(__name__)

class AuditPersistenceManager:
    """Manages audit report persistence with integrity validation"""
    
    def __init__(self, db_path: str = "./audit_reports.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize audit database schema"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_reports (
                        report_id TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        context_id TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        deviation_score REAL NOT NULL,
                        report_data TEXT NOT NULL,
                        report_hash TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        policy_version TEXT,
                        evaluator_version TEXT
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_integrity (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        report_id TEXT NOT NULL,
                        hash_chain TEXT NOT NULL,
                        signature TEXT,
                        created_at TIMESTAMP NOT NULL,
                        FOREIGN KEY (report_id) REFERENCES audit_reports (report_id)
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_task_id ON audit_reports (task_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_context_id ON audit_reports (context_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_created_at ON audit_reports (created_at)
                """)
                
                logger.info(f"Audit database initialized: {self.db_path}")
                
        except Exception as e:
            logger.error(f"Failed to initialize audit database: {e}")
            raise
    
    async def persist_report(self, response: GuardialEvaluationResponse, task_context: Dict[str, Any]) -> bool:
        """
        Persist audit report with cryptographic integrity
        
        Args:
            response: GuardialEvaluationResponse to persist
            task_context: Additional task context (task_id, context_id, user_id)
            
        Returns:
            True if successfully persisted, False otherwise
        """
        try:
            # Serialize report data
            report_data = self._serialize_report(response)
            
            # Calculate report hash
            report_hash = self._calculate_report_hash(report_data)
            
            # Generate hash chain for integrity
            hash_chain = await self._generate_hash_chain(response.report_id, report_hash)
            
            # Store in database
            with sqlite3.connect(self.db_path) as conn:
                # Insert main report
                conn.execute("""
                    INSERT INTO audit_reports (
                        report_id, task_id, context_id, user_id, decision,
                        deviation_score, report_data, report_hash, created_at,
                        policy_version, evaluator_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    response.report_id,
                    task_context.get("task_id", "unknown"),
                    task_context.get("context_id", "unknown"),
                    task_context.get("user_id", "unknown"),
                    response.decision,
                    response.deviation_score,
                    report_data,
                    report_hash,
                    response.evaluated_at,
                    response.policy_version,
                    response.evaluator_version
                ))
                
                # Insert integrity record
                conn.execute("""
                    INSERT INTO audit_integrity (
                        report_id, hash_chain, created_at
                    ) VALUES (?, ?, ?)
                """, (
                    response.report_id,
                    hash_chain,
                    datetime.utcnow()
                ))
                
                conn.commit()
            
            logger.info(f"✅ Audit report persisted: {response.report_id}")
            return True
            
        except Exception as e:
            logger.error(f"🚨 Failed to persist audit report: {e}")
            return False
    
    async def retrieve_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve audit report by ID with integrity validation
        
        Args:
            report_id: Report ID to retrieve
            
        Returns:
            Report data if found and valid, None otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                cursor = conn.execute("""
                    SELECT * FROM audit_reports WHERE report_id = ?
                """, (report_id,))
                
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Report not found: {report_id}")
                    return None
                
                # Validate integrity
                if not await self._validate_report_integrity(dict(row)):
                    logger.error(f"🚨 Report integrity validation failed: {report_id}")
                    return None
                
                # Deserialize report data
                report_data = json.loads(row["report_data"])
                
                return {
                    "report_id": row["report_id"],
                    "task_id": row["task_id"],
                    "context_id": row["context_id"],
                    "user_id": row["user_id"],
                    "decision": row["decision"],
                    "deviation_score": row["deviation_score"],
                    "report_data": report_data,
                    "created_at": row["created_at"],
                    "policy_version": row["policy_version"],
                    "evaluator_version": row["evaluator_version"]
                }
                
        except Exception as e:
            logger.error(f"Failed to retrieve audit report: {e}")
            return None
    
    async def query_reports(
        self,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        user_id: Optional[str] = None,
        decision: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query audit reports with filters
        
        Returns:
            List of matching reports
        """
        try:
            query = "SELECT * FROM audit_reports WHERE 1=1"
            params = []
            
            if task_id:
                query += " AND task_id = ?"
                params.append(task_id)
            
            if context_id:
                query += " AND context_id = ?"
                params.append(context_id)
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            if decision:
                query += " AND decision = ?"
                params.append(decision)
            
            if start_date:
                query += " AND created_at >= ?"
                params.append(start_date)
            
            if end_date:
                query += " AND created_at <= ?"
                params.append(end_date)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params)
                
                reports = []
                for row in cursor.fetchall():
                    reports.append({
                        "report_id": row["report_id"],
                        "task_id": row["task_id"],
                        "context_id": row["context_id"],
                        "user_id": row["user_id"],
                        "decision": row["decision"],
                        "deviation_score": row["deviation_score"],
                        "created_at": row["created_at"],
                        "policy_version": row["policy_version"],
                        "evaluator_version": row["evaluator_version"]
                    })
                
                return reports
                
        except Exception as e:
            logger.error(f"Failed to query audit reports: {e}")
            return []
    
    def _serialize_report(self, response: GuardialEvaluationResponse) -> str:
        """Serialize report to JSON string"""
        return json.dumps({
            "report_id": response.report_id,
            "decision": response.decision,
            "deviation_score": response.deviation_score,
            "audit_report": response.audit_report.dict(),
            "compliance_trace": response.compliance_trace.dict(),
            "uncertain": response.uncertain,
            "processing_time_ms": response.processing_time_ms,
            "evaluated_at": response.evaluated_at.isoformat(),
            "evaluator_version": response.evaluator_version,
            "policy_version": response.policy_version
        }, sort_keys=True)
    
    def _calculate_report_hash(self, report_data: str) -> str:
        """Calculate SHA-256 hash of report data"""
        return hashlib.sha256(report_data.encode('utf-8')).hexdigest()
    
    async def _generate_hash_chain(self, report_id: str, report_hash: str) -> str:
        """Generate hash chain for integrity validation"""
        try:
            # Get previous hash from chain
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT hash_chain FROM audit_integrity 
                    ORDER BY created_at DESC LIMIT 1
                """)
                row = cursor.fetchone()
                previous_hash = row[0] if row else "genesis"
            
            # Create chain hash
            chain_input = f"{previous_hash}:{report_id}:{report_hash}"
            chain_hash = hashlib.sha256(chain_input.encode('utf-8')).hexdigest()
            
            return chain_hash
            
        except Exception as e:
            logger.error(f"Failed to generate hash chain: {e}")
            return hashlib.sha256(f"{report_id}:{report_hash}".encode('utf-8')).hexdigest()
    
    async def _validate_report_integrity(self, report_row: Dict[str, Any]) -> bool:
        """Validate report integrity using stored hash"""
        try:
            # Recalculate hash
            calculated_hash = self._calculate_report_hash(report_row["report_data"])
            stored_hash = report_row["report_hash"]
            
            if calculated_hash != stored_hash:
                logger.error(f"Hash mismatch for report {report_row['report_id']}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Integrity validation failed: {e}")
            return False
    
    async def get_audit_statistics(self) -> Dict[str, Any]:
        """Get audit statistics for monitoring"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Total reports
                cursor = conn.execute("SELECT COUNT(*) FROM audit_reports")
                total_reports = cursor.fetchone()[0]
                
                # Decision distribution
                cursor = conn.execute("""
                    SELECT decision, COUNT(*) as count 
                    FROM audit_reports 
                    GROUP BY decision
                """)
                decision_distribution = dict(cursor.fetchall())
                
                # Average deviation score
                cursor = conn.execute("SELECT AVG(deviation_score) FROM audit_reports")
                avg_deviation = cursor.fetchone()[0] or 0.0
                
                # Reports by date (last 7 days)
                cursor = conn.execute("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM audit_reports 
                    WHERE created_at >= datetime('now', '-7 days')
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """)
                daily_reports = dict(cursor.fetchall())
                
                return {
                    "total_reports": total_reports,
                    "decision_distribution": decision_distribution,
                    "average_deviation_score": round(avg_deviation, 3),
                    "daily_reports_last_7_days": daily_reports,
                    "database_path": str(self.db_path),
                    "database_size_mb": round(self.db_path.stat().st_size / (1024 * 1024), 2)
                }
                
        except Exception as e:
            logger.error(f"Failed to get audit statistics: {e}")
            return {"error": str(e)}


# Singleton instance
_audit_persistence_manager = None

def get_audit_persistence_manager() -> AuditPersistenceManager:
    """Get singleton audit persistence manager"""
    global _audit_persistence_manager
    if _audit_persistence_manager is None:
        _audit_persistence_manager = AuditPersistenceManager()
    return _audit_persistence_manager