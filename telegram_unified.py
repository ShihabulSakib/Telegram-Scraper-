#!/usr/bin/env python3
"""
Telegram Tools Unified - Main CLI Application
Combines video downloads and link harvesting with intelligent categorization
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.telegram_client import TelegramClientWrapper
from core.data_manager import DataManager
from modules.video_scanner import VideoScanner
from modules.video_downloader import VideoDownloader
from modules.link_scanner import LinkScanner
from modules.link_downloader import LinkDownloader


async def list_channels_command(client, data_manager):
    """List all accessible channels/groups"""
    print("\n" + "="*70)
    print("YOUR TELEGRAM CHANNELS & GROUPS")
    print("="*70 + "\n")
    
    channel_list_data = []
    dialogs = await client.get_dialogs()
    
    for dialog in dialogs:
        if dialog.is_channel or dialog.is_group:
            channel_type = "📢 Channel" if dialog.is_channel else "👥 Group"
            username = f"@{dialog.entity.username}" if dialog.entity.username else "(no username)"
            
            print(f"{channel_type}: {dialog.name}")
            print(f"  ID: {dialog.id}")
            print(f"  Username: {username}")
            
            usage_id = f"@{dialog.entity.username}" if dialog.entity.username else dialog.id
            print(f"  Use: python telegram_unified.py scan-videos {usage_id}\n")
            
            channel_list_data.append({
                'name': dialog.name,
                'id': dialog.id,
                'username': dialog.entity.username,
                'type': 'channel' if dialog.is_channel else 'group'
            })
    
    data_manager.save_channel_list(channel_list_data)
    
    print("="*70)
    print("💡 Tip: Copy the ID or username to use with scan commands")
    print("="*70 + "\n")


async def scan_videos_command(client, data_manager, args):
    """Scan a channel for videos"""
    scanner = VideoScanner(client, data_manager)
    await scanner.scan_channel(args.channel, args.limit)


async def list_videos_command(data_manager, args):
    """List scanned videos"""
    all_videos = data_manager.get_all_videos()
    
    # Apply filters
    if args.filter:
        all_videos = [v for v in all_videos if args.filter.lower() in 
                     f"{v['filename']} {v.get('caption', '')}".lower()]
    
    if args.category:
        all_videos = [v for v in all_videos if v.get('category') == args.category]
    
    if not all_videos:
        print("No videos found")
        return
    
    # Group by category
    from collections import defaultdict
    by_category = defaultdict(list)
    for video in all_videos:
        category = video.get('category', 'Uncategorized')
        by_category[category].append(video)
    
    print(f"\n{'='*70}")
    print(f"SCANNED VIDEOS ({len(all_videos)} total)")
    print(f"{'='*70}\n")
    
    for category in sorted(by_category.keys()):
        videos = by_category[category]
        print(f"📁 {category} ({len(videos)} videos)")
        
        # Sort by ordinal if available, else date
        videos.sort(key=lambda x: (x.get('ordinal') or 9999, x.get('date', '')))
        
        for i, video in enumerate(videos, 1):
            size_mb = video['size'] / (1024 * 1024)
            ordinal_str = f" [Part {video['ordinal']}]" if video.get('ordinal') else ""
            conf_str = f" ({int(video.get('confidence', 0)*100)}% conf)" if video.get('confidence') else ""
            source_icon = "🤖" if video.get('chapter_source') == 'caption_inference' else "📍" if video.get('chapter_source') == 'checkpoint' else "⤵️"
            
            print(f"   {i}.{ordinal_str} {video['filename']} ({size_mb:.1f} MB) {source_icon}{conf_str}")
            if video.get('caption'):
                # Clean up caption for display - remove newlines
                clean_caption = video['caption'].replace('\n', ' ')[:60]
                print(f"      Caption: {clean_caption}...")
            if video.get('notes'):
                print(f"      Note: {video['notes']}")
        print()


async def download_videos_command(client, data_manager, config, args):
    """Download videos by category"""
    if not args.category:
        print("❌ Error: --category is required")
        print("Use 'list-videos' to see available categories")
        return
    
    downloader = VideoDownloader(client, data_manager, config)
    await downloader.download_videos_by_category(args.category, args.workers)


async def scan_links_command(client, data_manager, args):
    """Scan a channel for external links"""
    scanner = LinkScanner(client, data_manager)
    await scanner.scan_channel(args.channel, args.limit)


def list_links_command(data_manager, args):
    """List collected links"""
    all_links = data_manager.get_all_links()
    
    # Apply filters
    if args.filter:
        all_links = [l for l in all_links if args.filter.lower() in l.get('caption', '').lower()]
    
    if args.type:
        all_links = [l for l in all_links if l['type'] == args.type]
    
    if not all_links:
        print("No links found")
        return
    
    print(f"\n{'='*70}")
    print(f"COLLECTED LINKS ({len(all_links)} total)")
    print(f"{'='*70}\n")
    
    for i, link in enumerate(all_links, 1):
        status_emoji = {'pending': '⏳', 'completed': '✓', 'failed': '✗'}.get(link.get('status', 'pending'), '?')
        print(f"{i}. [{status_emoji}] {link['type'].upper()}: {link['url']}")
        print(f"   Caption: {link.get('caption', '')[:70]}...")
        print(f"   Date: {link['date']} | Status: {link.get('status', 'pending')}\n")


def download_links_command(data_manager, config, args):
    """Download external links"""
    # Validate worker count
    workers = args.workers
    if workers < 1:
        print("❌ Error: Workers must be at least 1")
        return
    if workers > 10:
        print("⚠️  Warning: More than 10 workers may cause rate limiting!")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # Get links
    all_links = data_manager.get_all_links()
    
    # Filter pending links
    pending = [l for l in all_links if l.get('status', 'pending') in ['pending', 'failed']]
    
    # Apply additional filters
    if args.type:
        pending = [l for l in pending if l['type'] == args.type]
    
    if args.filter:
        pending = [l for l in pending if args.filter.lower() in l.get('caption', '').lower()]
    elif not args.all:
        print("❌ Error: Specify --all or --filter")
        return
    
    if not pending:
        print("No pending links to download")
        return
    
    downloader = LinkDownloader(data_manager, config, workers)
    downloader.download_batch(pending)


def reset_links_command(data_manager, args):
    """Reset link statuses back to pending so they get retried."""
    target = args.status  # 'failed', 'completed', or 'all'
    filter_text = args.filter or ''
    link_type   = args.type or ''

    # Show a preview first
    all_links = data_manager.get_all_links()
    candidates = []
    for l in all_links:
        s = l.get('status', 'pending')
        if s == 'pending':
            continue
        if target != 'all' and s != target:
            continue
        if link_type and l.get('type', '') != link_type:
            continue
        if filter_text and filter_text.lower() not in l.get('caption', '').lower():
            continue
        candidates.append(l)

    if not candidates:
        print(f"No links match those criteria (status={target}, type={link_type or 'any'}, filter={filter_text or 'none'})")
        return

    print(f"\n🔄 About to reset {len(candidates)} link(s) → pending:")
    for l in candidates[:10]:
        print(f"  [{l.get('status','?')}] {l['type'].upper()}: {l.get('caption','')[:60]}")
    if len(candidates) > 10:
        print(f"  ... and {len(candidates) - 10} more")

    confirm = input(f"\nReset all {len(candidates)} link(s) to pending? (y/n): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return

    count = data_manager.reset_links_status(
        target_status=target,
        filter_text=filter_text,
        link_type=link_type,
    )
    print(f"✅ Reset {count} link(s) to pending. Run 'download-links --all' to retry them.")


def status_command(data_manager):
    """Show overall statistics"""
    stats = data_manager.get_statistics()
    
    print("\n" + "="*60)
    print("TELEGRAM TOOLS UNIFIED - STATUS")
    print("="*60)
    
    print(f"\n📹 Videos: {stats['total_videos']}")
    if stats['videos_by_category']:
        print("   By Category:")
        for category, count in sorted(stats['videos_by_category'].items()):
            print(f"     • {category}: {count}")
    
    print(f"\n🔗 Links: {stats['total_links']}")
    if stats['links_by_type']:
        print("   By Type:")
        for link_type, count in stats['links_by_type'].items():
            print(f"     • {link_type}: {count}")
    
    if stats['links_by_status']:
        print("   By Status:")
        for status, count in stats['links_by_status'].items():
            print(f"     • {status}: {count}")
    
    print("="*60 + "\n")



def rename_category_command(data_manager, args):
    """Rename a video category"""
    old_name = args.old
    new_name = args.new
    
    print(f"\n🔄 Renaming category '{old_name}' to '{new_name}'...")
    
    count = data_manager.rename_category(old_name, new_name)
    
    if count > 0:
        print(f"✅ Successfully updated {count} videos.")
        print(f"   Category '{old_name}' merged into '{new_name}'")
    else:
        print(f"⚠️  No videos found in category '{old_name}'")
    print()


def config_command(config, args):
    """Manage configuration"""
    if args.show:
        config.show_config()
    elif args.set:
        try:
            key, value = args.set.split('=', 1)
            if config.update_setting(key, value):
                config.save_config()
        except ValueError:
            print("❌ Error: Use format --set key=value")
    else:
        print("Use --show to view config or --set key=value to update")


async def main():
    """Main CLI application"""
    parser = argparse.ArgumentParser(
        description='Telegram Tools Unified - Video downloads and link harvesting',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List channels
  python telegram_unified.py list-channels
  
  # Scan for videos
  python telegram_unified.py scan-videos @channel --limit 100
  
  # List and download videos
  python telegram_unified.py list-videos
  python telegram_unified.py download-videos --category "Tutorial" --workers 3
  
  # Scan for links
  python telegram_unified.py scan-links @channel --limit 200
  
  # Download links
  python telegram_unified.py download-links --all --workers 4
  python telegram_unified.py download-links --type youtube --workers 3
  
  # Check status
  python telegram_unified.py status
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List channels
    subparsers.add_parser('list-channels', help='List all accessible channels/groups')
    
    # Scan videos
    scan_videos_parser = subparsers.add_parser('scan-videos', help='Scan channel for videos')
    scan_videos_parser.add_argument('channel', help='Channel username or ID')
    scan_videos_parser.add_argument('--limit', type=int, help='Limit number of messages')
    
    # List videos
    list_videos_parser = subparsers.add_parser('list-videos', help='List scanned videos')
    list_videos_parser.add_argument('--filter', help='Filter by keyword')
    list_videos_parser.add_argument('--category', help='Show specific category')
    
    # Download videos
    download_videos_parser = subparsers.add_parser('download-videos', help='Download videos')
    download_videos_parser.add_argument('--category', required=True, help='Category to download')
    download_videos_parser.add_argument('--workers', type=int, default=3, help='Parallel workers (default: 3)')
    
    # Scan links
    scan_links_parser = subparsers.add_parser('scan-links', help='Scan channel for links')
    scan_links_parser.add_argument('channel', help='Channel username or ID')
    scan_links_parser.add_argument('--limit', type=int, help='Limit number of messages')
    
    # List links
    list_links_parser = subparsers.add_parser('list-links', help='List collected links')
    list_links_parser.add_argument('--filter', help='Filter by caption text')
    list_links_parser.add_argument('--type', choices=['youtube', 'drive'], help='Filter by type')
    
    # Download links
    download_links_parser = subparsers.add_parser('download-links', help='Download external links')
    download_links_parser.add_argument('--all', action='store_true', help='Download all pending links')
    download_links_parser.add_argument('--type', choices=['youtube', 'drive'], help='Download specific type')
    download_links_parser.add_argument('--filter', help='Download links matching filter')
    download_links_parser.add_argument('--workers', type=int, default=4, help='Parallel workers (default: 4)')
    
    # Status
    subparsers.add_parser('status', help='Show statistics')

    # Reset links
    reset_links_parser = subparsers.add_parser('reset-links', help='Reset link statuses back to pending for retry')
    reset_links_parser.add_argument('--status', choices=['failed', 'completed', 'all'], default='failed',
                                    help="Which status to reset (default: failed)")
    reset_links_parser.add_argument('--type', choices=['youtube', 'drive'], help='Only reset this link type')
    reset_links_parser.add_argument('--filter', help='Only reset links whose caption contains this text')
    
    # Config
    config_parser = subparsers.add_parser('config', help='Manage configuration')
    config_parser.add_argument('--show', action='store_true', help='Show current config')
    config_parser.add_argument('--set', help='Set config value (format: key=value)')
    
    # Rename category
    rename_parser = subparsers.add_parser('rename-category', help='Rename/Merge video categories')
    rename_parser.add_argument('--old', required=True, help='Old category name')
    rename_parser.add_argument('--new', required=True, help='New category name')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize
    try:
        config = ConfigManager()
        if not config.validate():
            return
    except FileNotFoundError:
        return
    
    data_manager = DataManager()
    
    # Commands that don't need Telegram connection
    if args.command == 'list-videos':
        await list_videos_command(data_manager, args)
        return
    elif args.command == 'list-links':
        list_links_command(data_manager, args)
        return
    elif args.command == 'download-links':
        download_links_command(data_manager, config, args)
        return
    elif args.command == 'status':
        status_command(data_manager)
        return
    elif args.command == 'reset-links':
        reset_links_command(data_manager, args)
        return
    elif args.command == 'config':
        config_command(config, args)
        return
    elif args.command == 'rename-category':
        rename_category_command(data_manager, args)
        return
    
    # Commands that need Telegram connection
    client = TelegramClientWrapper(config)
    
    try:
        if not await client.connect():
            return
        
        if args.command == 'list-channels':
            await list_channels_command(client, data_manager)
        elif args.command == 'scan-videos':
            # Convert channel to int if it's a numeric ID
            channel = args.channel
            try:
                channel = int(channel)
            except ValueError:
                pass  # It's a username, keep as string
            args.channel = channel
            await scan_videos_command(client, data_manager, args)
        elif args.command == 'download-videos':
            await download_videos_command(client, data_manager, config, args)
        elif args.command == 'scan-links':
            # Convert channel to int if it's a numeric ID
            channel = args.channel
            try:
                channel = int(channel)
            except ValueError:
                pass  # It's a username, keep as string
            args.channel = channel
            await scan_links_command(client, data_manager, args)
    
    finally:
        await client.disconnect()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏸️  Interrupted by user")
        sys.exit(0)
