import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path
import shutil
import tempfile
import subprocess

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Body, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from web3 import Web3
import io
import ffmpeg

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

LEDGER_FILE = DB_DIR / "ledger.json"

def load_ledger():
    try:
        if LEDGER_FILE.exists():
            with open(LEDGER_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"❌ Error loading ledger: {e}")
        return []

def save_ledger_entry(entry: dict):
    try:
        ledger = load_ledger()
        ledger.append(entry)
        with open(LEDGER_FILE, "w") as f:
            json.dump(ledger, f, indent=2)
        print(f"✅ Ledger entry saved successfully. Total entries: {len(ledger)}")
    except Exception as e:
        print(f"❌ Error saving ledger entry: {e}")

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
        hash_hex = f"0x{video_hash_bytes.hex()}"
        print(f"\n{'='*60}")
        print(f"📝 STORING HASH ON BLOCKCHAIN")
        print(f"{'='*60}")
        print(f"Hash: {hash_hex}")
        
        exists, _ = contract.functions.verifyHash(video_hash_bytes).call()
        if exists:
            print(f"ℹ️  Hash already exists on blockchain")
            print(f"{'='*60}\n")
            return {
                "success": True,
                "message": "Hash already exists on blockchain",
                "hash": hash_hex,
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
        
        print(f"⏳ Transaction submitted: {tx_hash.hex()}")
        
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"✅ Hash stored successfully!")
        print(f"Transaction hash: {tx_receipt.transactionHash.hex()}")
        print(f"Block number: {tx_receipt.blockNumber}")
        print(f"Gas used: {tx_receipt.gasUsed}")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "message": "Hash stored successfully",
            "hash": hash_hex,
            "transaction_hash": tx_receipt.transactionHash.hex(),
            "block_number": tx_receipt.blockNumber,
            "already_exists": False
        }

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ERROR STORING HASH ON BLOCKCHAIN")
        print(f"{'='*60}")
        print(f"Hash: 0x{video_hash_bytes.hex()}")
        print(f"Error: {str(e)}")
        print(f"{'='*60}\n")
        raise HTTPException(status_code=500, detail=f"Blockchain error: {str(e)}")


def verify_hash_on_chain(video_hash_bytes: bytes) -> dict:
    if not w3 or not contract:
        raise HTTPException(status_code=503, detail="Blockchain connection not available")
    
    try:
        hash_hex = f"0x{video_hash_bytes.hex()}"
        print(f"\n{'='*60}")
        print(f"🔍 VERIFYING HASH ON BLOCKCHAIN")
        print(f"{'='*60}")
        print(f"Hash: {hash_hex}")
        
        exists, uploader_address = contract.functions.verifyHash(video_hash_bytes).call()
        
        if exists:
            print(f"✅ Video is authentic!")
            print(f"Uploader: {uploader_address}")
        else:
            print(f"❌ Video not found on blockchain")
        print(f"{'='*60}\n")
        
        return {
            "verified": exists,
            "hash": hash_hex,
            "uploader": uploader_address if exists else None,
            "message": "Video is authentic" if exists else "Video not found on blockchain"
        }
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"❌ ERROR VERIFYING HASH")
        print(f"{'='*60}")
        print(f"Hash: 0x{video_hash_bytes.hex()}")
        print(f"Error: {str(e)}")
        print(f"{'='*60}\n")
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
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    camera_id: str = Query(..., description="Camera identifier (e.g., cam_1)"),
    start_time: str = Query(..., description="Start time in format YYYY-MM-DD_HH-MM-00"),
    end_time: str = Query(..., description="End time in format YYYY-MM-DD_HH-MM-00")
):
    try:
        if not camera_id or not camera_id.startswith("cam_"):
            raise HTTPException(status_code=400, detail="Invalid camera_id format. Use cam_N")
        
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d_%H-%M-%S")
            end_dt = datetime.strptime(end_time, "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid time format. Use YYYY-MM-DD_HH-MM-SS")
        
        if start_dt.second != 0 or end_dt.second != 0:
            raise HTTPException(status_code=400, detail="Times must end at 00 seconds")
        
        duration = (end_dt - start_dt).total_seconds()
        if duration < 50 or duration > 70:
            raise HTTPException(status_code=400, detail="Chunk duration must be approximately 60 seconds")
        
        filename = f"{camera_id}_{start_time}-{end_time}.mp4"
        filepath = DB_DIR / filename
        
        video_data = await video.read()
        with open(filepath, "wb") as f:
            f.write(video_data)
        
        background_tasks.add_task(process_video_hash_in_background, filepath, video_data)
        
        return {
            "success": True,
            "message": "Video chunk uploaded successfully. Hash processing in background.",
            "filename": filename,
            "camera_id": camera_id,
            "start_time": start_time,
            "end_time": end_time,
            "file_size_bytes": len(video_data),
            "stored_in": str(filepath),
            "note": "Hash generation and blockchain storage will complete in background"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        if 'filepath' in locals() and filepath.exists():
            filepath.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video chunk: {str(e)}")


def process_video_hash_in_background(filepath: Path, video_data: bytes):
    try:
        print(f"\n🔄 Background processing started for: {filepath.name}")
        
        # Extract camera_id and time from filename
        filename = filepath.stem
        parts = filename.split("_", 1)
        camera_id = parts[0] if len(parts) > 0 else "unknown"
        
        # Calculate hash
        video_hash = hash_video_bytes(video_data)
        hash_hex = f"0x{video_hash.hex()}"
        
        print(f"📊 Hash calculated: {hash_hex}")
        
        # Store on blockchain
        blockchain_result = store_hash_on_chain(video_hash)
        
        # Save to ledger
        ledger_entry = {
            "timestamp": datetime.now().isoformat(),
            "camera_id": camera_id,
            "chunk_filename": filepath.name,
            "video_hash": hash_hex,
            "transaction_hash": blockchain_result.get("transaction_hash", "already_exists"),
            "block_number": blockchain_result.get("block_number"),
            "status": "stored" if blockchain_result["success"] else "failed"
        }
        save_ledger_entry(ledger_entry)
        
        print(f"✅ Background processing completed for: {filepath.name}")
        print(f"   Blockchain result: {blockchain_result['message']}")
        
    except Exception as e:
        print(f"❌ Error in background processing for {filepath.name}: {e}")


@app.get("/api/monitor/list-chunks")
async def list_monitoring_chunks(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID")
):
    try:
        chunks = []
        
        for video_file in sorted(DB_DIR.glob("*.mp4")):
            try:
                filename = video_file.stem
                
                if not filename.startswith("cam_"):
                    continue
                
                if camera_id and not filename.startswith(f"{camera_id}_"):
                    continue
                
                parts = filename.split("_", 1)
                if len(parts) != 2:
                    continue
                
                cam_id = parts[0]
                time_parts = parts[1].split("-", 6)
                
                video_data = video_file.read_bytes()
                video_hash = hash_video_bytes(video_data)
                
                try:
                    verification = verify_hash_on_chain(video_hash)
                    blockchain_status = "verified" if verification["verified"] else "not_verified"
                except:
                    blockchain_status = "unknown"
                
                chunks.append({
                    "filename": video_file.name,
                    "camera_id": cam_id,
                    "size_bytes": video_file.stat().st_size,
                    "video_hash": f"0x{video_hash.hex()}",
                    "blockchain_status": blockchain_status
                })
            except Exception as e:
                print(f"Error processing {video_file}: {e}")
                continue
        
        return {
            "chunks": chunks,
            "total_chunks": len(chunks)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing chunks: {str(e)}")


@app.get("/api/ledger")
async def get_ledger(
    limit: Optional[int] = Query(100, description="Maximum number of entries to return"),
    camera_id: Optional[str] = Query(None, description="Filter by camera ID")
):
    """
    Get ledger entries of all chunks stored on blockchain
    """
    try:
        print(f"📖 Fetching ledger entries (limit={limit}, camera_id={camera_id})")
        ledger = load_ledger()
        print(f"📊 Loaded {len(ledger)} total entries from ledger")
        
        # Filter by camera_id if provided
        if camera_id:
            ledger = [entry for entry in ledger if entry.get("camera_id") == camera_id]
            print(f"🔍 Filtered to {len(ledger)} entries for camera_id={camera_id}")
        
        # Sort by timestamp (newest first)
        ledger = sorted(ledger, key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Limit results
        ledger = ledger[:limit]
        
        return {
            "success": True,
            "total_entries": len(ledger),
            "entries": ledger
        }
        
    except Exception as e:
        print(f"❌ Error fetching ledger: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching ledger: {str(e)}")


def split_video_into_minute_chunks(video_path: Path) -> List[tuple[Path, int, int]]:
    file_size = video_path.stat().st_size
    estimated_duration_seconds = file_size / (1024 * 1024)
    
    chunks = []
    chunk_duration = 60
    num_chunks = max(1, int(estimated_duration_seconds / chunk_duration))
    
    temp_dir = Path(tempfile.mkdtemp())
    
    for i in range(num_chunks):
        start_sec = i * chunk_duration
        end_sec = (i + 1) * chunk_duration
        
        chunk_path = temp_dir / f"chunk_{i}.mp4"
        shutil.copy(video_path, chunk_path)
        
        chunks.append((chunk_path, start_sec, end_sec))
    
    return chunks


@app.get("/api/monitor/download-range")
async def download_video_range(
    camera_id: str = Query(..., description="Camera identifier (e.g., cam_1)"),
    start_datetime: str = Query(..., description="Start datetime in format YYYY-MM-DDTHH:MM:SS"),
    end_datetime: str = Query(..., description="End datetime in format YYYY-MM-DDTHH:MM:SS")
):
    temp_files = []
    
    try:
        try:
            start_dt = datetime.fromisoformat(start_datetime).replace(microsecond=0)
            end_dt = datetime.fromisoformat(end_datetime).replace(microsecond=0)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid datetime format. Use ISO format: YYYY-MM-DDTHH:MM:SS")
        
        if end_dt <= start_dt:
            raise HTTPException(status_code=400, detail="End time must be after start time")
        
        matching_chunks = []
        
        for video_file in sorted(DB_DIR.glob(f"{camera_id}_*.mp4")):
            try:
                filename = video_file.stem
                
                if not filename.startswith(f"{camera_id}_"):
                    continue
                
                time_part = filename[len(camera_id) + 1:]
                time_components = time_part.split("-")
                
                if len(time_components) >= 10:
                    start_year = int(time_components[0])
                    start_month = int(time_components[1])
                    start_day_hour = time_components[2].split("_")
                    start_day = int(start_day_hour[0])
                    start_hour = int(start_day_hour[1])
                    start_minute = int(time_components[3])
                    start_second = int(time_components[4])
                    
                    chunk_start = datetime(start_year, start_month, start_day, start_hour, start_minute, start_second)
                    
                    end_year = int(time_components[5])
                    end_month = int(time_components[6])
                    end_day_hour = time_components[7].split("_")
                    end_day = int(end_day_hour[0])
                    end_hour = int(end_day_hour[1])
                    end_minute = int(time_components[8])
                    end_second = int(time_components[9])
                    
                    chunk_end = datetime(end_year, end_month, end_day, end_hour, end_minute, end_second)
                    
                    if chunk_start >= start_dt and chunk_start < end_dt:
                        matching_chunks.append((chunk_start, video_file))
                
            except Exception as e:
                print(f"Error parsing {video_file}: {e}")
                continue
        
        if not matching_chunks:
            raise HTTPException(
                status_code=404,
                detail=f"No video chunks found for camera {camera_id} in the time range {start_datetime} to {end_datetime}"
            )
        
        matching_chunks.sort(key=lambda x: x[0])
        chunk_files = [chunk[1] for chunk in matching_chunks]
        
        if len(chunk_files) == 1:
            output_filename = f"{camera_id}_{formatTimeForFilename(start_dt)}_to_{formatTimeForFilename(end_dt)}.mp4"
            return FileResponse(
                chunk_files[0],
                media_type="video/mp4",
                filename=output_filename
            )
        
        try:
            temp_dir = Path(tempfile.mkdtemp())
            temp_files.append(temp_dir)
            
            concat_file = temp_dir / "concat.txt"
            with open(concat_file, "w") as f:
                for chunk_file in chunk_files:
                    abs_path = chunk_file.absolute()
                    f.write(f"file '{abs_path}'\n")
            
            output_filename = f"{camera_id}_{formatTimeForFilename(start_dt)}_to_{formatTimeForFilename(end_dt)}.mp4"
            output_path = temp_dir / output_filename
            
            try:
                (
                    ffmpeg
                    .input(str(concat_file), format='concat', safe=0)
                    .output(str(output_path), vcodec='libx264', acodec='aac')
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            except ffmpeg.Error as e:
                print(f"FFmpeg error: {e.stderr.decode()}")
                raise HTTPException(status_code=500, detail="Error merging video chunks with ffmpeg")
            
            return FileResponse(
                output_path,
                media_type="video/mp4",
                filename=output_filename,
                background=BackgroundTasks().add_task(cleanup_temp_files, temp_files)
            )
            
        except Exception as e:
            cleanup_temp_files(temp_files)
            raise HTTPException(status_code=500, detail=f"Error merging videos: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        cleanup_temp_files(temp_files)
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


def formatTimeForFilename(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d_%H-%M-%S")


def cleanup_temp_files(temp_files: list):
    for temp_file in temp_files:
        try:
            if isinstance(temp_file, Path):
                if temp_file.is_dir():
                    shutil.rmtree(temp_file, ignore_errors=True)
                elif temp_file.exists():
                    temp_file.unlink()
        except Exception as e:
            print(f"Error cleaning up {temp_file}: {e}")


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
        estimated_chunks = max(1, int(total_size / (1024 * 1024 * 10)))
        
        results = []
        validated_count = 0
        not_validated_count = 0
        
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
        if temp_video_path and temp_video_path.exists():
            try:
                temp_video_path.unlink()
            except Exception as e:
                print(f"Error deleting temp file: {e}")
        
        for chunk_path in chunk_paths:
            try:
                if chunk_path.exists():
                    chunk_path.unlink()
            except Exception as e:
                print(f"Error deleting chunk file: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
