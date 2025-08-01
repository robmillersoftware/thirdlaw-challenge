#!/usr/bin/env python3
"""
Generate test PDFs for load testing with random data, emails, and SSNs.
"""

import os
import random
import string
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import faker
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Initialize faker for realistic text generation
fake = faker.Faker()

# Common word lists for realistic text
BUSINESS_WORDS = [
    "company", "department", "office", "manager", "employee", "project", "meeting",
    "report", "document", "proposal", "contract", "agreement", "invoice", "budget",
    "quarterly", "annual", "review", "analysis", "strategy", "implementation", 
    "development", "research", "marketing", "sales", "finance", "operations",
    "human resources", "technology", "software", "system", "database", "network",
    "security", "compliance", "audit", "policy", "procedure", "guidelines",
    "performance", "evaluation", "assessment", "training", "workshop", "conference"
]

FILLER_SENTENCES = [
    "This document contains confidential information.",
    "Please review the attached materials carefully.",
    "All employees must comply with company policies.",
    "The quarterly report shows significant growth.",
    "Contact the HR department for more information.",
    "This proposal requires management approval.",
    "The project timeline has been updated.",
    "Please submit your expense reports by Friday.",
    "The new system will be implemented next month.",
    "Training sessions are mandatory for all staff.",
    "Customer data must be handled with care.",
    "The budget allocation has been finalized.",
    "Please confirm your attendance at the meeting.",
    "This information is strictly confidential.",
    "The deadline for submissions is approaching.",
]

def generate_realistic_email():
    """Generate a realistic-looking email address."""
    domains = [
        "company.com", "business.org", "corp.net", "enterprise.com", 
        "firm.co", "group.biz", "solutions.com", "services.net",
        "consulting.org", "systems.com", "tech.io", "startup.co",
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com"
    ]
    
    # Different email patterns
    patterns = [
        lambda: f"{fake.first_name().lower()}.{fake.last_name().lower()}@{random.choice(domains)}",
        lambda: f"{fake.first_name().lower()}{random.randint(1, 999)}@{random.choice(domains)}",
        lambda: f"{fake.last_name().lower()}.{fake.first_name().lower()}@{random.choice(domains)}",
        lambda: f"{fake.user_name()}@{random.choice(domains)}",
        lambda: f"{''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 12)))}@{random.choice(domains)}"
    ]
    
    return random.choice(patterns)()

def generate_realistic_ssn():
    """Generate a realistic-looking SSN in various formats."""
    # Generate 9 digits
    area = random.randint(100, 899)  # Avoid 000, 666, 900-999
    group = random.randint(10, 99)
    serial = random.randint(1000, 9999)
    
    formats = [
        f"{area:03d}-{group:02d}-{serial:04d}",  # XXX-XX-XXXX
        f"{area:03d} {group:02d} {serial:04d}",  # XXX XX XXXX
        f"{area:03d}{group:02d}{serial:04d}",    # XXXXXXXXX
    ]
    
    return random.choice(formats)

def generate_page_content(page_num, total_pages, pdf_index):
    """Generate realistic page content with embedded sensitive data."""
    content_lines = []
    
    # Page header
    content_lines.append(f"Document #{pdf_index:04d} - Page {page_num} of {total_pages}")
    content_lines.append(f"Generated: {fake.date_between(start_date='-2y', end_date='today')}")
    content_lines.append("")
    
    # Document type and context
    doc_types = [
        "Employee Record", "Customer Information", "Project Report", 
        "Financial Statement", "Contact Directory", "Meeting Minutes",
        "Training Materials", "Policy Document", "System Documentation",
        "Vendor Information", "Client Database", "Personnel File"
    ]
    content_lines.append(f"Document Type: {random.choice(doc_types)}")
    content_lines.append("")
    
    # Generate paragraphs with embedded sensitive data
    num_paragraphs = random.randint(3, 7)
    sensitive_data_inserted = 0
    target_sensitive_items = random.randint(2, 6)  # 2-6 sensitive items per page
    
    for para_idx in range(num_paragraphs):
        # Generate paragraph text
        paragraph_sentences = []
        num_sentences = random.randint(3, 8)
        
        for sent_idx in range(num_sentences):
            if random.random() < 0.4:  # 40% chance of filler sentence
                sentence = random.choice(FILLER_SENTENCES)
            else:
                # Generate fake business-like sentence
                sentence = fake.sentence()
                # Occasionally inject business words
                if random.random() < 0.3:
                    words = sentence.split()
                    insert_pos = random.randint(1, len(words) - 1)
                    words.insert(insert_pos, random.choice(BUSINESS_WORDS))
                    sentence = " ".join(words)
            
            # Randomly insert sensitive data into sentences
            if (sensitive_data_inserted < target_sensitive_items and 
                random.random() < 0.4):  # 40% chance per sentence
                
                if random.random() < 0.5:  # 50% email, 50% SSN
                    email = generate_realistic_email()
                    insertion_patterns = [
                        f"{sentence[:-1]} Contact: {email}.",
                        f"{sentence[:-1]} Email: {email}.",
                        f"Please reach out to {email}. {sentence}",
                        f"{sentence[:-1]} ({email}).",
                        f"For questions, email {email}. {sentence}",
                    ]
                    sentence = random.choice(insertion_patterns)
                else:
                    ssn = generate_realistic_ssn()
                    insertion_patterns = [
                        f"{sentence[:-1]} ID: {ssn}.",
                        f"{sentence[:-1]} SSN: {ssn}.",
                        f"Employee number {ssn}. {sentence}",
                        f"{sentence[:-1]} (ID: {ssn}).",
                        f"Reference: {ssn}. {sentence}",
                    ]
                    sentence = random.choice(insertion_patterns)
                
                sensitive_data_inserted += 1
            
            paragraph_sentences.append(sentence)
        
        paragraph = " ".join(paragraph_sentences)
        content_lines.append(paragraph)
        content_lines.append("")  # Empty line between paragraphs
    
    # Add some structured data sections occasionally
    if random.random() < 0.3:  # 30% chance
        content_lines.append("Contact Information:")
        for i in range(random.randint(2, 5)):
            name = fake.name()
            email = generate_realistic_email()
            content_lines.append(f"  {name} - {email}")
        content_lines.append("")
    
    if random.random() < 0.2:  # 20% chance
        content_lines.append("Employee Records:")
        for i in range(random.randint(1, 3)):
            name = fake.name()
            ssn = generate_realistic_ssn()
            dept = random.choice(["Engineering", "Marketing", "Sales", "HR", "Finance"])
            content_lines.append(f"  {name} - {dept} - ID: {ssn}")
        content_lines.append("")
    
    # Footer
    content_lines.append("")
    content_lines.append(f"Document ID: {fake.uuid4()}")
    if random.random() < 0.5:
        content_lines.append(f"Contact: {generate_realistic_email()}")
    
    return content_lines

def create_pdf(pdf_index, output_dir):
    """Create a single PDF with realistic content."""
    filename = f"test_document_{pdf_index:04d}.pdf"
    filepath = os.path.join(output_dir, filename)
    
    # Random number of pages (weighted towards fewer pages)
    page_weights = [0.4, 0.3, 0.15, 0.1, 0.05]  # 1-5 pages
    num_pages = random.choices(range(1, 6), weights=page_weights)[0]
    
    c = canvas.Canvas(filepath, pagesize=letter)
    width, height = letter
    
    for page_num in range(1, num_pages + 1):
        if page_num > 1:
            c.showPage()
        
        # Generate content for this page
        content_lines = generate_page_content(page_num, num_pages, pdf_index)
        
        # Write content to PDF
        y_position = height - 50  # Start near top
        line_height = 14
        
        for line in content_lines:
            if y_position < 50:  # Near bottom of page
                break
            
            # Handle long lines by wrapping
            if len(line) > 80:
                words = line.split()
                current_line = ""
                for word in words:
                    if len(current_line + word) > 80:
                        if current_line:
                            c.drawString(50, y_position, current_line.strip())
                            y_position -= line_height
                            if y_position < 50:
                                break
                        current_line = word + " "
                    else:
                        current_line += word + " "
                
                if current_line and y_position >= 50:
                    c.drawString(50, y_position, current_line.strip())
                    y_position -= line_height
            else:
                c.drawString(50, y_position, line)
                y_position -= line_height
    
    c.save()
    return filename

def generate_test_pdfs(num_pdfs=1000, output_dir="test_pdfs", max_workers=8):
    """Generate test PDFs using multiple threads."""
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"🚀 Generating {num_pdfs} test PDFs in '{output_dir}' directory...")
    print(f"Using {max_workers} worker threads for parallel generation")
    
    start_time = time.time()
    completed = 0
    
    # Use ThreadPoolExecutor for parallel PDF generation
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(create_pdf, i, output_dir): i 
            for i in range(1, num_pdfs + 1)
        }
        
        # Process completed tasks
        for future in as_completed(futures):
            pdf_index = futures[future]
            try:
                filename = future.result()
                completed += 1
                
                # Progress reporting
                if completed % 50 == 0 or completed == num_pdfs:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (num_pdfs - completed) / rate if rate > 0 else 0
                    
                    print(f"✅ Progress: {completed}/{num_pdfs} ({completed/num_pdfs*100:.1f}%) "
                          f"- Rate: {rate:.1f} PDFs/sec - ETA: {eta:.0f}s")
                
            except Exception as e:
                print(f"❌ Error generating PDF {pdf_index}: {e}")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n🎉 Generation complete!")
    print(f"📊 Statistics:")
    print(f"   • Total PDFs: {completed}/{num_pdfs}")
    print(f"   • Total time: {total_time:.1f} seconds")
    print(f"   • Average rate: {completed/total_time:.1f} PDFs/second")
    print(f"   • Directory: {os.path.abspath(output_dir)}")
    
    # Calculate directory size
    total_size = 0
    for filename in os.listdir(output_dir):
        if filename.endswith('.pdf'):
            filepath = os.path.join(output_dir, filename)
            total_size += os.path.getsize(filepath)
    
    print(f"   • Total size: {total_size / (1024*1024):.1f} MB")
    print(f"   • Average size: {total_size / completed / 1024:.1f} KB per PDF")
    
    return output_dir

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate test PDFs for load testing")
    parser.add_argument("--count", "-c", type=int, default=1000, 
                       help="Number of PDFs to generate (default: 1000)")
    parser.add_argument("--output", "-o", type=str, default="test_pdfs",
                       help="Output directory (default: test_pdfs)")
    parser.add_argument("--workers", "-w", type=int, default=8,
                       help="Number of worker threads (default: 8)")
    
    args = parser.parse_args()
    
    # Install faker if not available
    try:
        import faker
    except ImportError:
        print("📦 Installing faker library...")
        import subprocess
        subprocess.check_call(["pip", "install", "faker"])
        import faker
    
    generate_test_pdfs(args.count, args.output, args.workers)