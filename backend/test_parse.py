from datetime import datetime

# Test the parsing logic
filename = "cam_1_2025-10-19_05-20-00-2025-10-19_05-21-00"
camera_id = "cam_1"

print(f"Testing filename: {filename}")
print(f"Camera ID: {camera_id}")

# Remove camera_id prefix
time_part = filename[len(camera_id) + 1:]  # +1 for the underscore
print(f"Time part: {time_part}")

# Split by dash
time_components = time_part.split("-")
print(f"Time components: {time_components}")
print(f"Number of components: {len(time_components)}")

if len(time_components) >= 10:
    # Parse start time
    start_year = int(time_components[0])
    start_month = int(time_components[1])
    start_day_hour = time_components[2].split("_")
    start_day = int(start_day_hour[0])
    start_hour = int(start_day_hour[1])
    start_minute = int(time_components[3])
    start_second = int(time_components[4])
    
    chunk_start = datetime(start_year, start_month, start_day, start_hour, start_minute, start_second)
    print(f"Start time: {chunk_start}")
    
    # Parse end time
    end_year = int(time_components[5])
    end_month = int(time_components[6])
    end_day_hour = time_components[7].split("_")
    end_day = int(end_day_hour[0])
    end_hour = int(end_day_hour[1])
    end_minute = int(time_components[8])
    end_second = int(time_components[9])
    
    chunk_end = datetime(end_year, end_month, end_day, end_hour, end_minute, end_second)
    print(f"End time: {chunk_end}")
    
    # Test with sample query
    query_start = datetime(2025, 10, 19, 5, 20, 0)
    query_end = datetime(2025, 10, 19, 5, 21, 0)
    
    print(f"\nQuery range: {query_start} to {query_end}")
    print(f"Chunk range: {chunk_start} to {chunk_end}")
    print(f"Overlaps: {chunk_start <= query_end and chunk_end >= query_start}")
