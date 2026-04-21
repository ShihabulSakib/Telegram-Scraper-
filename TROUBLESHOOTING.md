# Troubleshooting Guide - Telegram Tools Unified

This guide covers common issues and their solutions.

## Installation Issues

### "ModuleNotFoundError: No module named 'telethon'"

**Problem**: Dependencies not installed.

**Solution**:
```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install telethon yt-dlp gdown tqdm python-Levenshtein
```

### "python: command not found"

**Problem**: Python not in PATH or not installed.

**Solution**:
- Try `python3` instead of `python`
- Install Python 3.10 or higher
- On Windows, reinstall Python and check "Add to PATH"

## Configuration Issues

### "config.json not found"

**Problem**: Configuration file missing.

**Solution**:
```bash
cp config.json.example config.json
# Edit config.json with your credentials
```

Get credentials from: https://my.telegram.org

### "Missing required configuration"

**Problem**: api_id, api_hash, or phone not set.

**Solution**:
1. Open `config.json`
2. Fill in all required fields:
   - `api_id`: Your Telegram API ID (number)
   - `api_hash`: Your Telegram API hash (string)
   - `phone`: Your phone with country code (e.g., "+1234567890")

### "api_id must be a number"

**Problem**: api_id is quoted as a string.

**Solution**:
```json
{
  "api_id": 12345678,  ← No quotes
  "api_hash": "abc123...",  ← With quotes
  "phone": "+1234567890"
}
```

## Connection Issues

### "Connection failed" or "Timeout"

**Problem**: Network issues or Telegram API unavailable.

**Solutions**:
1. Check your internet connection
2. Try again in a few minutes
3. Check Telegram API status: https://core.telegram.org/api
4. Increase timeout in config.json:
   ```json
   "connection_timeout_seconds": 60
   ```

### "Enter verification code:" but no code received

**Problem**: Code sent to your Telegram app.

**Solution**:
1. Open Telegram on your phone/desktop
2. Look for a message from "Telegram"
3. Enter the 5-digit code
4. Code expires after a few minutes - request new one if needed

### "SessionPasswordNeededError"

**Problem**: Your account has 2FA (two-factor authentication) enabled.

**Solution**:
1. Enter your 2FA password when prompted
2. This is your cloud password, not your phone's PIN
3. If forgotten, reset via Telegram app settings

## Channel/Group Issues

### "Cannot find any entity corresponding to..."

**Problem**: Channel doesn't exist or you're not a member.

**Solutions**:
1. Run `python telegram_unified.py list-channels` to see accessible channels
2. Make sure you're a member of the channel/group
3. For private channels, use the numeric ID instead of username
4. Check spelling of username (include @)

### "No videos/links found"

**Problem**: Channel has no content or limit too small.

**Solutions**:
1. Increase `--limit` or remove it to scan all messages
2. Verify channel actually has videos/links
3. Check if you have permission to view media

## Download Issues

### "FloodWait" or "Too many requests"

**Problem**: Telegram rate limiting.

**Solutions**:
1. Reduce number of workers:
   ```bash
   python telegram_unified.py download-videos --category "X" --workers 2
   ```
2. Wait the specified time (shown in error message)
3. Increase retry delay in config.json:
   ```json
   "retry_delay_seconds": 5
   ```

### YouTube download fails - "Video unavailable"

**Problem**: Video is private, deleted, or region-locked.

**Solutions**:
1. Check if video is accessible in browser
2. For private videos, you may need cookies (advanced)
3. Some videos cannot be downloaded programmatically
4. Try updating yt-dlp:
   ```bash
   pip install --upgrade yt-dlp
   ```

### Google Drive download fails - "Permission denied"

**Problem**: File is private or restricted.

**Solutions**:
1. Click link in browser and request access
2. Ask file owner to change permissions to "Anyone with link"
3. Some files cannot be downloaded programmatically
4. Try updating gdown:
   ```bash
   pip install --upgrade gdown
   ```

### "Disk space" or "No space left"

**Problem**: Not enough disk space.

**Solutions**:
1. Free up disk space
2. Change download location in config.json:
   ```json
   "download_path": "/path/to/larger/drive"
   ```
3. Download in smaller batches

### Downloads are slow

**Problem**: Network speed or rate limiting.

**Solutions**:
1. Check your internet speed
2. Reduce workers if being rate limited
3. Large videos naturally take time
4. Try downloading at off-peak hours

### Resume not working

**Problem**: Download state files corrupted or deleted.

**Solutions**:
1. Check `.telegram_tools_data/download_states/` exists
2. Delete `.dlstate` files and restart download
3. Ensure sufficient disk space
4. Check file permissions

## Categorization Issues

### Videos not categorized correctly

**Problem**: Auto-categorization algorithm limitations.

**Solutions**:
1. Videos are categorized by filename and caption keywords
2. Similar videos should have similar names/captions
3. Manual categorization not currently supported (feature request)
4. Check that captions are being extracted (they should be)

### All videos marked "Uncategorized"

**Problem**: No common keywords found.

**Solutions**:
1. This is normal for diverse content
2. Videos need similar keywords to be grouped
3. You can still download by "Uncategorized" category

## Error Messages

### "yt-dlp not installed"

**Solution**:
```bash
pip install yt-dlp
```

### "gdown not installed"

**Solution**:
```bash
pip install gdown
```

### "python-Levenshtein not installed"

**Solution**:
```bash
pip install python-Levenshtein
```

### "Permission denied" when writing files

**Problem**: No write permission in download directory.

**Solutions**:
1. Check directory permissions
2. Change download path in config.json
3. Run with appropriate permissions (avoid sudo if possible)

### "JSON decode error"

**Problem**: Corrupted database file.

**Solutions**:
1. Check `.telegram_tools_data/` directory
2. Backup and delete corrupted `.json` files
3. Re-scan channels to rebuild database

## Platform-Specific Issues

### Windows: "UnicodeEncodeError"

**Problem**: Terminal encoding issues.

**Solutions**:
1. Use Windows Terminal or PowerShell (not CMD)
2. Set environment variable:
   ```powershell
   $env:PYTHONIOENCODING="utf-8"
   ```
3. Run with UTF-8 support:
   ```powershell
   chcp 65001
   python telegram_unified.py ...
   ```

### Linux/Mac: "Permission denied" when running script

**Solution**:
```bash
chmod +x telegram_unified.py
```

### Mac: "SSL Certificate" errors

**Solution**:
```bash
/Applications/Python\ 3.x/Install\ Certificates.command
```

## Performance Issues

### High memory usage

**Problem**: Large number of videos/links in memory.

**Solutions**:
1. Process in smaller batches
2. Use filters to reduce dataset
3. Restart tool periodically

### Slow scanning

**Problem**: Large channels take time.

**Solutions**:
1. Use `--limit` to scan recent messages only
2. Scanning is I/O bound, be patient
3. This is normal for channels with thousands of messages

## Data Management

### Where is my data stored?

**Location**: `.telegram_tools_data/` directory

**Contents**:
- `channels/` - Channel information
- `videos/` - Video metadata
- `links/` - Link databases
- `download_states/` - Resume information

### How to reset everything?

**Solution**:
```bash
rm -rf .telegram_tools_data/
# Re-scan channels to rebuild
```

### How to backup my data?

**Solution**:
```bash
# Backup
tar -czf telegram_tools_backup.tar.gz .telegram_tools_data/

# Restore
tar -xzf telegram_tools_backup.tar.gz
```

## Getting More Help

### Enable debug mode

Add to your Python command:
```bash
python -v telegram_unified.py ...
```

### Check logs

Look for error messages in terminal output.

### Verify installation

```bash
python --version  # Should be 3.10+
pip list | grep telethon
pip list | grep yt-dlp
pip list | grep gdown
```

### Test connection

```bash
python telegram_unified.py list-channels
```

If this works, your setup is correct.

## Common Workflow Issues

### "No pending links to download"

**Problem**: All links already downloaded or no links collected.

**Solutions**:
1. Run `python telegram_unified.py list-links` to see status
2. Scan more channels with `scan-links`
3. Links marked "completed" won't be re-downloaded

### "Category not found"

**Problem**: Typo in category name or no videos in category.

**Solutions**:
1. Run `python telegram_unified.py list-videos` to see exact category names
2. Category names are case-sensitive
3. Use quotes if category has spaces: `--category "My Category"`

## Still Having Issues?

1. **Check Python version**: Must be 3.10 or higher
2. **Update dependencies**: `pip install --upgrade -r requirements.txt`
3. **Check Telegram API**: https://core.telegram.org/api
4. **Review command syntax**: `python telegram_unified.py <command> --help`
5. **Start fresh**: Delete `.telegram_tools_data/` and re-scan

## Reporting Bugs

When reporting issues, include:
- Python version (`python --version`)
- OS and version
- Full error message
- Command you ran
- Expected vs actual behavior
