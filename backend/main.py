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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
