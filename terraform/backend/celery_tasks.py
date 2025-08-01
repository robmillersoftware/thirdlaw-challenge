"""
Celery tasks for asynchronous PDF processing.
"""

import os
import time
import traceback
from typing import Dict, Any, Optional

from celery import current_task
from celery.exceptions import SoftTimeLimitExceeded

from celery_app import celery_app
from pdf_scanner import PDFScanner
from database import ClickHouseDB
from metrics import metrics_collector

# Initialize components (each worker will have its own instances)
pdf_scanner = PDFScanner()
db = ClickHouseDB()

@celery_app.task(bind=True, name='backend.celery_tasks.process_pdf_async')
def process_pdf_async(self, file_path: str, document_id: str, filename: str) -> Dict[str, Any]:
    """
    Asynchronously process a PDF file for sensitive data scanning.
    
    Args:
        self: Celery task instance
        file_path: Path to the PDF file
        document_id: Unique document identifier
        filename: Original filename
        
    Returns:
        Dictionary with processing results
    """
    operation_id = None
    
    try:
        # Update task state
        self.update_state(state='PROGRESS', meta={'status': 'Starting PDF scan'})
        
        # Get file size for metrics
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        
        # Start metrics tracking
        operation_id = metrics_collector.start_operation(document_id, "async_scan", file_size)
        
        # Validate PDF exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        self.update_state(state='PROGRESS', meta={'status': 'Scanning PDF for sensitive data'})
        
        # Process the PDF
        start_time = time.time()
        scan_result = pdf_scanner.scan_pdf(file_path)
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Determine success
        success = scan_result.get('status') == 'success'
        findings_count = scan_result.get('findings_count', 0)
        pages_processed = scan_result.get('total_pages', 0)
        
        # Store results in database (with connection retry)
        if success:
            self.update_state(state='PROGRESS', meta={'status': 'Storing results in database'})
            
            try:
                if not db.client:
                    db.connect()
                db.store_scan_result(document_id, filename, scan_result, processing_time_ms)
            except Exception as db_error:
                metrics_collector.record_error("database_error", "async_scan")
                print(f"Database error in async task: {db_error}")
        
        # End metrics tracking
        if operation_id:
            metrics_collector.end_operation(
                operation_id,
                success=success,
                findings_count=findings_count,
                pages_processed=pages_processed,
                error_type=None if success else "processing_error"
            )
        
        # Prepare final result
        result = {
            **scan_result,
            'document_id': document_id,
            'filename': filename,
            'processing_time_ms': processing_time_ms,
            'task_id': self.request.id
        }
        
        self.update_state(
            state='SUCCESS', 
            meta={
                'status': 'Processing complete',
                'result': result
            }
        )
        
        return result
        
    except SoftTimeLimitExceeded:
        if operation_id:
            metrics_collector.end_operation(operation_id, success=False, error_type="timeout")
        
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'Task timed out',
                'error': 'PDF processing exceeded time limit'
            }
        )
        raise
        
    except Exception as e:
        if operation_id:
            metrics_collector.end_operation(operation_id, success=False, error_type="unknown_error")
        
        error_trace = traceback.format_exc()
        print(f"Error in async PDF processing: {error_trace}")
        
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'Processing failed',
                'error': str(e),
                'traceback': error_trace
            }
        )
        raise


@celery_app.task(bind=True, name='backend.celery_tasks.process_pdf_scan_redact_async')
def process_pdf_scan_redact_async(self, file_path: str, document_id: str, filename: str) -> Dict[str, Any]:
    """
    Asynchronously process a PDF file for scanning and redaction.
    
    Args:
        self: Celery task instance
        file_path: Path to the PDF file
        document_id: Unique document identifier
        filename: Original filename
        
    Returns:
        Dictionary with processing results
    """
    operation_id = None
    
    try:
        # Update task state
        self.update_state(state='PROGRESS', meta={'status': 'Starting PDF scan and redaction'})
        
        # Get file size for metrics
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        
        # Start metrics tracking
        operation_id = metrics_collector.start_operation(document_id, "async_scan_redact", file_size)
        
        # Validate PDF exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        self.update_state(state='PROGRESS', meta={'status': 'Scanning and redacting PDF'})
        
        # Process the PDF
        start_time = time.time()
        scan_redact_result = pdf_scanner.scan_and_redact_pdf(file_path)
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Determine success and extract metrics
        success = scan_redact_result.get('status') == 'success'
        findings_count = scan_redact_result.get('findings_count', 0)
        pages_processed = scan_redact_result.get('total_pages', 0)
        redacted_instances = 0
        
        if success and 'redaction' in scan_redact_result:
            redacted_instances = scan_redact_result['redaction'].get('redacted_count', 0)
        
        # Store results in database (with connection retry)
        if success:
            self.update_state(state='PROGRESS', meta={'status': 'Storing results in database'})
            
            try:
                if not db.client:
                    db.connect()
                db.store_scan_result(document_id, filename, scan_redact_result, processing_time_ms)
            except Exception as db_error:
                metrics_collector.record_error("database_error", "async_scan_redact")
                print(f"Database error in async task: {db_error}")
        
        # End metrics tracking
        if operation_id:
            metrics_collector.end_operation(
                operation_id,
                success=success,
                findings_count=findings_count,
                pages_processed=pages_processed,
                redacted_instances=redacted_instances,
                error_type=None if success else "processing_error"
            )
        
        # Prepare final result
        result = {
            **scan_redact_result,
            'document_id': document_id,
            'filename': filename,
            'processing_time_ms': processing_time_ms,
            'task_id': self.request.id
        }
        
        self.update_state(
            state='SUCCESS',
            meta={
                'status': 'Processing complete',
                'result': result
            }
        )
        
        return result
        
    except SoftTimeLimitExceeded:
        if operation_id:
            metrics_collector.end_operation(operation_id, success=False, error_type="timeout")
        
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'Task timed out',
                'error': 'PDF processing exceeded time limit'
            }
        )
        raise
        
    except Exception as e:
        if operation_id:
            metrics_collector.end_operation(operation_id, success=False, error_type="unknown_error")
        
        error_trace = traceback.format_exc()
        print(f"Error in async PDF scan/redact processing: {error_trace}")
        
        self.update_state(
            state='FAILURE',
            meta={
                'status': 'Processing failed',
                'error': str(e),
                'traceback': error_trace
            }
        )
        raise


@celery_app.task(name='backend.celery_tasks.cleanup_temp_files')
def cleanup_temp_files(file_paths: list) -> Dict[str, Any]:
    """
    Clean up temporary files after processing.
    
    Args:
        file_paths: List of file paths to clean up
        
    Returns:
        Cleanup results
    """
    cleaned_files = []
    failed_cleanups = []
    
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                cleaned_files.append(file_path)
        except Exception as e:
            failed_cleanups.append({'file': file_path, 'error': str(e)})
    
    return {
        'cleaned_files': cleaned_files,
        'failed_cleanups': failed_cleanups,
        'total_processed': len(file_paths)
    }