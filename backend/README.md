# AuthLens Backend API

FastAPI backend for video authentication using blockchain technology.

## Features

- **Process Video Chunks**: Upload 1-minute video chunks with timestamps and store hashes on blockchain
- **Verify Videos**: Verify if a video exists on the blockchain
- **Retrieve Videos**: Combine and retrieve videos from a specific time range

## Setup

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with:
- Your Sepolia RPC URL (from Alchemy, Infura, etc.)
- Your wallet's private key
- Your deployed VideoAuth contract address

### 3. Copy Contract ABI

Copy the `VideoAuth.json` file from your artifacts to the backend directory:

```bash
copy ..\artifacts\contracts\VideoAuth.sol\VideoAuth.json VideoAuth.json
```

### 4. Run the Server

```bash
python main.py
```

Or use uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### 1. Process Video Chunk
**POST** `/api/video/process-chunk`

Upload a 1-minute video chunk with timestamp metadata.

**Parameters:**
- `video` (file): Video file to upload
- `start_time` (query): ISO format datetime (e.g., "2025-10-19T14:30:00")
- `end_time` (query): ISO format datetime (e.g., "2025-10-19T14:31:00")

**Example:**
```bash
curl -X POST "http://localhost:8000/api/video/process-chunk?start_time=2025-10-19T14:30:00&end_time=2025-10-19T14:31:00" \
  -F "video=@video.mp4"
```

**Response:**
```json
{
  "success": true,
  "message": "Video chunk processed successfully",
  "filename": "chunk_2025-10-19_14-30-00_to_2025-10-19_14-31-00.mp4",
  "start_time": "2025-10-19T14:30:00",
  "end_time": "2025-10-19T14:31:00",
  "file_size_bytes": 1048576,
  "blockchain": {
    "success": true,
    "hash": "0xabc123...",
    "transaction_hash": "0xdef456...",
    "already_exists": false
  }
}
```

### 2. Verify Video
**POST** `/api/video/verify`

Verify if a video exists on the blockchain by uploading it.

**Parameters:**
- `video` (file): Video file to verify

**Example:**
```bash
curl -X POST "http://localhost:8000/api/video/verify" \
  -F "video=@video.mp4"
```

**Response:**
```json
{
  "verified": true,
  "hash": "0xabc123...",
  "uploader": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "message": "Video is authentic"
}
```

### 3. Verify Hash
**POST** `/api/video/verify-hash`

Verify if a specific hash exists on the blockchain.

**Body:**
```json
{
  "video_hash": "0xabc123..."
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/video/verify-hash" \
  -H "Content-Type: application/json" \
  -d '{"video_hash": "0xabc123..."}'
```

### 4. Retrieve Video Range
**GET** `/api/video/retrieve`

Retrieve and combine videos from a specific time range.

**Parameters:**
- `start_datetime` (query): ISO format datetime
- `end_datetime` (query): ISO format datetime

**Example:**
```bash
curl -X GET "http://localhost:8000/api/video/retrieve?start_datetime=2025-10-19T14:30:00&end_datetime=2025-10-19T14:35:00" \
  --output combined_video.mp4
```

### 5. List Video Chunks
**GET** `/api/video/list-chunks`

List all available video chunks with optional time filtering.

**Parameters:**
- `start_datetime` (query, optional): Filter from this datetime
- `end_datetime` (query, optional): Filter to this datetime

**Example:**
```bash
curl -X GET "http://localhost:8000/api/video/list-chunks?start_datetime=2025-10-19T14:00:00&end_datetime=2025-10-19T15:00:00"
```

**Response:**
```json
{
  "chunks": [
    {
      "filename": "chunk_2025-10-19_14-30-00_to_2025-10-19_14-31-00.mp4",
      "start_time": "2025-10-19T14:30:00",
      "end_time": "2025-10-19T14:31:00",
      "size_bytes": 1048576
    }
  ],
  "total_chunks": 1
}
```

## Interactive API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Directory Structure

```
backend/
├── main.py              # Main FastAPI application
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (create from .env.example)
├── .env.example         # Example environment variables
├── VideoAuth.json       # Contract ABI (copy from artifacts)
└── video_chunks/        # Storage directory for video chunks (auto-created)
```

## Notes

### Video Combining
The current implementation uses simple binary concatenation for combining video chunks. For production use, consider using FFmpeg for proper video concatenation:

```python
# Example using ffmpeg-python
import ffmpeg

# Create concat file
with open('concat_list.txt', 'w') as f:
    for chunk in chunks:
        f.write(f"file '{chunk}'\n")

# Concatenate videos
ffmpeg.input('concat_list.txt', format='concat', safe=0).output('combined.mp4', c='copy').run()
```

### Security Considerations
- Never commit your `.env` file
- Use environment-specific CORS settings in production
- Implement rate limiting for API endpoints
- Add authentication/authorization as needed
- Validate video file types and sizes

### Production Deployment
For production deployment:
1. Use a proper ASGI server like Gunicorn with Uvicorn workers
2. Set up HTTPS
3. Configure proper CORS origins
4. Implement logging and monitoring
5. Use a database for metadata storage
6. Consider cloud storage for video files (S3, Azure Blob, etc.)
