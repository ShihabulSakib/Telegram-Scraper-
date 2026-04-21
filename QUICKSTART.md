# Quick Start Guide - Telegram Tools Unified

## Installation (5 minutes)

```bash
# 1. Navigate to the tool
cd /home/shanto/Desktop/Jishan/Telegram/TelegramToolsUnified

# 2. Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create configuration
cp config.json.example config.json

# 5. Edit config.json with your Telegram API credentials
# Get them from: https://my.telegram.org
nano config.json  # or use any text editor
```

## First Run

```bash
# Test connection and list your channels
python telegram_unified.py list-channels
```

## Common Workflows

### Download Telegram Videos

```bash
# 1. Scan a channel
python telegram_unified.py scan-videos @channelname --limit 100

# 2. See what was found
python telegram_unified.py list-videos

# 3. Download by category
python telegram_unified.py download-videos --category "CategoryName" --workers 3
```

### Download External Links (YouTube/Drive)

```bash
# 1. Scan for links
python telegram_unified.py scan-links @channelname --limit 200

# 2. See collected links
python telegram_unified.py list-links

# 3. Download all
python telegram_unified.py download-links --all --workers 4

# Or download only YouTube
python telegram_unified.py download-links --all --type youtube --workers 3
```

### Check Status

```bash
python telegram_unified.py status
```

## Help

```bash
# General help
python telegram_unified.py --help

# Command-specific help
python telegram_unified.py scan-videos --help
python telegram_unified.py download-links --help
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed solutions.

**Quick fixes**:
- Config not found: `cp config.json.example config.json`
- Module errors: `pip install -r requirements.txt`
- Can't find channel: Use `list-channels` to see accessible channels
- Rate limiting: Reduce `--workers` count

## Tips

- Start with `--limit 50` to test before full scans
- Use 3-4 workers for best balance of speed and safety
- Check `status` regularly to track progress
- Videos are auto-categorized by filename and caption
- All data stored in `.telegram_tools_data/` directory

## Next Steps

1. Read [README.md](README.md) for complete documentation
2. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if you encounter issues
3. Experiment with different commands and options

Enjoy your unified Telegram tool! 🚀
