# Video Download Feature - Implementation Summary

## Overview
Added a new "Download" page that allows users to download video recordings from a specific camera for a given time range. The system automatically merges multiple 1-minute video chunks using FFmpeg.

## Features Implemented

### Backend API Endpoint
**Endpoint:** `GET /api/monitor/download-range`

**Parameters:**
- `camera_id` (required): Camera identifier (e.g., cam_1, cam_2)
- `start_datetime` (required): Start time in ISO format (YYYY-MM-DDTHH:MM:SS)
- `end_datetime` (required): End time in ISO format (YYYY-MM-DDTHH:MM:SS)

**Functionality:**
1. Parses and validates the time range
2. Searches for all video chunks from the specified camera that overlap with the time range
3. If only one chunk is found, returns it directly
4. If multiple chunks are found, uses FFmpeg to merge them seamlessly
5. Returns a 404 error if no video exists for the specified time range
6. Automatically cleans up temporary files after download

**FFmpeg Integration:**
- Uses FFmpeg's concat demuxer for fast, lossless video merging
- Copies video streams without re-encoding (faster and maintains quality)
- Handles multiple minute-by-minute recordings automatically

### Frontend Page
**Route:** `/download`

**Components:**
- `Download.tsx` - Main page component
- `Download.css` - Styling

**Features:**
1. **Auto-populated Date:** Today's date is automatically set as the default
2. **Time Selection:** Separate date and time pickers for start and end times
3. **Camera Selection:** Text input for camera ID (cam_1, cam_2, etc.)
4. **Backend Connection Status:** Shows real-time connection status to backend
5. **Download Button:** Initiates the download process
6. **Error Handling:** 
   - Shows user-friendly error if no video exists
   - Validates that end time is after start time
   - Displays specific error messages for different failure scenarios
7. **Progress Feedback:** Shows status messages during download process
8. **Responsive Design:** Works on desktop and mobile devices

### Navigation
- Added "Download" link to the main navigation bar
- Icon: Download icon from lucide-react
- Located between "Live" and "Validate" links

## Files Modified

### Backend
1. **requirements.txt** - Added `ffmpeg-python` dependency
2. **main.py** - Added:
   - Import for ffmpeg
   - `/api/monitor/download-range` endpoint
   - `formatTimeForFilename()` helper function
   - `cleanup_temp_files()` helper function

### Frontend
1. **src/pages/Download.tsx** - New page component
2. **src/pages/Download.css** - New stylesheet
3. **src/Root.tsx** - Added Download route
4. **src/components/Navbar.tsx** - Added Download link to navigation

## Installation Instructions

### 1. Install Backend Dependencies
```bash
cd backend
pip install -r requirements.txt
```

**Note:** You also need FFmpeg installed on your system:
- **Windows:** Download from https://ffmpeg.org/ and add to PATH
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt-get install ffmpeg`

### 2. No Frontend Changes Required
The frontend already has all necessary dependencies (axios, react-router-dom, etc.)

## Usage

### For Users
1. Navigate to the "Download" page from the navigation bar
2. Enter the camera ID (e.g., cam_1)
3. Select the start date and time
4. Select the end date and time
5. Click "Download Video"
6. The system will:
   - Search for all video chunks in that time range
   - Merge them using FFmpeg
   - Download the merged video to your computer

### Error Messages
- **"No video recordings found..."** - No video was captured for that camera/time range
- **"End time must be after start time"** - Invalid time range selected
- **"Backend Disconnected"** - Cannot connect to the backend server

## Technical Details

### Video Chunk Format
Videos are stored as: `{camera_id}_{start_time}-{end_time}.mp4`
Example: `cam_1_2025-10-19_14-30-00-2025-10-19_14-31-00.mp4`

### FFmpeg Merging Process
1. Creates a temporary directory
2. Generates a concat file listing all video chunks
3. Uses FFmpeg concat demuxer to merge without re-encoding
4. Returns the merged video file
5. Cleans up temporary files in the background

### Time Range Matching
The system finds all video chunks where:
- Chunk start time ≤ requested end time
- Chunk end time ≥ requested start time

This ensures all overlapping recordings are included in the download.

## Future Enhancements (Optional)
- Add video preview before download
- Show total duration and file size before downloading
- Add option to trim exact start/end times from merged video
- Support batch downloads for multiple cameras
- Add progress bar for large downloads
- Video player with timeline showing available chunks
