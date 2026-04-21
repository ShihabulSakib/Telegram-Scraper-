#!/usr/bin/env python3
"""
Link Scanner for Telegram Tools Unified
Scans Telegram channels for external links (YouTube, Google Drive)
"""

import re
from typing import List, Dict, Optional
from telethon.tl.types import Message


class LinkScanner:
    """Scan Telegram channels for external links"""
    
    YOUTUBE_PATTERNS = [
        r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
        r'(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=[\w-]+',
    ]
    
    DRIVE_PATTERNS = [
        r'(?:https?://)?drive\.google\.com/file/d/[\w-]+',
        r'(?:https?://)?drive\.google\.com/drive/folders/[\w-]+',
        r'(?:https?://)?drive\.google\.com/open\?id=[\w-]+',
    ]
    
    def __init__(self, telegram_client, data_manager):
        self.client = telegram_client
        self.data_manager = data_manager
    
    def extract_links(self, text: str) -> List[Dict[str, str]]:
        """Extract all supported links from text"""
        if not text:
            return []
        
        links = []
        
        # Extract YouTube links
        for pattern in self.YOUTUBE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                links.append({'url': match.group(0), 'type': 'youtube'})
        
        # Extract Google Drive links
        for pattern in self.DRIVE_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                links.append({'url': match.group(0), 'type': 'drive'})
        
        return links
    
    async def scan_channel(self, channel, limit: Optional[int] = None) -> List[Dict]:
        """Scan a channel for external links"""
        print(f"\n🔍 Scanning '{channel}' for links...")
        print(f"Limit: {limit if limit else 'All messages'}")
        
        collected = []
        count = 0
        
        try:
            entity = await self.client.get_entity(channel)
            
            async for message in self.client.iter_messages(entity, limit=limit):
                if not isinstance(message, Message):
                    continue
                
                count += 1
                if count % 100 == 0:
                    print(f"  Scanned {count} messages, found {len(collected)} links...")
                
                text = message.text or message.message or ''
                links = self.extract_links(text)
                
                if links:
                    for link in links:
                        collected.append({
                            'url': link['url'],
                            'type': link['type'],
                            'caption': text[:500],  # First 500 chars
                            'date': message.date.isoformat(),
                            'message_id': message.id,
                            'channel': str(channel),
                            'sender': getattr(message.sender, 'username', 'unknown') if message.sender else 'unknown'
                        })
            
            print(f"\n✅ Scan complete: {count} messages scanned, {len(collected)} links found")
            
            # Add to database
            if collected:
                added = self.data_manager.add_links(channel, collected)
                print(f"✅ Added {added} new links to database")
                print(f"📊 Total links for this channel: {len(self.data_manager.load_links(channel))}")
            
            return collected
            
        except Exception as e:
            print(f"❌ Error scanning channel: {e}")
            return collected
