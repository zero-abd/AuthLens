import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path
import shutil
import tempfile

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Body
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from web3 import Web3
import io

load_dotenv()

app = FastAPI(title="AuthLens Video Authentication API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # IMPORTANT: Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# IMPORTANT: Configure these environment variables before deployment

SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "YOUR_DEPLOYED_CONTRACT_ADDRESS_HERE")

VIDEO_STORAGE_DIR = Path("video_chunks")
VIDEO_STORAGE_DIR.mkdir(exist_ok=True)

DB_DIR = Path("db")
DB_DIR.mkdir(exist_ok=True)

try:
    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
    if not w3.is_connected():
        print("❌ Error: Could not connect to the Ethereum node.")
        w3 = None
    else:
        account = w3.eth.account.from_key(PRIVATE_KEY)
        w3.eth.default_account = account.address
        print(f"✅ Connected to Ethereum. Using wallet: {account.address}")

        abi_path = Path(__file__).parent / "VideoAuth.json"
        if abi_path.exists():
            with open(abi_path) as f:
                contract_json = json.load(f)
                contract_abi = contract_json["abi"]
            contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
            print(f"✅ Contract loaded at address: {CONTRACT_ADDRESS}")
        else:
            print(f"⚠️ Warning: VideoAuth.json not found at {abi_path}. Contract interaction disabled.")
            contract = None
except Exception as e:
    print(f"❌ Error during setup: {e}")
    w3 = None
    contract = None


class VideoChunkMetadata(BaseModel):
    start_time: str
    end_time: str


class VerifyRequest(BaseModel):
    video_hash: str


class VideoRangeRequest(BaseModel):
    start_datetime: str
    end_datetime: str


def hash_video_bytes(video_data: bytes) -> bytes:
    sha256 = hashlib.sha256()
    sha256.update(video_data)
    return sha256.digest()


def hash_video_file(filepath: Path) -> bytes:
    BUF_SIZE = 65536
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(BUF_SIZE):
            sha256.update(chunk)
    return sha256.digest()


def format_timestamp_for_filename(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d_%H-%M-%S")


def store_hash_on_chain(video_hash_bytes: bytes) -> dict:
    if not w3 or not contract:
        raise HTTPException(status_code=503, detail="Blockchain connection not available")
    
    try:
        exists, _ = contract.functions.verifyHash(video_hash_bytes).call()
        if exists:
            return {
                "success": True,
                "message": "Hash already exists on blockchain",
                "hash": f"0x{video_hash_bytes.hex()}",
                "already_exists": True
            }

        tx = contract.functions.storeHash(video_hash_bytes).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        return {
            "success": True,
            "message": "Hash stored successfully",
            "hash": f"0x{video_hash_bytes.hex()}",
            "transaction_hash": tx_receipt.transactionHash.hex(),
            "already_exists": False
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Blockchain error: {str(e)}")


def verify_hash_on_chain(video_hash_bytes: bytes) -> dict:
    if not w3 or not contract:
        raise HTTPException(status_code=503, detail="Blockchain connection not available")
    
    try:
        exists, uploader_address = contract.functions.verifyHash(video_hash_bytes).call()
        
        return {
            "verified": exists,
            "hash": f"0x{video_hash_bytes.hex()}",
            "uploader": uploader_address if exists else None,
            "message": "Video is authentic" if exists else "Video not found on blockchain"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Blockchain error: {str(e)}")


def get_video_chunks_in_range(start_dt: datetime, end_dt: datetime) -> list[Path]:
    chunks = []
    
    for video_file in sorted(VIDEO_STORAGE_DIR.glob("*.mp4")):
        try:
            filename = video_file.stem
            if not filename.startswith("chunk_"):
                continue
            
            parts = filename.replace("chunk_", "").split("_to_")
            if len(parts) != 2:
                continue
            
            chunk_start = datetime.strptime(parts[0], "%Y-%m-%d_%H-%M-%S")
            chunk_end = datetime.strptime(parts[1], "%Y-%m-%d_%H-%M-%S")
            
            if chunk_start <= end_dt and chunk_end >= start_dt:
                chunks.append(video_file)
        except Exception as e:
            print(f"Error parsing filename {video_file}: {e}")
            continue
    
    return chunks


@app.get("/")
async def root():
    return {
        "message": "AuthLens Video Authentication API",
        "blockchain_connected": w3 is not None and w3.is_connected(),
        "contract_loaded": contract is not None
    }


@app.post("/api/video/process-chunk")
async def process_video_chunk(
    video: UploadFile = File(...),
    start_time: str = Query(..., description="ISO format datetime: 2025-10-19T14:30:00"),
    end_time: str = Query(..., description="ISO format datetime: 2025-10-19T14:31:00")
):
    try:
        start_dt = datetime.fromisoformat(start_time).replace(microsecond=0)
        end_dt = datetime.fromisoformat(end_time).replace(microsecond=0)
        
        start_str = format_timestamp_for_filename(start_dt)
        end_str = format_timestamp_for_filename(end_dt)
        filename = f"chunk_{start_str}_to_{end_str}.mp4"
        filepath = VIDEO_STORAGE_DIR / filename
        
        video_data = await video.read()
        with open(filepath, "wb") as f:
            f.write(video_data)
        
        video_hash = hash_video_bytes(video_data)
        
        blockchain_result = store_hash_on_chain(video_hash)
        
        return {
            "success": True,
            "message": "Video chunk processed successfully",
            "filename": filename,
            "start_time": start_time,
            "end_time": end_time,
            "file_size_bytes": len(video_data),
            "blockchain": blockchain_result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {str(e)}")
    except Exception as e:
        if filepath.exists():
            filepath.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")


@app.post("/api/video/verify")
async def verify_video(video: UploadFile = File(...)):
    try:
        video_data = await video.read()
        video_hash = hash_video_bytes(video_data)
        
        result = verify_hash_on_chain(video_hash)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verifying video: {str(e)}")


@app.post("/api/video/verify-hash")
async def verify_video_hash(request: VerifyRequest):
    try:
        hash_str = request.video_hash.replace("0x", "")
        video_hash = bytes.fromhex(hash_str)
        
        if len(video_hash) != 32:
            raise HTTPException(status_code=400, detail="Hash must be 32 bytes (64 hex characters)")
        
        result = verify_hash_on_chain(video_hash)
        
        return result
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid hex hash format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verifying hash: {str(e)}")


@app.get("/api/video/retrieve")
async def retrieve_video_range(
    start_datetime: str = Query(..., description="ISO format: 2025-10-19T14:30:00"),
    end_datetime: str = Query(..., description="ISO format: 2025-10-19T14:35:00")
):
    try:
        start_dt = datetime.fromisoformat(start_datetime).replace(microsecond=0)
        end_dt = datetime.fromisoformat(end_datetime).replace(microsecond=0)
        
        chunks = get_video_chunks_in_range(start_dt, end_dt)
        
        if not chunks:
            raise HTTPException(
                status_code=404,
                detail=f"No video chunks found for the time range {start_datetime} to {end_datetime}"
            )
        
        if len(chunks) == 1:
            return FileResponse(
                chunks[0],
                media_type="video/mp4",
                filename=f"video_{format_timestamp_for_filename(start_dt)}_to_{format_timestamp_for_filename(end_dt)}.mp4"
            )
        
        # IMPORTANT: Simple concatenation - consider using ffmpeg for production
        combined_data = io.BytesIO()
        for chunk in chunks:
            with open(chunk, "rb") as f:
                combined_data.write(f.read())
        
        combined_data.seek(0)
        
        return StreamingResponse(
            combined_data,
            media_type="video/mp4",
            headers={
                "Content-Disposition": f"attachment; filename=video_{format_timestamp_for_filename(start_dt)}_to_{format_timestamp_for_filename(end_dt)}.mp4"
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving video: {str(e)}")


@app.get("/api/video/list-chunks")
async def list_video_chunks(
    start_datetime: Optional[str] = Query(None, description="Filter from this datetime"),
    end_datetime: Optional[str] = Query(None, description="Filter to this datetime")
):
    try:
        all_chunks = []
        
        for video_file in sorted(VIDEO_STORAGE_DIR.glob("*.mp4")):
            try:
                filename = video_file.stem
                if not filename.startswith("chunk_"):
                    continue
                
                parts = filename.replace("chunk_", "").split("_to_")
                if len(parts) != 2:
                    continue
                
                chunk_start = datetime.strptime(parts[0], "%Y-%m-%d_%H-%M-%S")
                chunk_end = datetime.strptime(parts[1], "%Y-%m-%d_%H-%M-%S")
                
                if start_datetime:
                    filter_start = datetime.fromisoformat(start_datetime).replace(microsecond=0)
                    if chunk_end < filter_start:
                        continue
                
                if end_datetime:
                    filter_end = datetime.fromisoformat(end_datetime).replace(microsecond=0)
                    if chunk_start > filter_end:
                        continue
                
                all_chunks.append({
                    "filename": video_file.name,
                    "start_time": chunk_start.isoformat(),
                    "end_time": chunk_end.isoformat(),
                    "size_bytes": video_file.stat().st_size
                })
            except Exception as e:
                print(f"Error processing {video_file}: {e}")
                continue
        
        return {
            "chunks": all_chunks,
            "total_chunks": len(all_chunks)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing chunks: {str(e)}")


@app.post("/api/monitor/upload-chunk")
async def upload_monitoring_chunk(
    video: UploadFile = File(...),
    camera_id: str = Query(..., description="Camera identifier (e.g., cam_1)"),
    start_time: str = Query(..., description="Start time in format YYYY-MM-DD_HH-MM-00"),
    end_time: str = Query(..., description="End time in format YYYY-MM-DD_HH-MM-00")
):
    """
    Upload a 1-minute video chunk from monitoring camera.
    Stores in db/ folder with naming: cam_1_start-date_time-end_date_time.mp4
    """
    try:
        # Validate camera_id
        if not camera_id or not camera_id.startswith("cam_"):
            raise HTTPException(status_code=400, detail="Invalid camera_id format. Use cam_N")
        
        # Parse and validate timestamps
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d_%H-%M-%S")
            end_dt = datetime.strptime(end_time, "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format. Use YYYY-MM-DD_HH-MM-SS")
        
        # Ensure times end at 00 seconds
        if start_dt.second != 0 or end_dt.second != 0:
            raise HTTPException(status_code=400, detail="Times must end at 00 seconds")
        
        # Validate it's approximately 1 minute
        duration = (end_dt - start_dt).total_seconds()
        if duration < 50 or duration > 70:
            raise HTTPException(status_code=400, detail="Chunk duration must be approximately 60 seconds")
        
        # Create filename
        filename = f"{camera_id}_{start_time}-{end_time}.mp4"
        filepath = DB_DIR / filename
        
        # Save video chunk
        video_data = await video.read()
        with open(filepath, "wb") as f:
            f.write(video_data)
        
        # Calculate hash and store on blockchain
        video_hash = hash_video_bytes(video_data)
        blockchain_result = store_hash_on_chain(video_hash)
        
        return {
            "success": True,
            "message": "Video chunk uploaded and stored successfully",
            "filename": filename,
            "camera_id": camera_id,
            "start_time": start_time,
            "end_time": end_time,
            "file_size_bytes": len(video_data),
            "video_hash": f"0x{video_hash.hex()}",
            "blockchain": blockchain_result,
            "stored_in": str(filepath)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if 'filepath' in locals() and filepath.exists():
            filepath.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video chunk: {str(e)}")


def split_video_into_minute_chunks(video_path: Path) -> List[tuple[Path, int, int]]:
    """
    Split a video file into 1-minute chunks.
    Returns list of (chunk_path, start_second, end_second)
    
    NOTE: This is a simplified version. In production, use ffmpeg for proper video splitting.
    For now, we'll treat each minute as a separate logical chunk without actual splitting.
    """
    # Get video file size to estimate duration (rough estimate)
    file_size = video_path.stat().st_size
    
    # Rough estimate: ~1MB per second of video at medium quality
    # This is very approximate and should be replaced with actual video analysis
    estimated_duration_seconds = file_size / (1024 * 1024)  # Very rough
    
    chunks = []
    chunk_duration = 60  # 1 minute
    
    # For now, we'll use a simple approach: read the entire file and logically divide it
    # In production, use ffmpeg or similar to actually split the video
    num_chunks = max(1, int(estimated_duration_seconds / chunk_duration))
    
    temp_dir = Path(tempfile.mkdtemp())
    
    for i in range(num_chunks):
        start_sec = i * chunk_duration
        end_sec = (i + 1) * chunk_duration
        
        # For now, we create a reference to the original file
        # In production, actually split using ffmpeg
        chunk_path = temp_dir / f"chunk_{i}.mp4"
        shutil.copy(video_path, chunk_path)  # Simplified - copies whole file
        
        chunks.append((chunk_path, start_sec, end_sec))
    
    return chunks


@app.post("/api/validate/upload")
async def validate_uploaded_video(
    video: UploadFile = File(...)
):
    """
    Validate an uploaded video by:
    1. Splitting into 1-minute chunks
    2. Hashing each chunk
    3. Checking if hash exists in blockchain (recorded on facility cam)
    4. Returning verification result
    5. Cleaning up uploaded file
    """
    temp_video_path = None
    chunk_paths = []
    
    try:
        # Save uploaded video temporarily
        temp_video_path = Path(tempfile.gettempdir()) / f"validate_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{video.filename}"
        video_data = await video.read()
        
        with open(temp_video_path, "wb") as f:
            f.write(video_data)
        
        # Get total file size for progress calculation
        total_size = len(video_data)
        
        # Split video into minute chunks (simplified)
        # In production, use ffmpeg to actually split the video
        # For now, we'll process the whole video as chunks
        
        # Estimate number of chunks (rough)
        estimated_chunks = max(1, int(total_size / (1024 * 1024 * 10)))  # Assume ~10MB per minute
        
        results = []
        validated_count = 0
        not_validated_count = 0
        
        # For simplicity, we'll treat the video as a single chunk or multiple logical chunks
        # Check if entire video or chunks exist in blockchain
        
        # Process as single chunk for now
        video_hash = hash_video_bytes(video_data)
        verification = verify_hash_on_chain(video_hash)
        
        chunk_result = {
            "chunk_index": 0,
            "hash": f"0x{video_hash.hex()}",
            "verified": verification["verified"],
            "status": "validated" if verification["verified"] else "not_validated"
        }
        
        results.append(chunk_result)
        
        if verification["verified"]:
            validated_count += 1
        else:
            not_validated_count += 1
        
        # Determine overall verdict
        if validated_count > 0 and not_validated_count == 0:
            verdict = "validated"
            message = "Video is validated - recorded on a facility camera"
        elif validated_count == 0:
            verdict = "not_validated"
            message = "Video is not validated - not recorded on a facility camera"
        else:
            verdict = "partially_validated"
            message = f"Video is partially validated - {validated_count}/{len(results)} chunks validated"
        
        return {
            "success": True,
            "verdict": verdict,
            "message": message,
            "total_chunks": len(results),
            "validated_chunks": validated_count,
            "not_validated_chunks": not_validated_count,
            "chunk_details": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating video: {str(e)}")
    
    finally:
        # Clean up temporary files
        if temp_video_path and temp_video_path.exists():
            try:
                temp_video_path.unlink()
            except Exception as e:
                print(f"Error deleting temp file: {e}")
        
        # Clean up chunk paths
        for chunk_path in chunk_paths:
            try:
                if chunk_path.exists():
                    chunk_path.unlink()
            except Exception as e:
                print(f"Error deleting chunk file: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
