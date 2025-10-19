"""
Simple test client for AuthLens API
Usage: python test_client.py
"""

import requests
from datetime import datetime, timedelta
import json

BASE_URL = "http://localhost:8000"

def test_health():
    print("🔍 Testing health check...")
    response = requests.get(f"{BASE_URL}/")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.json()

def test_upload_chunk(video_path: str, start_time: datetime, end_time: datetime):
    start_time = start_time.replace(microsecond=0)
    end_time = end_time.replace(microsecond=0)
    
    print(f"📤 Uploading video chunk: {video_path}")
    print(f"   Time range: {start_time.isoformat()} to {end_time.isoformat()}")
    
    with open(video_path, "rb") as video_file:
        files = {"video": video_file}
        params = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        response = requests.post(
            f"{BASE_URL}/api/video/process-chunk",
            files=files,
            params=params
        )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Success!")
        print(f"   Filename: {result['filename']}")
        print(f"   Hash: {result['blockchain']['hash']}")
        print(f"   TX Hash: {result['blockchain'].get('transaction_hash', 'N/A')}\n")
        return result
    else:
        print(f"❌ Error: {response.text}\n")
        return None

def test_verify_video(video_path: str):
    print(f"🔎 Verifying video: {video_path}")
    
    with open(video_path, "rb") as video_file:
        files = {"video": video_file}
        response = requests.post(
            f"{BASE_URL}/api/video/verify",
            files=files
        )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        if result["verified"]:
            print(f"✅ Video is VERIFIED!")
            print(f"   Hash: {result['hash']}")
            print(f"   Uploader: {result['uploader']}\n")
        else:
            print(f"❌ Video NOT verified on blockchain\n")
        return result
    else:
        print(f"❌ Error: {response.text}\n")
        return None

def test_list_chunks(start_time=None, end_time=None):
    print("📋 Listing video chunks...")
    
    if start_time:
        start_time = start_time.replace(microsecond=0)
    if end_time:
        end_time = end_time.replace(microsecond=0)
    
    params = {}
    if start_time:
        params["start_datetime"] = start_time.isoformat()
    if end_time:
        params["end_datetime"] = end_time.isoformat()
    
    response = requests.get(f"{BASE_URL}/api/video/list-chunks", params=params)
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Total chunks: {result['total_chunks']}")
        for chunk in result['chunks']:
            print(f"  - {chunk['filename']}")
            print(f"    Time: {chunk['start_time']} to {chunk['end_time']}")
            print(f"    Size: {chunk['size_bytes']:,} bytes")
        print()
        return result
    else:
        print(f"❌ Error: {response.text}\n")
        return None

def test_retrieve_video(start_time: datetime, end_time: datetime, output_path: str):
    start_time = start_time.replace(microsecond=0)
    end_time = end_time.replace(microsecond=0)
    
    print(f"📥 Retrieving video from {start_time.isoformat()} to {end_time.isoformat()}")
    
    params = {
        "start_datetime": start_time.isoformat(),
        "end_datetime": end_time.isoformat()
    }
    
    response = requests.get(
        f"{BASE_URL}/api/video/retrieve",
        params=params,
        stream=True
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✅ Video saved to: {output_path}\n")
        return True
    else:
        print(f"❌ Error: {response.text}\n")
        return False

def main():
    print("=" * 60)
    print("AuthLens API Test Client")
    print("=" * 60 + "\n")
    
    print("TEST 1: Health Check")
    print("-" * 60)
    health = test_health()
    if not health.get("blockchain_connected"):
        print("⚠️  Warning: Blockchain not connected. Some tests may fail.\n")
    
    print("TEST 2: List Existing Chunks (Before Upload)")
    print("-" * 60)
    test_list_chunks()
    
    test1_path = "../test_videos/test1.mp4"
    test2_path = "../test_videos/test2.mp4"
    
    now = datetime.now()
    test1_start = now
    test1_end = now + timedelta(minutes=1)
    
    test2_start = now + timedelta(minutes=2)
    test2_end = now + timedelta(minutes=3)
    
    print("=" * 60)
    print("TESTS FOR test1.mp4 (UPLOADED TO BLOCKCHAIN)")
    print("=" * 60 + "\n")
    
    print("TEST 3: Upload test1.mp4 Chunk")
    print("-" * 60)
    upload_result1 = test_upload_chunk(test1_path, test1_start, test1_end)
    
    print("TEST 4: Verify test1.mp4 (Expected: VERIFIED)")
    print("-" * 60)
    verify_result1 = test_verify_video(test1_path)
    if verify_result1 and verify_result1.get("verified"):
        print("✅ TEST PASSED: test1.mp4 is verified on blockchain\n")
    else:
        print("❌ TEST FAILED: test1.mp4 should be verified but isn't\n")
    
    print("TEST 5: List Chunks (After test1.mp4 Upload)")
    print("-" * 60)
    test_list_chunks()
    
    print("TEST 6: Retrieve test1.mp4 Video")
    print("-" * 60)
    retrieve_result1 = test_retrieve_video(test1_start, test1_end, "retrieved_test1.mp4")
    if retrieve_result1:
        print("✅ TEST PASSED: test1.mp4 retrieved successfully\n")
    else:
        print("❌ TEST FAILED: Could not retrieve test1.mp4\n")
    
    print("=" * 60)
    print("TESTS FOR test2.mp4 (NOT UPLOADED TO BLOCKCHAIN)")
    print("=" * 60 + "\n")
    
    print("TEST 7: Verify test2.mp4 (Expected: NOT VERIFIED)")
    print("-" * 60)
    verify_result2 = test_verify_video(test2_path)
    if verify_result2 and not verify_result2.get("verified"):
        print("✅ TEST PASSED: test2.mp4 is not verified (as expected)\n")
    else:
        print("❌ TEST FAILED: test2.mp4 should not be verified\n")
    
    print("TEST 8: Try to Retrieve test2.mp4 (Expected: FAIL)")
    print("-" * 60)
    retrieve_result2 = test_retrieve_video(test2_start, test2_end, "retrieved_test2.mp4")
    if not retrieve_result2:
        print("✅ TEST PASSED: test2.mp4 cannot be retrieved (as expected)\n")
    else:
        print("❌ TEST FAILED: test2.mp4 should not be retrievable\n")
    
    print("TEST 9: List All Chunks (Final State)")
    print("-" * 60)
    test_list_chunks()
    
    print("TEST 10: List Chunks with Time Range Filter (test1 range)")
    print("-" * 60)
    test_list_chunks(start_time=test1_start, end_time=test1_end)
    
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("✅ test1.mp4: Uploaded to blockchain, should be verified")
    print("❌ test2.mp4: NOT uploaded to blockchain, should NOT be verified")
    print("\nAll tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main()
