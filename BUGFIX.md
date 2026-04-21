# Bug Fixes

## 1. Channel ID Conversion in Scanner (Fixed previously)
**Issue**: Numeric channel IDs passed as strings caused "Cannot find entity" error during scanning.
**Fix**: Added conversion logic in `telegram_unified.py`.

## 2. Channel ID Conversion in Downloader (Fixed 2026-01-02)
**Issue**: `download-videos` command failed with `ValueError: Cannot find any entity corresponding to "-100..."`.
**Cause**: The downloader was reading channel IDs from the JSON database as strings (e.g., "-100123...") and passing them directly to Telethon, which requires integers for ID lookups.
**Fix**: Updated `modules/video_downloader.py` to convert `video['channel']` to integer before calling `get_entity()`.
**Verification**: Successfully initiated download for category "NO CQ-MCQ Class😕". Files were created and sizes started increasing.
