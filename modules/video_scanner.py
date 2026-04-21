#!/usr/bin/env python3
"""
Video Scanner for Telegram Tools Unified
Scans Telegram channels for videos with intelligent categorization
"""

import re
import Levenshtein
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Set, Optional
from telethon.tl.types import MessageMediaDocument, DocumentAttributeVideo, DocumentAttributeFilename
from .chapter_classifier import ChapterClassifier


class VideoScanner:
    """Scan Telegram channels for videos and categorize them intelligently"""
    
    def __init__(self, telegram_client, data_manager):
        self.client = telegram_client
        self.data_manager = data_manager
    
    async def scan_channel(self, channel, limit: Optional[int] = None) -> List[Dict]:
        """Scan a channel for video messages and classify them"""
        print(f"\n🔍 Scanning '{channel}' for videos...")
        
        videos = []
        all_messages = []
        count = 0
        
        try:
            entity = await self.client.get_entity(channel)
            
            # First pass: Collect messages and raw video data
            async for message in self.client.iter_messages(entity, limit=limit):
                count += 1
                if count % 50 == 0:
                    print(f"  Scanned {count} messages, found {len(videos)} videos...")
                
                # Store lightweight message info for context analysis
                msg_info = {
                    'msg_id': message.id,
                    'text': message.text or message.message or "",
                    'date': message.date.isoformat(),
                    'has_media': bool(message.media),
                    'has_video': False
                }
                
                if message.media and isinstance(message.media, MessageMediaDocument):
                    doc = message.media.document
                    is_video = any(isinstance(attr, DocumentAttributeVideo) for attr in doc.attributes)
                    
                    if is_video:
                        msg_info['has_video'] = True
                        filename = None
                        for attr in doc.attributes:
                            if isinstance(attr, DocumentAttributeFilename):
                                filename = attr.file_name
                                break
                        
                        if not filename:
                            filename = f"video_{message.id}.mp4"
                        
                        # Extract caption/text
                        caption = message.text or message.message or ""
                        
                        video_data = {
                            'msg_id': message.id,
                            'filename': filename,
                            'size': doc.size,
                            'date': message.date.isoformat(),
                            'caption': caption,
                            'channel': str(channel),
                            'category': None  # Will be set by classifier
                        }
                        videos.append(video_data)
                
                all_messages.append(msg_info)
            
            print(f"\n✅ Found {len(videos)} videos in {count} messages")
            
            # Second pass: Intelligent Classification
            if videos:
                print("\n🤖 Running intelligent classification...")
                classifier = ChapterClassifier()
                classified_results = classifier.classify_all(all_messages, videos)
                
                # Convert back to dictionary format expected by data manager
                final_videos = []
                for v_cls, v_raw in zip(classified_results, videos):
                    v_dict = v_raw.copy()
                    v_dict.update({
                        'category': v_cls.chapter_name,
                        'chapter_source': v_cls.chapter_source,
                        'ordinal': v_cls.ordinal_within_chapter,
                        'confidence': v_cls.confidence,
                        'notes': v_cls.notes
                    })
                    final_videos.append(v_dict)
                
                # Statistics
                categories = defaultdict(int)
                for v in final_videos:
                    categories[v['category']] += 1
                
                print(f"✅ Classified into {len(categories)} chapters")
                for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:5]:
                    print(f"  • {cat}: {count}")
                if len(categories) > 5:
                    print(f"  ... and {len(categories)-5} more")

                # Save to database
                self.data_manager.save_videos(channel, final_videos)
                return final_videos
            
            return videos
            
        except Exception as e:
            print(f"❌ Error scanning channel: {e}")
            import traceback
            traceback.print_exc()
            return videos
    
    # Legacy methods kept for reference but unused
    def extract_keywords(self, text: str) -> Set[str]:
        """Extract meaningful keywords from text"""
        text_lower = text.lower()
        # Remove file extensions
        text_lower = re.sub(r'\.(mp4|avi|mkv|mov|webm)$', '', text_lower)
        
        # Noise words to ignore
        noise = {
            'lec', 'lecture', 'part', 'ep', 'episode', 'video', 'class', 
            'session', 'chapter', 'lesson', 'the', 'and', 'of', 'in', 'to',
            'for', 'with', 'on', 'at', 'from', 'by', 'about', 'as', 'into'
        }
        
        # Split on common separators
        words = re.split(r'[\s\-_\.]+', text_lower)
        
        # Filter out noise, numbers, and short words
        keywords = {
            w for w in words 
            if w and not w.isdigit() and w not in noise and len(w) > 2
        }
        
        return keywords
    
    def find_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        dist = Levenshtein.distance(text1.lower(), text2.lower())
        max_len = max(len(text1), len(text2))
        return 1 - (dist / max_len) if max_len > 0 else 1.0
    
    def extract_number(self, text: str) -> Optional[int]:
        """Extract lecture/episode number from text"""
        patterns = [
            r'lec(?:ture)?[\s\-_]*(\d+)',
            r'part[\s\-_]*(\d+)',
            r'ep(?:isode)?[\s\-_]*(\d+)',
            r'class[\s\-_]*(\d+)',
            r'session[\s\-_]*(\d+)',
            r'chapter[\s\-_]*(\d+)',
            r'\b(\d+)\b'  # Any standalone number
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return int(match.group(1))
        return None
    
    def auto_categorize(self, videos: List[Dict]) -> List[Dict]:
        """Intelligently categorize videos using filenames and captions"""
        print("\n🤖 Auto-categorizing videos...")
        
        categorized_ids = set()
        categories = defaultdict(list)
        
        for i, video in enumerate(videos):
            if video['msg_id'] in categorized_ids:
                continue
            
            # Combine filename and caption for better categorization
            combined_text = f"{video['filename']} {video['caption']}"
            keywords1 = self.extract_keywords(combined_text)
            
            if not keywords1:
                video['category'] = 'Uncategorized'
                categorized_ids.add(video['msg_id'])
                continue
            
            # Find similar videos
            group = [video]
            categorized_ids.add(video['msg_id'])
            
            for other in videos:
                if other['msg_id'] in categorized_ids:
                    continue
                
                other_combined = f"{other['filename']} {other['caption']}"
                keywords2 = self.extract_keywords(other_combined)
                
                if keywords1 and keywords2:
                    # Check keyword overlap
                    overlap = len(keywords1 & keywords2)
                    # Check text similarity
                    similarity = self.find_similarity(combined_text, other_combined)
                    
                    if overlap >= 2 or similarity > 0.6:
                        group.append(other)
                        categorized_ids.add(other['msg_id'])
            
            # Determine category name
            if len(group) > 1:
                # Use most common meaningful keyword
                category_name = min(keywords1, key=len).capitalize() if keywords1 else f"Group_{i+1}"
                
                # Sort group by number if present, then by date
                group.sort(key=lambda v: (
                    self.extract_number(f"{v['filename']} {v['caption']}") or 999,
                    v['date']
                ))
                
                for vid in group:
                    vid['category'] = category_name
                    categories[category_name].append(vid)
            else:
                video['category'] = 'Uncategorized'
        
        print(f"✅ Created {len(categories)} categories, {sum(1 for v in videos if v['category'] == 'Uncategorized')} uncategorized")
        
        return videos
