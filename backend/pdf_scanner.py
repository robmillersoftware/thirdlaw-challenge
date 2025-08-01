import re
import PyPDF2
import pdfplumber
import fitz  # PyMuPDF for redaction
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import os
import tempfile
import gc
import weakref
from contextlib import contextmanager

@dataclass
class Finding:
    type: str
    value: str
    page: int
    position: Dict[str, Any] = None

class PDFScanner:
    def __init__(self):
        # Email regex pattern
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        
        # SSN regex patterns (various formats)
        self.ssn_patterns = [
            re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),  # XXX-XX-XXXX
            re.compile(r'\b\d{3}\s\d{2}\s\d{4}\b'),  # XXX XX XXXX
            re.compile(r'\b\d{9}\b'),  # XXXXXXXXX (9 consecutive digits)
        ]
        
        # Track active PDF objects for memory management
        self._active_pdfs = weakref.WeakSet()
    
    @contextmanager
    def _memory_managed_processing(self):
        """Context manager for memory-optimized PDF processing."""
        try:
            yield
        finally:
            # Force garbage collection after processing
            gc.collect()

    def scan_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Scan a PDF file for sensitive data with memory optimization.
        Returns a dictionary with scan results.
        """
        with self._memory_managed_processing():
            try:
                findings = []
                total_pages = 0
                file_size = os.path.getsize(file_path)
                
                # Try pdfplumber first (better text extraction)
                try:
                    with pdfplumber.open(file_path) as pdf:
                        self._active_pdfs.add(pdf)
                        total_pages = len(pdf.pages)
                        
                        # Process pages in batches to manage memory
                        batch_size = 5  # Process 5 pages at a time
                        for i in range(0, total_pages, batch_size):
                            batch_findings = []
                            end_idx = min(i + batch_size, total_pages)
                            
                            for page_num in range(i, end_idx):
                                page = pdf.pages[page_num]
                                text = page.extract_text()
                                if text:
                                    page_findings = self._scan_text(text, page_num + 1)
                                    batch_findings.extend(page_findings)
                                # Clear page text from memory
                                del text
                            
                            findings.extend(batch_findings)
                            # Force garbage collection between batches
                            if i > 0:
                                gc.collect()
                                
                except Exception as pdfplumber_error:
                    # Fallback to PyPDF2 with memory management
                    try:
                        with open(file_path, 'rb') as file:
                            pdf_reader = PyPDF2.PdfReader(file)
                            total_pages = len(pdf_reader.pages)
                            
                            # Process in batches
                            batch_size = 5
                            for i in range(0, total_pages, batch_size):
                                batch_findings = []
                                end_idx = min(i + batch_size, total_pages)
                                
                                for page_num in range(i, end_idx):
                                    page = pdf_reader.pages[page_num]
                                    text = page.extract_text()
                                    if text:
                                        page_findings = self._scan_text(text, page_num + 1)
                                        batch_findings.extend(page_findings)
                                    # Clear page text from memory
                                    del text
                                
                                findings.extend(batch_findings)
                                # Force garbage collection between batches
                                if i > 0:
                                    gc.collect()
                                    
                    except Exception as pypdf2_error:
                        return {
                            'status': 'error',
                            'error': f'Could not read PDF: {str(pypdf2_error)}',
                            'file_size': file_size
                        }
                
                # Remove duplicates
                unique_findings = self._deduplicate_findings(findings)
                
                return {
                    'status': 'success',
                    'findings': [
                        {
                            'type': f.type,
                            'value': f.value,
                            'page': f.page,
                            'position': f.position
                        } for f in unique_findings
                    ],
                    'total_pages': total_pages,
                    'file_size': file_size,
                    'findings_count': len(unique_findings)
                }
                
            except Exception as e:
                return {
                    'status': 'error',
                    'error': str(e),
                    'file_size': os.path.getsize(file_path) if os.path.exists(file_path) else 0
                }

    def _scan_text(self, text: str, page_num: int) -> List[Finding]:
        """Scan text content for sensitive data patterns."""
        findings = []
        
        # Scan for emails
        email_matches = self.email_pattern.finditer(text)
        for match in email_matches:
            findings.append(Finding(
                type='email',
                value=match.group(),
                page=page_num,
                position={'start': match.start(), 'end': match.end()}
            ))
        
        # Scan for SSNs
        for ssn_pattern in self.ssn_patterns:
            ssn_matches = ssn_pattern.finditer(text)
            for match in ssn_matches:
                # Additional validation for 9-digit pattern
                if len(match.group().replace('-', '').replace(' ', '')) == 9:
                    findings.append(Finding(
                        type='ssn',
                        value=match.group(),
                        page=page_num,
                        position={'start': match.start(), 'end': match.end()}
                    ))
        
        return findings

    def _deduplicate_findings(self, findings: List[Finding]) -> List[Finding]:
        """Remove duplicate findings based on type and value."""
        seen = set()
        unique_findings = []
        
        for finding in findings:
            key = (finding.type, finding.value)
            if key not in seen:
                seen.add(key)
                unique_findings.append(finding)
        
        return unique_findings

    def is_valid_pdf(self, file_path: str) -> bool:
        """Check if file is a valid PDF."""
        try:
            with open(file_path, 'rb') as file:
                # Check PDF header
                header = file.read(4)
                return header == b'%PDF'
        except Exception:
            return False

    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get basic information about the PDF file."""
        if not os.path.exists(file_path):
            return {'error': 'File not found'}
        
        file_size = os.path.getsize(file_path)
        
        try:
            with pdfplumber.open(file_path) as pdf:
                return {
                    'file_size': file_size,
                    'total_pages': len(pdf.pages),
                    'is_valid': True
                }
        except Exception:
            try:
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    return {
                        'file_size': file_size,
                        'total_pages': len(pdf_reader.pages),
                        'is_valid': True
                    }
            except Exception as e:
                return {
                    'file_size': file_size,
                    'total_pages': 0,
                    'is_valid': False,
                    'error': str(e)
                }

    def create_redacted_pdf(self, file_path: str, findings: List[Finding], output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a redacted version of the PDF with sensitive data blacked out.
        Memory-optimized version with proper resource cleanup.
        
        Args:
            file_path: Path to the original PDF
            findings: List of findings to redact
            output_path: Output path for redacted PDF (optional)
            
        Returns:
            Dictionary with redaction results
        """
        with self._memory_managed_processing():
            doc = None
            try:
                if not output_path:
                    # Create output path with _redacted suffix
                    base_name = os.path.splitext(file_path)[0]
                    output_path = f"{base_name}_redacted.pdf"
                
                # Open PDF with PyMuPDF
                doc = fitz.open(file_path)
                self._active_pdfs.add(doc)
                
                redacted_count = 0
                
                # Group findings by page for efficient processing
                findings_by_page = {}
                for finding in findings:
                    page_num = finding.page - 1  # PyMuPDF uses 0-based indexing
                    if page_num not in findings_by_page:
                        findings_by_page[page_num] = []
                    findings_by_page[page_num].append(finding)
                
                # Process each page with findings
                for page_num, page_findings in findings_by_page.items():
                    if page_num >= len(doc):
                        continue
                        
                    page = doc[page_num]
                    
                    # Find and redact text instances
                    for finding in page_findings:
                        text_instances = page.search_for(finding.value)
                        
                        for rect in text_instances:
                            # Create redaction annotation
                            redact_annot = page.add_redact_annot(rect)
                            redact_annot.set_colors(stroke=(0, 0, 0), fill=(0, 0, 0))  # Black redaction
                            redact_annot.update()
                            redacted_count += 1
                    
                    # Apply redactions to the page
                    page.apply_redactions()
                    
                    # Force garbage collection every 10 pages
                    if page_num % 10 == 0:
                        gc.collect()
                
                # Save redacted PDF
                doc.save(output_path)
                
                return {
                    'status': 'success',
                    'output_path': output_path,
                    'redacted_count': redacted_count,
                    'original_file': file_path,
                    'file_size': os.path.getsize(output_path)
                }
                
            except Exception as e:
                return {
                    'status': 'error',
                    'error': str(e),
                    'original_file': file_path
                }
            finally:
                # Ensure document is properly closed
                if doc:
                    try:
                        doc.close()
                    except:
                        pass

    def scan_and_redact_pdf(self, file_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Scan a PDF for sensitive data and create a redacted version.
        
        Args:
            file_path: Path to the original PDF
            output_path: Output path for redacted PDF (optional)
            
        Returns:
            Dictionary with scan and redaction results
        """
        # First, scan for sensitive data
        scan_result = self.scan_pdf(file_path)
        
        if scan_result['status'] != 'success':
            return scan_result
        
        # Convert findings dict back to Finding objects for redaction
        findings = []
        for finding_dict in scan_result['findings']:
            findings.append(Finding(
                type=finding_dict['type'],
                value=finding_dict['value'],
                page=finding_dict['page'],
                position=finding_dict['position']
            ))
        
        # Create redacted version if findings exist
        if findings:
            redaction_result = self.create_redacted_pdf(file_path, findings, output_path)
            
            # Combine scan and redaction results
            return {
                **scan_result,
                'redaction': redaction_result
            }
        else:
            # No sensitive data found, no redaction needed
            return {
                **scan_result,
                'redaction': {
                    'status': 'no_redaction_needed',
                    'message': 'No sensitive data found to redact'
                }
            }