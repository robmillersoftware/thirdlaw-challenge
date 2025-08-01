# PDF Sensitive Data Scanner

A web application that scans PDF files for sensitive information like email addresses and Social Security numbers, storing results in ClickHouse database.

## Features

### Core Features ✅
- Single-page web interface for PDF file uploads
- Python server that analyzes PDFs for sensitive data:
  - Email addresses (RFC compliant regex)
  - Social Security numbers (multiple formats: XXX-XX-XXXX, XXX XX XXXX, XXXXXXXXX)
- ClickHouse database integration for storing results
- RESTful API endpoint (`/findings`) returning results in JSON format
- File validation and error handling

### Architecture
- **Frontend**: HTML5 with vanilla JavaScript (drag & drop file upload)
- **Backend**: FastAPI (Python) with async processing
- **Database**: ClickHouse (single-node via Docker)
- **PDF Processing**: PyPDF2 + pdfplumber for robust text extraction

## Setup and Installation

### Prerequisites
- Python 3.8+
- Docker and Docker Compose
- Git

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd thirdlaw-challenge
   ```

2. **Start ClickHouse database**
   ```bash
   docker-compose up -d
   ```

3. **Set up Python environment**
   ```bash
   python -m venv venv
   source ./venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Start the application**
   ```bash
   cd backend
   python main.py
   ```

5. **Access the application**
   - Open your browser to `http://localhost:8000`
   - API documentation: `http://localhost:8000/docs`

## Usage

### Web Interface
1. Navigate to `http://localhost:8000`
2. Drag and drop PDF files or click to select them
3. Click "Upload and Scan" to process files
4. View results immediately on the page
5. Check "Recent Findings" section for historical data

### API Endpoints

#### Upload and Scan PDF
```bash
POST /upload
Content-Type: multipart/form-data

curl -X POST "http://localhost:8000/upload" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@sample.pdf"
```

#### Get Findings
```bash
GET /findings?limit=50&document_id=optional-uuid

curl "http://localhost:8000/findings"
```

#### Health Check
```bash
GET /health

curl "http://localhost:8000/health"
```

#### Statistics
```bash
GET /stats

curl "http://localhost:8000/stats"
```

### Sample Response Format

**Upload Response:**
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "sample.pdf",
  "status": "success",
  "processing_time_ms": 234,
  "findings": [
    {
      "type": "email",
      "value": "user@example.com",
      "page": 1,
      "position": {"start": 123, "end": 140}
    },
    {
      "type": "ssn",
      "value": "123-45-6789",
      "page": 2,
      "position": {"start": 456, "end": 467}
    }
  ],
  "findings_count": 2,
  "total_pages": 5,
  "file_size": 102400
}
```

**Findings Response:**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "filename": "sample.pdf",
    "processed_at": "2023-08-01T12:34:56",
    "status": "success",
    "findings_count": 2,
    "total_pages": 5,
    "file_size": 102400,
    "processing_time_ms": 234,
    "findings": [
      {
        "type": "email",
        "value": "user@example.com",
        "page": 1
      }
    ]
  }
]
```

## Database Schema

### Documents Table
```sql
CREATE TABLE documents (
    id String,
    filename String,
    file_size UInt64,
    total_pages UInt32,
    processed_at DateTime,
    status String,
    error_message String,
    findings_count UInt32,
    processing_time_ms UInt32
) ENGINE = MergeTree() ORDER BY processed_at
```

### Findings Table
```sql
CREATE TABLE findings (
    document_id String,
    finding_type String,
    finding_value String,
    page_number UInt32,
    position_start Nullable(UInt32),
    position_end Nullable(UInt32),
    detected_at DateTime
) ENGINE = MergeTree() ORDER BY (document_id, detected_at)
```

## Configuration

Environment variables (`.env` file):
```bash
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
CLICKHOUSE_DATABASE=pdf_scanner
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=10485760  # 10MB
```

## Error Handling

The application handles various error scenarios:
- Invalid file types (non-PDF files)
- Oversized files (configurable limit)
- Corrupted PDF files
- Database connection issues
- Processing timeouts

## Development

### Project Structure
```
thirdlaw-challenge/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── pdf_scanner.py       # PDF processing logic
│   └── database.py          # ClickHouse integration
├── static/
│   └── index.html           # Frontend interface
├── uploads/                 # Temporary file storage
├── docker-compose.yml       # ClickHouse setup
├── requirements.txt         # Python dependencies
└── README.md
```

### Testing

Test the application with various PDF files:
```bash
# Test with curl
curl -X POST "http://localhost:8000/upload" \
     -H "accept: application/json" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@test.pdf"

# Check findings
curl "http://localhost:8000/findings"

# Health check
curl "http://localhost:8000/health"
```

## Troubleshooting

### Common Issues

1. **ClickHouse connection failed**
   ```bash
   # Check if ClickHouse is running
   docker ps
   curl http://localhost:8123
   ```

2. **Port 8000 already in use**
   ```bash
   # Find and kill the process
   lsof -i :8000
   kill <PID>
   ```

3. **Module not found errors**
   ```bash
   # Ensure virtual environment is activated
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Permission denied errors**
   ```bash
   # Check file permissions
   chmod +x backend/main.py
   ```

### Logs

Application logs are printed to stdout. For debugging:
```bash
# Run with debug logging
cd backend
python main.py
```

ClickHouse logs:
```bash
docker logs thirdlaw-challenge-clickhouse-1
```

## Performance Notes

- Files are processed synchronously for simplicity
- Temporary files are cleaned up after processing
- ClickHouse provides high-performance analytics storage
- Processing time scales with document size and complexity

## Security Considerations

- File type validation prevents non-PDF uploads
- File size limits prevent DoS attacks
- Temporary files are cleaned up automatically
- No authentication required (as per requirements)
- Sensitive data is logged but not exposed in responses

---

## Next Steps (Bonus Features)

The core application is complete. Additional features can be implemented:

1. **PDF Redaction**: Generate redacted versions with sensitive data blacked out
2. **Enhanced Error Handling**: Better corrupt file detection and recovery
3. **Performance Metrics**: Real-time performance dashboard
4. **Deployment**: Containerized deployment to cloud platforms
5. **Custom Features**: WebSocket progress updates, bulk processing, etc.

Built with ❤️ for the Thirdlaw code challenge.