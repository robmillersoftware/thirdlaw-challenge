import clickhouse_connect
from datetime import datetime
from typing import List, Dict, Any, Optional
import json
import os
from dotenv import load_dotenv

load_dotenv()

class ClickHouseDB:
    def __init__(self):
        self.host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        self.port = int(os.getenv('CLICKHOUSE_PORT', 8123))
        self.user = os.getenv('CLICKHOUSE_USER', 'default')
        self.password = os.getenv('CLICKHOUSE_PASSWORD', '')
        self.database = os.getenv('CLICKHOUSE_DATABASE', 'pdf_scanner')
        self.client = None

    def connect(self):
        """Connect to ClickHouse database."""
        try:
            self.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password
            )
            
            # Create database if it doesn't exist
            self.client.command(f'CREATE DATABASE IF NOT EXISTS {self.database}')
            
            # Switch to the database
            self.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
                database=self.database
            )
            
            # Create tables
            self._create_tables()
            return True
            
        except Exception as e:
            print(f"Error connecting to ClickHouse: {e}")
            return False

    def _create_tables(self):
        """Create necessary tables."""
        
        # Main documents table
        create_documents_table = """
        CREATE TABLE IF NOT EXISTS documents (
            id String,
            filename String,
            file_size UInt64,
            total_pages UInt32,
            processed_at DateTime,
            status String,
            error_message String,
            findings_count UInt32,
            processing_time_ms UInt32
        ) ENGINE = MergeTree()
        ORDER BY processed_at
        """
        
        # Findings table
        create_findings_table = """
        CREATE TABLE IF NOT EXISTS findings (
            document_id String,
            finding_type String,
            finding_value String,
            page_number UInt32,
            position_start Nullable(UInt32),
            position_end Nullable(UInt32),
            detected_at DateTime
        ) ENGINE = MergeTree()
        ORDER BY (document_id, detected_at)
        """
        
        self.client.command(create_documents_table)
        self.client.command(create_findings_table)

    def store_scan_result(self, document_id: str, filename: str, scan_result: Dict[str, Any], processing_time_ms: int) -> bool:
        """Store PDF scan results in the database."""
        try:
            # Insert document record
            document_data = {
                'id': document_id,
                'filename': filename,
                'file_size': scan_result.get('file_size', 0),
                'total_pages': scan_result.get('total_pages', 0),
                'processed_at': datetime.now(),
                'status': scan_result.get('status', 'unknown'),
                'error_message': scan_result.get('error', ''),
                'findings_count': scan_result.get('findings_count', 0),
                'processing_time_ms': processing_time_ms
            }
            
            self.client.insert('documents', [document_data])
            
            # Insert findings if any
            if scan_result.get('findings'):
                findings_data = []
                current_time = datetime.now()
                
                for finding in scan_result['findings']:
                    finding_record = {
                        'document_id': document_id,
                        'finding_type': finding['type'],
                        'finding_value': finding['value'],
                        'page_number': finding['page'],
                        'position_start': finding.get('position', {}).get('start'),
                        'position_end': finding.get('position', {}).get('end'),
                        'detected_at': current_time
                    }
                    findings_data.append(finding_record)
                
                self.client.insert('findings', findings_data)
            
            return True
            
        except Exception as e:
            print(f"Error storing scan result: {e}")
            return False

    def get_findings(self, limit: int = 100, document_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve findings from the database."""
        try:
            if document_id:
                query = """
                SELECT 
                    d.id,
                    d.filename,
                    d.processed_at,
                    d.status,
                    d.findings_count,
                    d.total_pages,
                    d.file_size,
                    d.processing_time_ms,
                    groupArray(tuple(f.finding_type, f.finding_value, f.page_number)) as findings
                FROM documents d
                LEFT JOIN findings f ON d.id = f.document_id
                WHERE d.id = %(document_id)s
                GROUP BY d.id, d.filename, d.processed_at, d.status, d.findings_count, d.total_pages, d.file_size, d.processing_time_ms
                ORDER BY d.processed_at DESC
                """
                params = {'document_id': document_id}
            else:
                query = """
                SELECT 
                    d.id,
                    d.filename,
                    d.processed_at,
                    d.status,
                    d.findings_count,
                    d.total_pages,
                    d.file_size,
                    d.processing_time_ms,
                    groupArray(tuple(f.finding_type, f.finding_value, f.page_number)) as findings
                FROM documents d
                LEFT JOIN findings f ON d.id = f.document_id
                GROUP BY d.id, d.filename, d.processed_at, d.status, d.findings_count, d.total_pages, d.file_size, d.processing_time_ms
                ORDER BY d.processed_at DESC
                LIMIT %(limit)s
                """
                params = {'limit': limit}
            
            result = self.client.query(query, params)
            
            documents = []
            for row in result.result_rows:
                doc = {
                    'id': row[0],
                    'filename': row[1],
                    'processed_at': row[2].isoformat() if row[2] else None,
                    'status': row[3],
                    'findings_count': row[4],
                    'total_pages': row[5],
                    'file_size': row[6],
                    'processing_time_ms': row[7],
                    'findings': []
                }
                
                # Parse findings
                if row[8] and row[8][0] != ('', '', 0):  # Check if findings exist
                    for finding_tuple in row[8]:
                        if finding_tuple[0]:  # Check if finding_type is not empty
                            doc['findings'].append({
                                'type': finding_tuple[0],
                                'value': finding_tuple[1],
                                'page': finding_tuple[2]
                            })
                
                documents.append(doc)
            
            return documents
            
        except Exception as e:
            print(f"Error retrieving findings: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            stats_query = """
            SELECT 
                count() as total_documents,
                sum(findings_count) as total_findings,
                avg(processing_time_ms) as avg_processing_time,
                quantile(0.95)(processing_time_ms) as p95_processing_time,
                sum(file_size) as total_file_size
            FROM documents
            WHERE status = 'success'
            """
            
            result = self.client.query(stats_query)
            row = result.result_rows[0]
            
            return {
                'total_documents': row[0],
                'total_findings': row[1],
                'avg_processing_time_ms': round(row[2], 2) if row[2] else 0,
                'p95_processing_time_ms': round(row[3], 2) if row[3] else 0,
                'total_file_size_bytes': row[4]
            }
            
        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}

    def health_check(self) -> bool:
        """Check if database connection is healthy."""
        try:
            self.client.query("SELECT 1")
            return True
        except Exception:
            return False