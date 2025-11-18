#!/usr/bin/env python3
"""
Script that watches a folder and removes metadata from image files.
When an image is added, all EXIF metadata is stripped while preserving the file's modification date.
Works on both macOS and Linux.
"""

import os
import sys
import time
from pathlib import Path

# Check for required dependencies
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Error: 'watchdog' module not found.", file=sys.stderr)
    print("\nPlease install required dependencies:", file=sys.stderr)
    print("  pip3 install -r requirements.txt", file=sys.stderr)
    print("  or", file=sys.stderr)
    print("  pip3 install watchdog Pillow", file=sys.stderr)
    sys.exit(1)

try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    print("Error: 'Pillow' module not found.", file=sys.stderr)
    print("\nPlease install required dependencies:", file=sys.stderr)
    print("  pip3 install -r requirements.txt", file=sys.stderr)
    print("  or", file=sys.stderr)
    print("  pip3 install watchdog Pillow", file=sys.stderr)
    sys.exit(1)


class ImageMetadataCleaner(FileSystemEventHandler):
    """Handler for file system events that cleans image metadata."""
    
    # Supported image formats
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.webp'}
    
    def __init__(self, watch_folder):
        self.watch_folder = Path(watch_folder)
        self.processed_files = set()  # Track files to avoid reprocessing
        
    def is_image_file(self, file_path):
        """Check if file is a supported image format."""
        return Path(file_path).suffix.lower() in self.SUPPORTED_FORMATS
    
    def get_metadata(self, image_path):
        """
        Extract and return metadata from an image file.
        Returns a dictionary of metadata tags.
        """
        metadata = {}
        try:
            with Image.open(image_path) as img:
                # Get EXIF data - try both new and old methods
                exifdata = img.getexif()
                gps_info_resolved = False
                
                # Try to get GPS data using the older _getexif() method if GPSInfo is unresolved
                if exifdata:
                    gps_tag_id = None
                    for tag_id in exifdata.keys():
                        if TAGS.get(tag_id) == 'GPSInfo':
                            gps_tag_id = tag_id
                            break
                    
                    # If GPSInfo exists but is an integer (IFD offset), try _getexif() as fallback
                    if gps_tag_id is not None:
                        gps_value = exifdata.get(gps_tag_id)
                        if isinstance(gps_value, int):
                            try:
                                # Try deprecated _getexif() which sometimes resolves IFD offsets better
                                old_exif = img._getexif()
                                if old_exif and gps_tag_id in old_exif:
                                    gps_dict = old_exif[gps_tag_id]
                                    if isinstance(gps_dict, dict):
                                        gps_data = {}
                                        for gps_tag_id_inner, gps_value_inner in gps_dict.items():
                                            gps_tag = GPSTAGS.get(gps_tag_id_inner, gps_tag_id_inner)
                                            gps_data[gps_tag] = gps_value_inner
                                        metadata['GPSInfo'] = gps_data
                                        gps_info_resolved = True
                            except (AttributeError, TypeError):
                                pass
                
                # Process all EXIF tags
                if exifdata:
                    for tag_id, value in exifdata.items():
                        tag = TAGS.get(tag_id, tag_id)
                        
                        # Skip GPSInfo if we already resolved it above
                        if tag == 'GPSInfo' and gps_info_resolved:
                            continue
                        
                        # Handle GPS data - check if value is actually a dict
                        if tag == 'GPSInfo' and isinstance(value, dict):
                            try:
                                gps_data = {}
                                for gps_tag_id, gps_value in value.items():
                                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                                    gps_data[gps_tag] = gps_value
                                metadata[tag] = gps_data
                            except (AttributeError, TypeError) as e:
                                # If GPSInfo value is not iterable, it's likely an IFD offset
                                metadata[tag] = f"IFD offset: {value} (GPS data pointer, not actual GPS coordinates)"
                        elif tag == 'GPSInfo' and isinstance(value, int):
                            # GPSInfo is an IFD offset - explain what it means
                            metadata[tag] = f"IFD offset: {value} (GPS data pointer, not actual GPS coordinates)"
                        elif tag == 'MakerNote':
                            # MakerNote contains proprietary manufacturer data (often includes serial numbers)
                            # PIL can't fully parse it, but we can indicate its presence
                            if isinstance(value, bytes):
                                metadata[tag] = f"<Proprietary data: {len(value)} bytes - May contain device serial numbers>"
                            else:
                                metadata[tag] = f"<Proprietary manufacturer data - May contain device serial numbers>"
                        else:
                            # Convert bytes to string if needed
                            if isinstance(value, bytes):
                                try:
                                    value = value.decode('utf-8', errors='ignore')
                                except:
                                    value = f"<bytes: {len(value)} bytes>"
                            # Handle other complex types (tuples, lists, etc.)
                            elif isinstance(value, (tuple, list)):
                                value = ', '.join(str(v) for v in value)
                            metadata[tag] = value
                
                # Get other image info
                metadata['Image Format'] = img.format
                metadata['Image Mode'] = img.mode
                metadata['Image Size'] = img.size
        except Exception as e:
            metadata['Error'] = str(e)
        
        return metadata
    
    def display_metadata(self, metadata, label="Metadata"):
        """Display metadata in a readable format."""
        if not metadata:
            print(f"  {label}: No metadata found")
            return
        
        # Sensitive fields that may contain identifying information
        sensitive_fields = {
            'SerialNumber', 'BodySerialNumber', 'LensSerialNumber', 
            'CameraSerialNumber', 'InternalSerialNumber', 'Serial Number',
            'Make', 'Model', 'Software', 'Artist', 'Copyright',
            'OwnerName', 'GPSInfo', 'GPSLatitude', 'GPSLongitude',
            'GPSAltitude', 'DateTime', 'DateTimeOriginal', 'DateTimeDigitized',
            'MakerNote', 'UserComment', 'ImageUniqueID', 'DocumentName'
        }
        
        print(f"  {label}:")
        for key, value in sorted(metadata.items()):
            # Skip image format/size/mode as they're not really "metadata" to clean
            if key in ('Image Format', 'Image Mode', 'Image Size'):
                continue
            
            # Check if this is sensitive information
            is_sensitive = any(sensitive.lower() in key.lower() for sensitive in sensitive_fields)
            marker = "🔒 " if is_sensitive else "   "
            
            # Format GPS data nicely
            if key == 'GPSInfo' and isinstance(value, dict):
                print(f"    {marker}{key} (Location Data):")
                for gps_key, gps_value in sorted(value.items()):
                    print(f"      {gps_key}: {gps_value}")
            else:
                # Truncate very long values
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                
                # Add note for serial numbers
                if 'serial' in key.lower():
                    print(f"    {marker}{key}: {value_str} ⚠️ Device Serial Number")
                elif is_sensitive:
                    print(f"    {marker}{key}: {value_str} ⚠️ Sensitive")
                else:
                    print(f"    {key}: {value_str}")
    
    def clean_image_metadata(self, image_path):
        """
        Remove all metadata from an image file while preserving the file's modification date.
        """
        try:
            image_path = Path(image_path)
            
            # Skip if not an image file
            if not self.is_image_file(image_path):
                return False
            
            # Skip if already processed (to avoid infinite loops)
            if str(image_path) in self.processed_files:
                return False
            
            print(f"\n📷 Processing: {image_path.name}")
            print("-" * 50)
            
            # Get and display metadata before cleaning
            metadata_before = self.get_metadata(image_path)
            self.display_metadata(metadata_before, "Metadata BEFORE cleaning")
            
            # Preserve original file modification time
            original_mtime = os.path.getmtime(image_path)
            
            # Open and process the image
            with Image.open(image_path) as img:
                # Create a new image without metadata
                # Convert to RGB if necessary (some formats like PNG with transparency)
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Create a white background for transparent images
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save without metadata
                # Use quality=95 for JPEG to maintain good quality
                if image_path.suffix.lower() in {'.jpg', '.jpeg'}:
                    img.save(image_path, 'JPEG', quality=95, optimize=True)
                elif image_path.suffix.lower() == '.png':
                    img.save(image_path, 'PNG', optimize=True)
                elif image_path.suffix.lower() in {'.tiff', '.tif'}:
                    img.save(image_path, 'TIFF')
                elif image_path.suffix.lower() == '.webp':
                    img.save(image_path, 'WEBP', quality=95)
                elif image_path.suffix.lower() == '.bmp':
                    img.save(image_path, 'BMP')
            
            # Restore original file modification time
            os.utime(image_path, (original_mtime, original_mtime))
            
            # Get and display metadata after cleaning
            metadata_after = self.get_metadata(image_path)
            self.display_metadata(metadata_after, "Metadata AFTER cleaning")
            
            # Mark as processed
            self.processed_files.add(str(image_path))
            
            print(f"✓ Cleaned metadata from: {image_path.name}")
            print("-" * 50)
            return True
            
        except Exception as e:
            print(f"✗ Error processing {image_path}: {e}", file=sys.stderr)
            return False
    
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory:
            # Small delay to ensure file is fully written
            time.sleep(0.5)
            self.clean_image_metadata(event.src_path)
    
    def on_moved(self, event):
        """Handle file move/rename events."""
        if not event.is_directory:
            # Small delay to ensure file is fully written
            time.sleep(0.5)
            self.clean_image_metadata(event.dest_path)


def main():
    """Main function to set up and run the folder watcher."""
    if len(sys.argv) < 2:
        print("Usage: python3 clean_images.py <folder_path>")
        print("Example: python3 clean_images.py /path/to/images")
        sys.exit(1)
    
    watch_folder = sys.argv[1]
    
    if not os.path.isdir(watch_folder):
        print(f"Error: '{watch_folder}' is not a valid directory", file=sys.stderr)
        sys.exit(1)
    
    print(f"Watching folder: {watch_folder}")
    print("Press Ctrl+C to stop...")
    print("-" * 50)
    
    # Create event handler and observer
    event_handler = ImageMetadataCleaner(watch_folder)
    observer = Observer()
    observer.schedule(event_handler, watch_folder, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping watcher...")
        observer.stop()
    
    observer.join()
    print("Watcher stopped.")


if __name__ == "__main__":
    main()

