from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
from vidgear.gears import CamGear
import cv2
import uvicorn
import time
import socket

app = FastAPI()

def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"  # Fallback to localhost

# Initialize camera with error handling
try:
    # Configure camera for 280p resolution and 30 fps
    stream = CamGear(
        source=0,
        logging=True,
        # Set resolution to 480x280 (280p)
        CAP_PROP_FRAME_WIDTH=480,
        CAP_PROP_FRAME_HEIGHT=280,
        # Set frame rate to 30 fps
        CAP_PROP_FPS=30
    ).start()
    print("Camera initialized successfully!")
    print("Resolution: 480x280 (280p)")
    print("Frame rate: 30 fps")
except Exception as e:
    print(f"Failed to initialize camera: {e}")
    print("Make sure your camera is not being used by another application.")
    stream = None

def generate():
    if stream is None:
        print("ERROR: Camera stream not available - generating error frame")
        # Generate a simple error frame
        error_frame = cv2.imread("error_frame.jpg") if cv2.imread("error_frame.jpg") is not None else None
        if error_frame is None:
            # Create a simple error frame programmatically
            error_frame = cv2.zeros((280, 480, 3), dtype=cv2.uint8)
            cv2.putText(error_frame, "Camera Not Available", (50, 140), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        while True:
            _, jpeg = cv2.imencode(".jpg", error_frame)
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
            time.sleep(0.1)  # Slow down error frame updates
    
    target_fps = 30
    frame_time = 1.0 / target_fps
    last_time = time.time()
    frame_count = 0
    
    print("Starting video stream generation...")
    
    while True:
        current_time = time.time()
        
        frame = stream.read()
        if frame is None:
            print("ERROR: Failed to read frame from camera")
            break
        
        frame_count += 1
        if frame_count % 100 == 0:  # Print status every 100 frames
            print(f"Streaming frame {frame_count}")
        
        # Resize frame to ensure 280p resolution (480x280)
        frame_resized = cv2.resize(frame, (480, 280), interpolation=cv2.INTER_LINEAR)
        
        # Frame rate control - skip frames if we're ahead of schedule
        elapsed = current_time - last_time
        if elapsed < frame_time:
            time.sleep(frame_time - elapsed)
        
        last_time = time.time()
        
        try:
            _, jpeg = cv2.imencode(".jpg", frame_resized)
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        except Exception as e:
            print(f"ERROR encoding frame: {e}")
            break


@app.get("/")
def index():
    """Serve the main page with video stream"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Live Camera Stream</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f0f0f0;
                text-align: center;
            }
            h1 {
                color: #333;
                margin-bottom: 20px;
            }
            .video-container {
                display: inline-block;
                border: 2px solid #333;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            }
            img {
                display: block;
                max-width: 100%;
                height: auto;
            }
            .status {
                margin-top: 20px;
                padding: 10px;
                background-color: #e8f5e8;
                border-radius: 5px;
                color: #2d5a2d;
            }
            .error {
                background-color: #ffe8e8;
                color: #5a2d2d;
            }
        </style>
    </head>
    <body>
        <h1>Live Camera Stream</h1>
        <div class="video-container">
            <img src="/video" alt="Live Camera Feed" />
        </div>
        <div class="status" id="status">
            Camera stream loading...
        </div>
        
        <script>
            const img = document.querySelector('img');
            const status = document.getElementById('status');
            
            img.onload = function() {
                status.textContent = 'Camera stream active ✓';
                status.className = 'status';
            };
            
            img.onerror = function() {
                status.textContent = 'Error: Camera stream failed to load. Check if camera is available.';
                status.className = 'status error';
            };
            
            // Check if image loads within 5 seconds
            setTimeout(() => {
                if (status.textContent === 'Camera stream loading...') {
                    status.textContent = 'Error: Camera stream timeout. Check camera permissions and availability.';
                    status.className = 'status error';
                }
            }, 5000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/video")
def video_feed():
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    local_ip = get_local_ip()
    print("Starting FastAPI server...")
    print(f"Camera stream will be available at:")
    print(f"  Local: http://localhost:8001/")
    print(f"  Network: http://{local_ip}:8001/")
    print(f"Direct video stream: http://localhost:8001/video")
    print(f"Camera status: {'✓ Available' if stream is not None else '✗ Not Available'}")
    uvicorn.run(app, host="0.0.0.0", port=8001)

