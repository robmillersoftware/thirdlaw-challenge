#!/usr/bin/env python3
"""
Generate test PDFs specifically for testing oversized and corrupt PDF handling.
This is separate from the load testing PDF generator.
"""
import os
import tempfile
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import random
import string

def generate_large_pdf(output_path: str, num_pages: int = 1000, with_sensitive_data: bool = True):
    """Generate a large PDF with many pages."""
    print(f"Generating large PDF with {num_pages} pages...")
    
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    # Sample emails and SSNs for testing
    test_emails = [
        "john.doe@example.com",
        "jane.smith@company.org", 
        "admin@testsite.net",
        "user123@domain.co.uk",
        "contact@business.io"
    ]
    
    test_ssns = [
        "123-45-6789",
        "987-65-4321", 
        "555 44 3333",
        "111223333"
    ]
    
    for page_num in range(num_pages):
        # Add title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, f"Test Document - Page {page_num + 1}")
        
        # Add content with random text
        c.setFont("Helvetica", 12)
        y_pos = height - 100
        
        # Add some random paragraphs
        for para in range(10):
            # Random text
            random_text = ''.join(random.choices(string.ascii_letters + string.digits + ' ', k=80))
            c.drawString(50, y_pos, random_text)
            y_pos -= 20
            
            # Randomly add sensitive data
            if with_sensitive_data and random.random() < 0.3:  # 30% chance
                if random.random() < 0.5:
                    # Add email
                    email = random.choice(test_emails)
                    c.drawString(50, y_pos, f"Contact email: {email}")
                else:
                    # Add SSN
                    ssn = random.choice(test_ssns)
                    c.drawString(50, y_pos, f"SSN: {ssn}")
                y_pos -= 20
            
            if y_pos < 100:  # Start new page if running out of space
                break
        
        c.showPage()
        
        # Print progress every 100 pages
        if (page_num + 1) % 100 == 0:
            print(f"  Generated {page_num + 1} pages...")
    
    c.save()
    print(f"Large PDF saved to: {output_path}")

def generate_oversized_pdf(output_path: str, target_size_mb: int = 60):
    """Generate a PDF that exceeds size limits."""
    print(f"Generating oversized PDF (~{target_size_mb}MB)...")
    
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    # Calculate approximate pages needed
    # Rough estimate: each page with lots of text ~= 50KB
    approx_pages = (target_size_mb * 1024) // 50
    
    for page_num in range(approx_pages):
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, f"Oversized Test Document - Page {page_num + 1}")
        
        # Fill page with lots of text to increase size
        c.setFont("Helvetica", 10)
        y_pos = height - 100
        
        # Add dense text content
        dense_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 20
        for line in range(50):  # Many lines per page
            if y_pos > 50:
                c.drawString(50, y_pos, dense_text[:100])  # Truncate to fit
                y_pos -= 12
        
        # Add some sensitive data for testing
        if page_num % 10 == 0:  # Every 10th page
            c.drawString(50, 40, "Email: oversized.test@largefile.com")
            c.drawString(50, 25, "SSN: 999-88-7777")
        
        c.showPage()
        
        # Check file size periodically
        if page_num % 50 == 0 and page_num > 0:
            c.save()
            current_size = os.path.getsize(output_path) / (1024 * 1024)
            print(f"  Current size: {current_size:.1f}MB")
            if current_size >= target_size_mb:
                break
            c = canvas.Canvas(output_path, pagesize=letter)  # Reopen to continue
    
    c.save()
    final_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Oversized PDF saved to: {output_path} ({final_size:.1f}MB)")

def generate_corrupt_pdf(output_path: str):
    """Generate a corrupt PDF file."""
    print("Generating corrupt PDF...")
    
    # First create a valid small PDF
    temp_path = output_path + ".temp"
    c = canvas.Canvas(temp_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(100, 750, "This will be corrupted")
    c.drawString(100, 730, "Email: corrupt@test.com")
    c.drawString(100, 710, "SSN: 123-45-6789")
    c.save()
    
    # Now corrupt it by modifying bytes
    with open(temp_path, 'rb') as f:
        content = bytearray(f.read())
    
    # Corrupt the middle section
    start_corrupt = len(content) // 3
    end_corrupt = start_corrupt + 100
    for i in range(start_corrupt, min(end_corrupt, len(content))):
        content[i] = random.randint(0, 255)
    
    # Write corrupted content
    with open(output_path, 'wb') as f:
        f.write(content)
    
    # Clean up temp file
    os.remove(temp_path)
    print(f"Corrupt PDF saved to: {output_path}")

def generate_empty_pdf(output_path: str):
    """Generate an empty file with PDF extension."""
    print("Generating empty PDF file...")
    with open(output_path, 'w') as f:
        pass  # Create empty file
    print(f"Empty PDF saved to: {output_path}")

def generate_fake_pdf(output_path: str):
    """Generate a file that looks like PDF but isn't."""
    print("Generating fake PDF file...")
    with open(output_path, 'w') as f:
        f.write("This is not a PDF file, just text pretending to be one.")
    print(f"Fake PDF saved to: {output_path}")

def generate_truncated_pdf(output_path: str):
    """Generate a truncated PDF (missing EOF)."""
    print("Generating truncated PDF...")
    
    # Create valid PDF first
    temp_path = output_path + ".temp"
    c = canvas.Canvas(temp_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(100, 750, "This PDF will be truncated")
    c.drawString(100, 730, "Email: truncated@test.com")
    c.save()
    
    # Read and truncate
    with open(temp_path, 'rb') as f:
        content = f.read()
    
    # Remove last 100 bytes (including EOF marker)
    truncated_content = content[:-100]
    
    with open(output_path, 'wb') as f:
        f.write(truncated_content)
    
    os.remove(temp_path)
    print(f"Truncated PDF saved to: {output_path}")

def generate_malformed_header_pdf(output_path: str):
    """Generate a PDF with malformed header."""
    print("Generating malformed header PDF...")
    
    # Create valid PDF first
    temp_path = output_path + ".temp"
    c = canvas.Canvas(temp_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(100, 750, "This PDF has malformed header")
    c.save()
    
    # Read content and corrupt header
    with open(temp_path, 'rb') as f:
        content = bytearray(f.read())
    
    # Corrupt the PDF header
    if content.startswith(b'%PDF'):
        content[0:4] = b'%XDF'  # Change header
    
    with open(output_path, 'wb') as f:
        f.write(content)
    
    os.remove(temp_path)
    print(f"Malformed header PDF saved to: {output_path}")

def main():
    """Generate all test PDFs for oversized/corrupt handling."""
    print("Generating test PDFs for oversized/corrupt handling...")
    
    # Create test directory
    test_dir = "problematic_test_pdfs"
    os.makedirs(test_dir, exist_ok=True)
    
    # Generate different types of problematic PDFs
    test_files = {
        "large_500_pages.pdf": lambda path: generate_large_pdf(path, 500, True),
        "large_1000_pages.pdf": lambda path: generate_large_pdf(path, 1000, True),
        "oversized_60mb.pdf": lambda path: generate_oversized_pdf(path, 60),
        "corrupt.pdf": generate_corrupt_pdf,
        "empty.pdf": generate_empty_pdf,
        "fake.pdf": generate_fake_pdf,
        "truncated.pdf": generate_truncated_pdf,
        "malformed_header.pdf": generate_malformed_header_pdf,
    }
    
    for filename, generator in test_files.items():
        filepath = os.path.join(test_dir, filename)
        try:
            generator(filepath)
        except Exception as e:
            print(f"Error generating {filename}: {e}")
    
    # Generate a normal PDF for comparison
    normal_path = os.path.join(test_dir, "normal_with_sensitive_data.pdf")
    c = canvas.Canvas(normal_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(100, 750, "Normal PDF with sensitive data")
    c.drawString(100, 730, "Email: normal@test.com")
    c.drawString(100, 710, "SSN: 555-12-3456")
    c.drawString(100, 690, "Contact: jane.doe@company.org")
    c.drawString(100, 670, "ID: 987 65 4321")
    c.save()
    print(f"Normal test PDF saved to: {normal_path}")
    
    print("\nTest PDF generation complete!")
    print(f"Files saved in: {test_dir}/")
    
    # Print summary
    print("\nGenerated files:")
    for filename in os.listdir(test_dir):
        filepath = os.path.join(test_dir, filename)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"  {filename}: {size_mb:.2f}MB")

if __name__ == "__main__":
    main()