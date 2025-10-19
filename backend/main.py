import hashlib
import json
import os
from datetime import datetime
from typing import Optional
from pathlib import Path
import shutil

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from web3 import Web3
import io

# Load environment variables
load_dotenv()

app = FastAPI(title="AuthLens Video Authentication API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
SEPOLIA_RPC_URL = os.getenv("SEPOLIA_RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS", "YOUR_DEPLOYED_CONTRACT_ADDRESS_HERE")

# Video storage directory
VIDEO_STORAGE_DIR = Path("video_chunks")
VIDEO_STORAGE_DIR.mkdir(exist_ok=True)

# --- WEB3 & CONTRACT SETUP ---
try:
    w3 = Web3(Web3.HTTPProvider(SEPOLIA_RPC_URL))
    if not w3.is_connected():
        print("❌ Error: Could not connect to the Ethereum node.")
        w3 = None
    else:
        account = w3.eth.account.from_key(PRIVATE_KEY)
        w3.eth.default_account = account.address
        print(f"✅ Connected to Ethereum. Using wallet: {account.address}")

        # Load the contract ABI
        abi_path = Path("VideoAuth.json")
        if abi_path.exists():
            with open(abi_path) as f:
                contract_json = json.load(f)
                contract_abi = contract_json["abi"]
            contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
        else:
            print("⚠️ Warning: VideoAuth.json not found. Contract interaction disabled.")
            contract = None
except Exception as e:
    print(f"❌ Error during setup: {e}")
    w3 = None
    contract = None


# --- PYDANTIC MODELS ---
class VideoChunkMetadata(BaseModel):
    start_time: str  # ISO format datetime string
    end_time: str    # ISO format datetime string


class VerifyRequest(BaseModel):
    video_hash: str  # Hex string of the hash


class VideoRangeRequest(BaseModel):
    start_datetime: str  # ISO format: "2025-10-19T14:30:00"
    end_datetime: str    # ISO format: "2025-10-19T14:35:00"


# --- HELPER FUNCTIONS ---
def hash_video_bytes(video_data: bytes) -> bytes:
    """Hash video data using SHA-256 and return raw 32-byte hash."""
    sha256 = hashlib.sha256()
    sha256.update(video_data)
    return sha256.digest()


def hash_video_file(filepath: Path) -> bytes:
    """Hash a video file using SHA-256."""
    BUF_SIZE = 65536  # 64kb chunks
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(BUF_SIZE):
            sha256.update(chunk)
    return sha256.digest()


def format_timestamp_for_filename(dt: datetime) -> str:
    """Format datetime to filename-safe string: YYYY-MM-DD_HH-MM-SS"""
    return dt.strftime("%Y-%m-%d_%H-%M-%S")


def store_hash_on_chain(video_hash_bytes: bytes) -> dict:
    """Store hash on blockchain and return result."""
    if not w3 or not contract:
        raise HTTPException(status_code=503, detail="Blockchain connection not available")
    
    try:
        # Check if the hash already exists
        exists, _ = contract.functions.verifyHash(video_hash_bytes).call()
        if exists:
            return {
                "success": True,
                "message": "Hash already exists on blockchain",
                "hash": f"0x{video_hash_bytes.hex()}",
                "already_exists": True
            }

        # Build the transaction
        tx = contract.functions.storeHash(video_hash_bytes).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 200000,
            'gasPrice': w3.eth.gas_price
        })

        # Sign and send the transaction
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        # Wait for confirmation
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
    """Verify if hash exists on blockchain."""
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
    """Get all video chunk files within the specified time range."""
    chunks = []
    
    for video_file in sorted(VIDEO_STORAGE_DIR.glob("*.mp4")):
        # Parse filename: chunk_START_to_END.mp4
        try:
            filename = video_file.stem  # Remove .mp4
            if not filename.startswith("chunk_"):
                continue
            
            # Extract timestamps from filename
            parts = filename.replace("chunk_", "").split("_to_")
            if len(parts) != 2:
                continue
            
            chunk_start = datetime.strptime(parts[0], "%Y-%m-%d_%H-%M-%S")
            chunk_end = datetime.strptime(parts[1], "%Y-%m-%d_%H-%M-%S")
            
            # Check if chunk overlaps with requested range
            if chunk_start <= end_dt and chunk_end >= start_dt:
                chunks.append(video_file)
        except Exception as e:
            print(f"Error parsing filename {video_file}: {e}")
            continue
    
    return chunks


# --- API ENDPOINTS ---
@app.get("/")
async def root():
    """Health check endpoint."""
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
    """
    Process a 1-minute video chunk:
    1. Save it locally with timestamp-based naming
    2. Hash the video
    3. Store the hash on blockchain
    """
    try:
        # Parse timestamps
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        
        # Create filename based on timestamps
        start_str = format_timestamp_for_filename(start_dt)
        end_str = format_timestamp_for_filename(end_dt)
        filename = f"chunk_{start_str}_to_{end_str}.mp4"
        filepath = VIDEO_STORAGE_DIR / filename
        
        # Save the video chunk
        video_data = await video.read()
        with open(filepath, "wb") as f:
            f.write(video_data)
        
        # Hash the video
        video_hash = hash_video_bytes(video_data)
        
        # Store hash on blockchain
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
        # Clean up file if something went wrong
        if filepath.exists():
            filepath.unlink()
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")


@app.post("/api/video/verify")
async def verify_video(video: UploadFile = File(...)):
    """
    Verify if a video exists on the blockchain by hashing it and checking the blockchain.
    """
    try:
        # Read and hash the video
        video_data = await video.read()
        video_hash = hash_video_bytes(video_data)
        
        # Verify on blockchain
        result = verify_hash_on_chain(video_hash)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verifying video: {str(e)}")


@app.post("/api/video/verify-hash")
async def verify_video_hash(request: VerifyRequest):
    """
    Verify if a hash exists on the blockchain.
    Accepts hash as hex string (with or without 0x prefix).
    """
    try:
        # Parse hex hash
        hash_str = request.video_hash.replace("0x", "")
        video_hash = bytes.fromhex(hash_str)
        
        if len(video_hash) != 32:
            raise HTTPException(status_code=400, detail="Hash must be 32 bytes (64 hex characters)")
        
        # Verify on blockchain
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
    """
    Retrieve and combine video chunks from a specified time range.
    Returns the combined video file.
    """
    try:
        # Parse timestamps
        start_dt = datetime.fromisoformat(start_datetime)
        end_dt = datetime.fromisoformat(end_datetime)
        
        # Get video chunks in range
        chunks = get_video_chunks_in_range(start_dt, end_dt)
        
        if not chunks:
            raise HTTPException(
                status_code=404,
                detail=f"No video chunks found for the time range {start_datetime} to {end_datetime}"
            )
        
        # If only one chunk, return it directly
        if len(chunks) == 1:
            return FileResponse(
                chunks[0],
                media_type="video/mp4",
                filename=f"video_{format_timestamp_for_filename(start_dt)}_to_{format_timestamp_for_filename(end_dt)}.mp4"
            )
        
        # For multiple chunks, we need to combine them
        # Note: This is a simple concatenation. For production, consider using ffmpeg
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
    """
    List all available video chunks, optionally filtered by time range.
    """
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
                
                # Apply filters if provided
                if start_datetime:
                    filter_start = datetime.fromisoformat(start_datetime)
                    if chunk_end < filter_start:
                        continue
                
                if end_datetime:
                    filter_end = datetime.fromisoformat(end_datetime)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
