# clean_images.py

Python script to clean meta data from images

# Install

Supports MacOS and Linux and maybe others
Requires: watchdog, Pillow (e.g. pip3 install watchdog Pillow)

# Run

* Open terminal
* python3 clean_images.py [path]

# Other

* Run this on a Diode Collab sync peer so any files added to the Drive are automatically cleaned
* Install in systemd service to make persistent on a Bot / Linux device

# Example session

```
hr@Hs-MacBook-Pro clean_images % python3 clean_images.py ./
Watching folder: ./
Press Ctrl+C to stop...
--------------------------------------------------

📷 Processing: PXL_20251117_235033644.jpg
--------------------------------------------------
  Metadata BEFORE cleaning:
    🔒 DateTime: 2025:11:17 15:50:33 ⚠️ Sensitive
    ExifOffset: 218
    🔒 GPSInfo (Location Data):
      GPSImgDirection: 273.0
      GPSImgDirectionRef: M
      GPSVersionID: b'\x02\x02\x00\x00'
    🔒 Make: Google ⚠️ Sensitive
    🔒 Model: Pixel 8 ⚠️ Sensitive
    Orientation: 1
    ResolutionUnit: 2
    🔒 Software: HDR+ 1.0.748116481zd ⚠️ Sensitive
    XResolution: 72.0
    YCbCrPositioning: 1
    YResolution: 72.0
  Metadata AFTER cleaning:
✓ Cleaned metadata from: PXL_20251117_235033644.jpg
--------------------------------------------------
```

