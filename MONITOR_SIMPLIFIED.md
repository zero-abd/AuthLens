# Monitor Page - Clean & Simple Version

## What Changed

### ❌ REMOVED:
- All "Start/Stop Camera" separate buttons
- "Send Frames" toggle/mode
- Ngrok URL input field  
- Frames captured counter
- "/receiver" streaming references
- Complex multi-step UI flow
- Unnecessary state management

### ✅ SIMPLIFIED TO:

**Just 2 States:**
1. **Not Monitoring** - Shows overlay, ready to start
2. **Monitoring** - Camera active, recording chunks

**Just 1 Button:**
- **"Start Monitoring"** - Starts camera instantly + begins recording
- **"Stop Monitoring"** - Stops immediately, discards incomplete chunk

## How It Works Now

### Start Monitoring Flow:
```
User clicks "Start Monitoring"
  ↓
Camera activates IMMEDIATELY
  ↓
Video preview shows live feed
  ↓
System waits for next minute mark (e.g., 2:35:00)
  ↓
Starts recording 60-second chunk
  ↓
Uploads to backend at localhost:8000
  ↓
Minutes counter: +1
  ↓
Repeats every minute automatically
```

### Stop Monitoring Flow:
```
User clicks "Stop Monitoring"
  ↓
Cancels next scheduled recording
  ↓
Stops current recording (if active)
  ↓
DISCARDS incomplete chunk (doesn't upload)
  ↓
Stops camera feed
  ↓
Status: "Monitoring stopped"
```

## UI Components

### Left Panel - Video Preview:
- Live camera feed when monitoring
- Overlay with message when stopped
- **Single button**: Start/Stop Monitoring

### Right Panel - Status:
1. **Backend API** - Shows connection to localhost:8000
2. **Monitoring** - Shows "Live" or "Stopped"
3. **Minutes Captured** - Count of uploaded chunks
4. **Current Time** - Clock display

### Status Messages:
- "Ready to start monitoring" (idle)
- "Starting camera..." (activating)
- "Waiting for [time]..." (waiting for minute mark)
- "Recording: [start] - [end]" (active recording)
- "Next chunk at [time]" (between chunks)
- "Stopping monitoring..." (stopping)
- "Monitoring stopped" (stopped)

## Key Behaviors

### ✅ Instant Camera Start
- No separate "Start Camera" button needed
- Camera activates when monitoring starts
- No delay, no extra clicks

### ✅ Clean Stop
- Stops immediately when requested
- Does NOT upload incomplete chunks (< 60 seconds)
- Properly cleans up all resources

### ✅ Automatic Sync
- Always starts recording at :00 seconds
- Always records full 60-second chunks
- Always uploads complete chunks only

### ✅ Backend Integration
- Connects to localhost:8000
- Checks connection every 10 seconds
- Shows connection status in real-time

## Technical Details

### Chunk Naming:
```
cam_1_2025-10-19_14-30-00-2025-10-19_14-31-00.mp4
```

### Upload Endpoint:
```
POST http://localhost:8000/api/monitor/upload-chunk
```

### Stop Behavior:
```javascript
// When stopping, override onstop to prevent upload
mediaRecorderRef.current.onstop = () => {
  console.log("Recording stopped without upload (incomplete chunk)");
};
mediaRecorderRef.current.stop();
```

## What You Get

**Before (Complex):**
- Start Camera button
- Start Recording button
- Stop Recording button
- Stop Camera button
- Stream Mode toggle
- Ngrok URL field
- Frames counter
- Multiple status indicators

**After (Simple):**
- **Start Monitoring** button → Does everything
- **Stop Monitoring** button → Stops cleanly
- Clean status panel
- Minutes captured counter
- That's it!

---

## Summary

The Monitor page is now **dead simple**:
- **One button to start** (camera + recording)
- **One button to stop** (clean shutdown)
- **Clear status display**
- **No incomplete chunks uploaded**

No more confusion, no more unnecessary UI elements. Just start, record, stop. 🎯
