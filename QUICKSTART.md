# AuthLens Quick Start Guide

## Setup Instructions

### Prerequisites
- Python 3.8+
- Node.js 16+
- npm or yarn
- Web browser with camera access
- Ethereum wallet with Sepolia ETH

### Step 1: Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Create virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Create a `.env` file in the `backend` directory:
   ```env
   SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_KEY
   PRIVATE_KEY=your_wallet_private_key_without_0x
   CONTRACT_ADDRESS=your_deployed_contract_address
   ```

5. **Start the backend server:**
   ```bash
   python main.py
   ```
   
   Server should start on `http://localhost:8000`
   You should see:
   ```
   ✅ Connected to Ethereum. Using wallet: 0x...
   ✅ Contract loaded at address: 0x...
   ```

### Step 2: Frontend Setup

1. **Navigate to frontend directory:**
   ```bash
   cd AuthLens-Frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm start
   ```
   
   App should open at `http://localhost:3000`

### Step 3: Test the Integration

#### Test Live Monitoring:
1. Open `http://localhost:3000/monitor`
2. Click "Start Monitoring"
3. Allow camera access
4. Wait for the next minute mark (e.g., 2:30:00)
5. Recording will start automatically
6. Each minute, a new chunk is uploaded
7. Check `backend/db/` folder for saved videos
8. Click "Stop Monitoring" to end

#### Test Video Validation:
1. Open `http://localhost:3000/validate`
2. Upload a video file (preferably one recorded with monitoring)
3. Watch the progress bar
4. View validation result:
   - ✅ Validated (if recorded on facility camera)
   - ❌ Not Validated (if not found in blockchain)
5. Check chunk details

## Verification Checklist

### Backend Health Check:
- [ ] Backend server running on port 8000
- [ ] Blockchain connected (check console for ✅)
- [ ] Contract loaded successfully
- [ ] `db/` folder exists

### Frontend Health Check:
- [ ] Frontend running on port 3000
- [ ] Can access all routes (/, /monitor, /validate)
- [ ] No console errors
- [ ] Camera permission granted

### Integration Tests:

**Monitor Test:**
```
1. Navigate to /monitor
2. Click "Start Monitoring"
3. Allow camera access
4. Wait for recording to start
5. Let it record for 2+ minutes
6. Check backend console for upload logs
7. Verify files in backend/db/ folder
8. Stop monitoring
```

**Validate Test:**
```
1. Navigate to /validate
2. Upload one of the recorded videos from backend/db/
3. Wait for validation
4. Should show "Validated" verdict
5. Upload a random video file
6. Should show "Not Validated" verdict
```

## Common Issues & Solutions

### Issue: Camera not accessible
**Solution:**
- Grant camera permissions in browser
- Use HTTPS or localhost
- Check if camera is in use by another app
- Try different browser

### Issue: Backend not connecting to blockchain
**Solution:**
- Check RPC URL is correct
- Verify private key format (no 0x prefix in .env)
- Ensure wallet has Sepolia ETH
- Check Infura/Alchemy project limits

### Issue: CORS errors
**Solution:**
- Backend CORS is set to allow all origins for development
- Check if backend is running on port 8000
- Verify frontend is on port 3000

### Issue: Upload fails
**Solution:**
- Check backend console for errors
- Verify `db/` folder exists and is writable
- Ensure video format is supported (WebM, MP4)
- Check available disk space

### Issue: Validation always fails
**Solution:**
- Ensure you're uploading videos recorded with monitoring
- Check blockchain connection
- Verify contract has stored hashes
- Check console for hash comparison logs

## Directory Structure After Setup

```
AuthLens/
├── backend/
│   ├── venv/                  # Virtual environment
│   ├── .env                   # Environment variables
│   ├── main.py                # Running server
│   ├── db/                    # Video storage (created automatically)
│   │   └── cam_1_*.mp4       # Recorded chunks
│   └── video_chunks/          # Legacy storage
│
├── AuthLens-Frontend/
│   ├── node_modules/          # Dependencies
│   ├── public/
│   ├── src/
│   │   └── pages/
│   │       ├── Monitor.tsx    # Monitoring page
│   │       └── Validate.tsx   # Validation page
│   └── package.json
│
└── INTEGRATION.md             # Full documentation
```

## Next Steps

1. **Test with Multiple Cameras:**
   - Modify `camera_id` parameter in Monitor.tsx
   - Create different camera streams

2. **Deploy to Production:**
   - Set up proper environment variables
   - Configure CORS for your domain
   - Use HTTPS for frontend
   - Set up cloud storage

3. **Enhance Security:**
   - Add user authentication
   - Implement rate limiting
   - Add request validation
   - Use secrets manager

4. **Monitor Performance:**
   - Check upload speeds
   - Monitor blockchain gas costs
   - Track storage usage
   - Set up logging

## Support & Documentation

- **Full Integration Guide:** `INTEGRATION.md`
- **Backend API:** `http://localhost:8000/docs` (Swagger UI)
- **Frontend Routes:**
  - `/` - Home page
  - `/monitor` - Live monitoring
  - `/validate` - Video validation
  - `/live` - Original live stream demo

## Testing Commands

**Test Backend API:**
```bash
# Check health
curl http://localhost:8000/

# List video chunks
curl http://localhost:8000/api/video/list-chunks
```

**Build for Production:**
```bash
# Frontend
cd AuthLens-Frontend
npm run build

# Backend
cd backend
pip install gunicorn
gunicorn main:app
```

---

**🎉 You're all set! Start monitoring and validating videos with AuthLens!**
