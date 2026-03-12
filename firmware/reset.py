"""
reset.py - Recursive file system clearer for MicroPython devices

This script recursively deletes all files and directories on the device,
leaving the filesystem clean. Use with caution!
"""

import os
import sys

def delete_recursively(path="/"):
    """
    Recursively delete all files and directories starting from path.
    
    Args:
        path: Starting path (default is root "/")
    """
    try:
        items = os.listdir(path)
    except OSError as e:
        print(f"Error listing {path}: {e}")
        return
    
    for item in items:
        # Skip the script itself if we encounter it
        if item == "reset.py":
            print(f"Skipping {item} (this script)")
            continue
        
        full_path = path + item if path == "/" else path + "/" + item
        
        try:
            # Check if it's a directory by trying to list it
            stat = os.stat(full_path)
            is_dir = stat[0] & 0o040000  # Check if directory bit is set
            
            if is_dir:
                print(f"Deleting directory: {full_path}")
                # Recursively delete contents of subdirectory
                delete_recursively(full_path + "/")
                # Then delete the empty directory
                try:
                    os.rmdir(full_path)
                    print(f"  Removed: {full_path}")
                except OSError as e:
                    print(f"  Error removing {full_path}: {e}")
            else:
                print(f"Deleting file: {full_path}")
                try:
                    os.remove(full_path)
                    print(f"  Removed: {full_path}")
                except OSError as e:
                    print(f"  Error removing {full_path}: {e}")
        except OSError as e:
            print(f"Error processing {full_path}: {e}")

def main():
    print("=" * 50)
    print("MicroPython FileStore Clearer")
    print("=" * 50)
    print("\nWARNING: This will delete ALL files on the device!")
    print("Press Ctrl+C to cancel, or wait 5 seconds to proceed...\n")
    
    # Simple countdown (user can interrupt with Ctrl+C)
    for i in range(5, 0, -1):
        print(f"Proceeding in {i} seconds...")
        import time
        time.sleep(1)
    
    print("\nStarting filesystem cleanup...\n")
    
    try:
        delete_recursively("/")
        print("\n" + "=" * 50)
        print("Filesystem cleanup complete!")
        print("=" * 50)
        print("\nThe device is now clean. You can now:")
        print("1. Upload fresh firmware files")
        print("2. Soft reset the device (Ctrl+D in REPL)")
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
