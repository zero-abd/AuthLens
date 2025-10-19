# AuthLens Integration Documentation

## Overview
AuthLens has been integrated with full monitoring and validation pipelines, allowing real-time video capture synchronized to clock minutes and blockchain-backed video authentication.

## Features Implemented

### 1. Live Monitoring (`/monitor` route)
- **Real-time Video Capture**: Records from webcam in 1-minute synchronized chunks
- **Minute-Aligned Recording**: Automatically starts/stops at :00 seconds
- **Automatic Upload**: Sends each chunk to backend with metadata
- **Blockchain Storage**: Each chunk is hashed and stored on-chain
- **Filename Format**: `cam_1_YYYY-MM-DD_HH-MM-00-YYYY-MM-DD_HH-MM-00.mp4`
- **Storage Location**: `backend/db/` folder

#### How to Use:
1. Navigate to `/monitor` page
2. Click "Start Monitoring" button
3. System waits for the next minute mark (:00 seconds)
4. Recording begins and continues in 1-minute intervals
5. Each chunk is automatically uploaded and stored
6. Click "Stop Monitoring" to finish current chunk and end

### 2. Video Validation (`/validate` route)
- **Upload Interface**: Drag-and-drop or file picker
- **Progress Bar**: Real-time upload and validation progress
- **Chunk Analysis**: Splits videos into minute segments
- **Blockchain Verification**: Checks each chunk against stored hashes
- **Verdict System**:
  - ✅ **Validated**: Recorded on facility camera
  - ❌ **Not Validated**: Not recorded on facility camera
  - ⚠️ **Partially Validated**: Some chunks validated
- **Auto-Cleanup**: Uploaded videos deleted after verification

#### How to Use:
1. Navigate to `/validate` page
2. Upload a video file
3. System processes and validates against stored hashes
4. View detailed results for each chunk
5. Video is automatically removed after validation

## Backend API Endpoints

### Monitor Upload Endpoint
```
POST /api/monitor/upload-chunk
```
**Parameters:**
- `video`: multipart file upload
- `camera_id`: string (e.g., "cam_1")
- `start_time`: string (format: YYYY-MM-DD_HH-MM-SS)
- `end_time`: string (format: YYYY-MM-DD_HH-MM-SS)

**Response:**
```json
{
  "success": true,
  "filename": "cam_1_2025-10-19_14-30-00-2025-10-19_14-31-00.mp4",
  "video_hash": "0xabc123...",
  "blockchain": {
    "transaction_hash": "0x...",
    "already_exists": false
  }
}
```

### Validation Endpoint
```
POST /api/validate/upload
```
**Parameters:**
- `video`: multipart file upload

**Response:**
```json
{
  "success": true,
  "verdict": "validated" | "not_validated" | "partially_validated",
  "message": "Video is validated - recorded on a facility camera",
  "total_chunks": 3,
  "validated_chunks": 3,
  "not_validated_chunks": 0,
  "chunk_details": [
    {
      "chunk_index": 0,
      "hash": "0xabc...",
      "verified": true,
      "status": "validated"
    }
  ]
}
```

## Technical Details

### Frontend Technology
- **React + TypeScript**
- **MediaRecorder API**: WebM video capture
- **Axios**: HTTP requests
- **Framer Motion**: Animations
- **React Router**: Navigation

### Backend Technology
- **FastAPI**: Python web framework
- **Web3.py**: Blockchain integration
- **Sepolia Testnet**: Ethereum blockchain
- **SHA-256**: Video hashing algorithm

### Video Recording
- **Format**: WebM with VP8 codec
- **Resolution**: 1280x720 (720p)
- **Chunk Duration**: Exactly 60 seconds
- **Synchronization**: Aligned to system clock minutes
- **Storage**: Local filesystem + blockchain hash

### Validation Process
1. Upload video file
2. Read file content
3. Calculate SHA-256 hash
4. Query blockchain for hash
5. Return verification result
6. Delete uploaded file

## Configuration

### Backend Environment Variables
Create a `.env` file in the `backend/` directory:
```env
SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_KEY
PRIVATE_KEY=your_wallet_private_key
CONTRACT_ADDRESS=your_deployed_contract_address
```

### Frontend Configuration
Update `BACKEND_URL` in:
- `src/pages/Monitor.tsx`
- `src/pages/Validate.tsx`

Default: `http://localhost:8000`

## Running the Application

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```
Server runs on: `http://localhost:8000`

### Frontend
```bash
cd AuthLens-Frontend
npm install
npm start
```
App runs on: `http://localhost:3000`

## File Structure
```
AuthLens/
├── backend/
│   ├── main.py                 # FastAPI server
│   ├── db/                     # Stored video chunks
│   ├── video_chunks/           # Legacy storage
│   └── requirements.txt
├── AuthLens-Frontend/
│   └── src/
│       ├── pages/
│       │   ├── Monitor.tsx     # Live monitoring page
│       │   ├── Monitor.css
│       │   ├── Validate.tsx    # Validation page
│       │   └── Validate.css
│       └── Root.tsx            # Route configuration
└── README.md
```

## Security Considerations

### Production Deployment
1. **CORS**: Configure allowed origins properly
2. **Rate Limiting**: Add request throttling
3. **File Size Limits**: Enforce max upload size
4. **Authentication**: Add user authentication
5. **Storage**: Use cloud storage (S3, GCS)
6. **HTTPS**: Enable SSL/TLS
7. **Private Key**: Use secrets manager

### Video Processing
- Current implementation is simplified
- Production should use FFmpeg for proper video splitting
- Add video format validation
- Implement virus scanning
- Add file type verification

## Future Enhancements
1. Multiple camera support
2. Live streaming to backend
3. Real-time dashboard
4. Video playback interface
5. Advanced analytics
6. Metadata extraction
7. Face detection
8. Motion detection
9. Cloud storage integration
10. Mobile app support

## Troubleshooting

### Camera Access Issues
- Check browser permissions
- Ensure HTTPS (or localhost)
- Try different browser
- Check system camera settings

### Upload Failures
- Check backend is running
- Verify CORS configuration
- Check network connectivity
- Ensure sufficient disk space

### Blockchain Errors
- Verify RPC URL is accessible
- Check wallet has sufficient ETH
- Confirm contract is deployed
- Validate contract ABI

### Validation Issues
- Ensure video was recorded with monitoring
- Check timestamp alignment
- Verify blockchain sync
- Check hash calculation

## Support
For issues and questions, please refer to the project repository.
