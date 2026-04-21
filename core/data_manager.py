#!/usr/bin/env python3
"""
Data Manager for Telegram Tools Unified
Handles all file and directory operations for persistent data storage
"""

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class DataManager:
    """Manages all data storage for videos, links, and download states"""
    
    def __init__(self, data_dir: str = '.telegram_tools_data'):
        self.data_dir = Path(data_dir)
        self.channels_dir = self.data_dir / 'channels'
        self.videos_dir = self.data_dir / 'videos'
        self.links_dir = self.data_dir / 'links'
        self.states_dir = self.data_dir / 'download_states'
        self.channel_info_path = self.data_dir / 'channel_info.json'
        
        # Create all directories
        for directory in [self.data_dir, self.channels_dir, self.videos_dir, 
                         self.links_dir, self.states_dir]:
            directory.mkdir(exist_ok=True, parents=True)
        
        # Thread locks for file operations
        self.locks = {}
    
    def _get_lock(self, filepath: str) -> threading.Lock:
        """Get or create a lock for a specific file"""
        if filepath not in self.locks:
            self.locks[filepath] = threading.Lock()
        return self.locks[filepath]
    
    def _sanitize_channel_id(self, channel_entity) -> str:
        """Convert channel entity to safe filename string"""
        channel_id = str(channel_entity).lstrip('@')
        return re.sub(r'[^\w\.\-]', '_', channel_id)
    
    # Channel Information
    def save_channel_list(self, channel_list: List[Dict]):
        """Save list of user's channels"""
        with self._get_lock(str(self.channel_info_path)):
            with open(self.channel_info_path, 'w', encoding='utf-8') as f:
                json.dump(channel_list, f, indent=2, ensure_ascii=False)
    
    def load_channel_list(self) -> List[Dict]:
        """Load list of user's channels"""
        if not self.channel_info_path.exists():
            return []
        with self._get_lock(str(self.channel_info_path)):
            with open(self.channel_info_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    # Video Data Management
    def get_video_db_path(self, channel_entity) -> Path:
        """Get database path for channel's videos"""
        safe_id = self._sanitize_channel_id(channel_entity)
        return self.videos_dir / f"{safe_id}_videos.json"
    
    def save_videos(self, channel_entity, videos: List[Dict]):
        """Save video data for a channel"""
        db_path = self.get_video_db_path(channel_entity)
        with self._get_lock(str(db_path)):
            with open(db_path, 'w', encoding='utf-8') as f:
                json.dump(videos, f, indent=2, ensure_ascii=False)
    
    def load_videos(self, channel_entity) -> List[Dict]:
        """Load video data for a channel"""
        db_path = self.get_video_db_path(channel_entity)
        if not db_path.exists():
            return []
        with self._get_lock(str(db_path)):
            with open(db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    def get_all_videos(self) -> List[Dict]:
        """Load all videos from all channels"""
        all_videos = []
        for db_path in self.videos_dir.glob('*_videos.json'):
            with self._get_lock(str(db_path)):
                with open(db_path, 'r', encoding='utf-8') as f:
                    all_videos.extend(json.load(f))
        return all_videos
    
    
    def rename_category(self, old_category: str, new_category: str) -> int:
        """Rename a category across all video databases"""
        updated_count = 0
        
        for db_path in self.videos_dir.glob('*_videos.json'):
            updated_in_file = False
            file_videos = []
            
            with self._get_lock(str(db_path)):
                with open(db_path, 'r', encoding='utf-8') as f:
                    file_videos = json.load(f)
                
                for video in file_videos:
                    if video.get('category') == old_category:
                        video['category'] = new_category
                        video['notes'] = (video.get('notes', '') + f" [Renamed from '{old_category}']").strip()
                        updated_count += 1
                        updated_in_file = True
                
                if updated_in_file:
                    with open(db_path, 'w', encoding='utf-8') as f:
                        json.dump(file_videos, f, indent=2, ensure_ascii=False)
        
        return updated_count
    
    # Link Data Management
    def get_link_db_path(self, channel_entity) -> Path:
        """Get database path for channel's links"""
        safe_id = self._sanitize_channel_id(channel_entity)
        return self.links_dir / f"{safe_id}_links.json"
    
    def save_links(self, channel_entity, links: List[Dict]):
        """Save link data for a channel"""
        db_path = self.get_link_db_path(channel_entity)
        with self._get_lock(str(db_path)):
            with open(db_path, 'w', encoding='utf-8') as f:
                json.dump(links, f, indent=2, ensure_ascii=False)
    
    def load_links(self, channel_entity) -> List[Dict]:
        """Load link data for a channel"""
        db_path = self.get_link_db_path(channel_entity)
        if not db_path.exists():
            return []
        with self._get_lock(str(db_path)):
            with open(db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    
    def get_all_links(self) -> List[Dict]:
        """Load all links from all channels"""
        all_links = []
        for db_path in self.links_dir.glob('*_links.json'):
            with self._get_lock(str(db_path)):
                with open(db_path, 'r', encoding='utf-8') as f:
                    all_links.extend(json.load(f))
        return all_links
    
    def add_links(self, channel_entity, new_links: List[Dict]) -> int:
        """Add new links to channel database (with deduplication)"""
        existing_links = self.load_links(channel_entity)
        existing_urls = {link['url'] for link in existing_links}
        
        added = 0
        for link in new_links:
            if link['url'] not in existing_urls:
                link['status'] = 'pending'
                link['collected_at'] = datetime.now().isoformat()
                existing_links.append(link)
                existing_urls.add(link['url'])
                added += 1
        
        if added > 0:
            self.save_links(channel_entity, existing_links)
        
        return added
    
    def mark_link_downloaded(self, link: Dict, success: bool):
        """Mark a link as downloaded in its source channel database"""
        if 'channel' not in link:
            return
        
        channel = link['channel']
        links = self.load_links(channel)
        
        for l in links:
            if l['url'] == link['url']:
                l['status'] = 'completed' if success else 'failed'
                l['downloaded_at'] = datetime.now().isoformat()
                break
        
        self.save_links(channel, links)

    def reset_links_status(self, target_status: str = 'failed', filter_text: str = '', link_type: str = '') -> int:
        """
        Reset links back to 'pending' so they get retried on next download-links run.

        Args:
            target_status: which status to reset — 'failed', 'completed', or 'all'
            filter_text:   only reset links whose caption contains this string (case-insensitive)
            link_type:     only reset links of this type ('youtube', 'drive', or '' for all)

        Returns:
            Number of links reset.
        """
        all_links_files = list(self.links_dir.glob('*_links.json'))
        total_reset = 0

        for links_file in all_links_files:
            channel_id = links_file.stem.replace('_links', '')
            links = self.load_links(channel_id)
            changed = False

            for link in links:
                current_status = link.get('status', 'pending')

                # Status filter
                if target_status != 'all' and current_status != target_status:
                    continue
                # Don't reset links that are already pending
                if current_status == 'pending':
                    continue
                # Type filter
                if link_type and link.get('type', '') != link_type:
                    continue
                # Caption filter
                if filter_text and filter_text.lower() not in link.get('caption', '').lower():
                    continue

                link['status'] = 'pending'
                link.pop('downloaded_at', None)
                total_reset += 1
                changed = True

            if changed:
                self.save_links(channel_id, links)

        return total_reset

    # Download State Management
    def get_state_path(self, filepath: Path) -> Path:
        """Get download state file path"""
        # Create a unique state filename based on the download filepath
        state_filename = f"{filepath.stem}_{hash(str(filepath))}.dlstate"
        return self.states_dir / state_filename
    
    def save_download_state(self, filepath: Path, downloaded_bytes: int, total_bytes: int):
        """Save download state for resume support"""
        state_path = self.get_state_path(filepath)
        state_data = {
            'filepath': str(filepath),
            'downloaded_bytes': downloaded_bytes,
            'total_bytes': total_bytes,
            'timestamp': datetime.now().isoformat()
        }
        
        with self._get_lock(str(state_path)):
            with open(state_path, 'w') as f:
                json.dump(state_data, f)
    
    def load_download_state(self, filepath: Path) -> Optional[Dict]:
        """Load download state if exists"""
        state_path = self.get_state_path(filepath)
        if not state_path.exists():
            return None
        
        with self._get_lock(str(state_path)):
            try:
                with open(state_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
    
    def cleanup_download_state(self, filepath: Path):
        """Remove download state file after successful download"""
        state_path = self.get_state_path(filepath)
        if state_path.exists():
            with self._get_lock(str(state_path)):
                state_path.unlink()
    
    # Statistics
    def get_statistics(self) -> Dict:
        """Get overall statistics"""
        all_videos = self.get_all_videos()
        all_links = self.get_all_links()
        
        stats = {
            'total_videos': len(all_videos),
            'total_links': len(all_links),
            'links_by_type': {},
            'links_by_status': {},
            'videos_by_category': {}
        }
        
        # Count links by type
        for link in all_links:
            link_type = link.get('type', 'unknown')
            stats['links_by_type'][link_type] = stats['links_by_type'].get(link_type, 0) + 1
            
            status = link.get('status', 'pending')
            stats['links_by_status'][status] = stats['links_by_status'].get(status, 0) + 1
        
        # Count videos by category
        for video in all_videos:
            category = video.get('category', 'Uncategorized')
            stats['videos_by_category'][category] = stats['videos_by_category'].get(category, 0) + 1
        
        return stats
