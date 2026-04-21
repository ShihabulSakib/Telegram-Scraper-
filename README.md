# Telegram Tools Unified

A powerful CLI tool combining Telegram video downloads and external link harvesting with intelligent categorization and parallel download support.

## Features

### 🎥 Telegram Video Downloads
- Scan channels for video content
- **Intelligent auto-categorization** using filenames and captions
- Channel message pattern analysis for chronological grouping
- Parallel downloads with resume support
- Progress tracking with speed and ETA

### 🔗 External Link Harvesting
- Scan channels for YouTube and Google Drive links
- Parallel downloads (3-10x faster)
- Support for playlists and folders
- Beautiful progress bars with tqdm

### 🛡️ Robust Error Handling
- Automatic retry with exponential backoff
- FloodWait detection and handling
- Network error recovery
- Clear, actionable error messages

### 💾 Smart Download Management
- Resume interrupted downloads
- Download state persistence
- File verification
- Configurable parallel workers (1-10)

## Installation

### Prerequisites
- Python 3.10 or higher
- Telegram API credentials ([Get them here](https://my.telegram.org))

### Setup

```bash
# Navigate to the tool directory
cd TelegramToolsUnified

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create configuration file
cp config.json.example config.json
# Edit config.json with your Telegram API credentials
```

### Configuration

Edit `config.json` with your credentials:

```json
{
  "api_id": "12345678",
  "api_hash": "your_api_hash_here",
  "phone": "+1234567890",
  "download_path": "downloads",
  "max_parallel_downloads": 3,
  "chunk_size_kb": 512,
  "max_retries": 5,
  "retry_delay_seconds": 3
}
```

## Usage

### List Your Channels

```bash
python telegram_unified.py list-channels
```

### Scan for Videos

```bash
# Scan a channel for Telegram videos
python telegram_unified.py scan-videos @channelname

# Limit the scan
python telegram_unified.py scan-videos @channelname --limit 100

# Scan private channel by ID
python telegram_unified.py scan-videos -1001234567890
```

### List Scanned Videos

```bash
# List all videos with categories
python telegram_unified.py list-videos

# Filter by keyword
python telegram_unified.py list-videos --filter "python"

# Show specific category
python telegram_unified.py list-videos --category "Tutorial"
```

### Download Videos

```bash
# Download all videos from a category
python telegram_unified.py download-videos --category "Tutorial" --workers 3

# Download all uncategorized videos
python telegram_unified.py download-videos --category "Uncategorized"

# Download with more parallel workers (faster)
python telegram_unified.py download-videos --category "Course" --workers 5
```

### Scan for External Links

```bash
# Scan for YouTube and Google Drive links
python telegram_unified.py scan-links @channelname --limit 200

# Scan multiple channels (run multiple times)
python telegram_unified.py scan-links @channel1 --limit 100
python telegram_unified.py scan-links @channel2 --limit 100
```

### List Collected Links

```bash
# List all links
python telegram_unified.py list-links

# Filter by keyword
python telegram_unified.py list-links --filter "tutorial"

# Show only YouTube links
python telegram_unified.py list-links --type youtube
```

### Download External Links

```bash
# Download all pending links with 4 workers (recommended)
python telegram_unified.py download-links --all --workers 4

# Download only YouTube videos
python telegram_unified.py download-links --all --type youtube --workers 3

# Download only Google Drive files
python telegram_unified.py download-links --all --type drive --workers 5

# Download with filter
python telegram_unified.py download-links --filter "python" --workers 4
```

### Check Status

```bash
# View overall statistics
python telegram_unified.py status
```

### Manage Configuration

```bash
# Show current configuration
python telegram_unified.py config --show

# Update settings
python telegram_unified.py config --set max_parallel_downloads=5
```

## Command Reference

| Command | Description |
|---------|-------------|
| `list-channels` | List all accessible Telegram channels/groups |
| `scan-videos` | Scan a channel for Telegram videos |
| `list-videos` | List scanned videos with categories |
| `download-videos` | Download Telegram videos by category |
| `scan-links` | Scan a channel for external links (YouTube/Drive) |
| `list-links` | List collected external links |
| `download-links` | Download external content |
| `status` | Show overall statistics |
| `config` | Manage configuration |

## Performance Tips

### Worker Count Recommendations

- **1-2 workers**: Slow internet, maximum safety
- **3-4 workers**: ⭐ **Recommended** - Best balance
- **5-6 workers**: Fast internet, some risk
- **7+ workers**: ⚠️ High rate limit risk

### For Best Results

1. Start with 4 workers (default)
2. Use `--limit` to test with small batches first
3. Monitor download speeds and adjust workers
4. Check `status` regularly to track progress
5. Use filters to download only what you need

## Troubleshooting

### Common Issues

**"config.json not found"**
```bash
cp config.json.example config.json
# Then edit with your credentials
```

**"Cannot find entity"**
- Make sure you're a member of the channel/group
- Use `list-channels` to see accessible channels
- Try using the numeric ID instead of username

**"FloodWait" or rate limiting**
```bash
# Reduce workers
python telegram_unified.py download-links --all --workers 2
```

**Download fails to resume**
- Check disk space
- Verify file permissions in download directory
- Try deleting `.dlstate` files and restarting

**"Session password needed"**
- Your account has 2FA enabled
- Enter your 2FA password when prompted
- This only happens once per session

For more detailed troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Project Structure

```
TelegramToolsUnified/
├── telegram_unified.py          # Main CLI entry point
├── config.json                  # Your configuration (create from example)
├── config.json.example          # Example configuration
├── requirements.txt             # Dependencies
├── README.md                    # This file
├── TROUBLESHOOTING.md          # Detailed troubleshooting guide
├── core/                        # Core components
│   ├── config_manager.py       # Configuration management
│   ├── telegram_client.py      # Telegram client wrapper
│   └── data_manager.py         # Data storage management
├── modules/                     # Feature modules
│   ├── video_scanner.py        # Video scanning & categorization
│   ├── video_downloader.py     # Video downloads
│   ├── link_scanner.py         # Link extraction
│   └── link_downloader.py      # External downloads
└── utils/                       # Utilities
    ├── progress_display.py     # Progress tracking
    ├── error_handler.py        # Error handling
    └── validators.py           # Input validation
```

## Security & Privacy

- **Keep `config.json` private** - Contains your API credentials
- **Session files** - The `.session` file contains your login token
- **Never share** - Don't commit credentials to public repositories
- **2FA recommended** - Enable two-factor authentication on your Telegram account

### .gitignore Recommendation

```
config.json
*.session
*.session-journal
.telegram_tools_data/
downloads/
__pycache__/
*.pyc
venv/
```

## Examples

### Daily Content Collector

```bash
#!/bin/bash
# Scan multiple channels daily
python telegram_unified.py scan-videos @educhannel --limit 50
python telegram_unified.py scan-links @techNews --limit 100

# Download everything
python telegram_unified.py download-videos --category "Lecture" --workers 4
python telegram_unified.py download-links --all --workers 4

# Check results
python telegram_unified.py status
```

### Selective Download

```bash
# Scan and filter before downloading
python telegram_unified.py scan-links @channel --limit 500
python telegram_unified.py list-links --filter "python"
python telegram_unified.py download-links --filter "python" --workers 3
```

## License

This tool is provided as-is for personal use. Respect copyright laws and Telegram's Terms of Service when downloading content.

## Legal Notice

- Only download content you have permission to access
- Respect intellectual property rights
- Follow Telegram's Terms of Service
- This tool is for personal archival purposes
- The creator is not responsible for misuse

## Support

For issues and questions:
1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Review command help: `python telegram_unified.py <command> --help`
3. Check Telegram API status: [https://core.telegram.org/api](https://core.telegram.org/api)

---

**Made with ❤️ for Telegram power users**

**Now with intelligent categorization and blazing-fast parallel downloads! 🚀**
