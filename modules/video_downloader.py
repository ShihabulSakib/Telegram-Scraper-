#!/usr/bin/env python3
"""
Video Downloader for Telegram Tools Unified
Downloads Telegram videos with parallel support and resume capability
"""

import asyncio
import time
from pathlib import Path
from typing import List, Dict
from telethon.errors import FloodWaitError, TimeoutError as TelethonTimeoutError


class VideoDownloader:
    """Download Telegram videos with parallel support"""
    
    def __init__(self, telegram_client, data_manager, config):
        self.client = telegram_client
        self.data_manager = data_manager
        self.config = config
        self.shutdown_flag = False
    
    async def download_videos_by_category(self, category: str, workers: int = 3):
        """Download all videos in a category"""
        # Load all videos
        all_videos = self.data_manager.get_all_videos()
        
        # Filter by category
        videos = [v for v in all_videos if v.get('category') == category]
        
        if not videos:
            print(f"❌ No videos found in category '{category}'")
            return
        
        # Check total size
        total_size = sum(v['size'] for v in videos)
        total_mb = total_size / (1024 * 1024)
        
        print(f"\n📥 Downloading {len(videos)} videos from '{category}'")
        print(f"📊 Total size: {total_mb:.1f} MB")
        print(f"⚙️  Using {workers} parallel workers\n")
        
        # Confirm if large
        if total_mb > self.config.size_warning_mb:
            response = input(f"⚠️  Large download ({total_mb:.1f} MB). Continue? (y/n): ")
            if response.lower() != 'y':
                return
        
        # Create download directory
        download_dir = Path(self.config.download_path) / category
        download_dir.mkdir(parents=True, exist_ok=True)
        
        # Create semaphore for parallel control
        semaphore = asyncio.Semaphore(workers)
        
        # Download tasks
        tasks = []
        for i, video in enumerate(videos, 1):
            ext = Path(video['filename']).suffix or '.mp4'
            filename = f"{category}_{i:02d}{ext}"
            filepath = download_dir / filename
            
            task = self.download_single_video(video, filepath, semaphore, i, len(videos))
            tasks.append(task)
        
        # Execute all downloads
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start_time
        
        # Count successes
        success = sum(1 for r in results if r is True)
        
        print("\n" + "="*60)
        print(f"✅ Download complete: {success}/{len(videos)} successful")
        print(f"⏱️  Total time: {elapsed:.1f}s")
        print("="*60 + "\n")
    
    async def download_single_video(self, video: Dict, filepath: Path, 
                                   semaphore: asyncio.Semaphore, 
                                   index: int, total: int) -> bool:
        """Download a single video with retry logic"""
        async with semaphore:
            # Check if already exists
            if filepath.exists():
                existing_size = filepath.stat().st_size
                if existing_size == video['size']:
                    print(f"[{index}/{total}] ✅ {filepath.name} (already complete)")
                    return True
            
            # Load download state
            state = self.data_manager.load_download_state(filepath)
            if state:
                print(f"[{index}/{total}] 🔄 Resuming {filepath.name}")
            else:
                print(f"[{index}/{total}] ⬇️  Downloading {filepath.name}")
            
            retry = 0
            while retry < self.config.max_retries:
                if self.shutdown_flag:
                    return False
                
                try:
                    # Get message
                    channel_id = video['channel']
                    try:
                        channel_id = int(channel_id)
                    except ValueError:
                        pass
                    
                    channel = await self.client.get_entity(channel_id)
                    message = await self.client.get_messages(channel, ids=video['msg_id'])
                    
                    # Progress callback
                    def progress(current, total):
                        if current % (total // 10 + 1) == 0:  # Update every 10%
                            percent = (current / total) * 100
                            print(f"[{index}/{total}] {filepath.name}: {percent:.0f}%", end='\r')
                    
                    # Download
                    await self.client.download_media(
                        message,
                        file=str(filepath),
                        progress_callback=progress
                    )
                    
                    # Verify
                    final_size = filepath.stat().st_size
                    if final_size == video['size']:
                        print(f"[{index}/{total}] ✅ {filepath.name} ({final_size/(1024*1024):.1f} MB)")
                        self.data_manager.cleanup_download_state(filepath)
                        return True
                    else:
                        retry += 1
                        print(f"[{index}/{total}] ⚠️  Size mismatch, retry {retry}/{self.config.max_retries}")
                
                except FloodWaitError as e:
                    print(f"[{index}/{total}] ⏳ FloodWait {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                    retry += 1
                
                except (TelethonTimeoutError, ConnectionError, OSError) as e:
                    retry += 1
                    wait = self.config.retry_delay * (2 ** (retry - 1))
                    print(f"[{index}/{total}] 🔄 Network error, retry in {wait:.0f}s")
                    # Save state before retry
                    if filepath.exists():
                        self.data_manager.save_download_state(filepath, filepath.stat().st_size, video['size'])
                    await asyncio.sleep(wait)
                    await self.client.reconnect()
                
                except Exception as e:
                    print(f"[{index}/{total}] ❌ Error: {type(e).__name__}: {str(e)[:50]}")
                    retry += 1
                    if retry < self.config.max_retries:
                        await asyncio.sleep(self.config.retry_delay)
            
            print(f"[{index}/{total}] ❌ Failed after {self.config.max_retries} retries")
            return False
