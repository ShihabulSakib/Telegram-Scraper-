#!/usr/bin/env python3
"""
Chapter Classifier for Telegram Tools Unified
Intelligent video classification based on channel message patterns,
checkpoints, captions, and fuzzy matching with confidence scoring.
"""

import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime
from collections import defaultdict

try:
    import Levenshtein
except ImportError:
    Levenshtein = None


@dataclass
class VideoClassification:
    """Structured output for video classification"""
    video_id: str
    message_id: str
    date_utc: str
    caption_text: str
    filename: str
    size: int
    
    chapter_name: str
    chapter_source: str  # "checkpoint" | "caption_inference" | "propagated"
    ordinal_within_chapter: Optional[int]
    confidence: float  # 0.0 - 1.0
    
    duplicate: bool
    notes: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


class FuzzyMatcher:
    """Handles fuzzy/similarity matching between texts"""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for matching"""
        if not text:
            return ""
        # Lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove common punctuation
        text = re.sub(r'[।,.:;!?\-_\[\](){}"\']+', ' ', text)
        return text.strip()
    
    @staticmethod
    def extract_tokens(text: str) -> Set[str]:
        """Extract meaningful tokens from text"""
        normalized = FuzzyMatcher.normalize_text(text)
        tokens = set(normalized.split())
        # Remove very short tokens and numbers
        return {t for t in tokens if len(t) > 1 and not t.isdigit()}
    
    @staticmethod
    def token_overlap_score(text1: str, text2: str) -> float:
        """Calculate token overlap ratio"""
        tokens1 = FuzzyMatcher.extract_tokens(text1)
        tokens2 = FuzzyMatcher.extract_tokens(text2)
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        
        return len(intersection) / len(union) if union else 0.0
    
    @staticmethod
    def levenshtein_similarity(text1: str, text2: str) -> float:
        """Calculate normalized Levenshtein similarity"""
        if not Levenshtein:
            return FuzzyMatcher.token_overlap_score(text1, text2)
        
        t1 = FuzzyMatcher.normalize_text(text1)
        t2 = FuzzyMatcher.normalize_text(text2)
        
        if not t1 or not t2:
            return 0.0
        
        distance = Levenshtein.distance(t1, t2)
        max_len = max(len(t1), len(t2))
        
        return 1 - (distance / max_len) if max_len > 0 else 0.0
    
    @staticmethod
    def combined_similarity(text1: str, text2: str) -> float:
        """Combined similarity score using multiple methods"""
        token_score = FuzzyMatcher.token_overlap_score(text1, text2)
        lev_score = FuzzyMatcher.levenshtein_similarity(text1, text2)
        
        # Weight token overlap higher for topic matching
        return 0.6 * token_score + 0.4 * lev_score


class CaptionAnalyzer:
    """Analyzes video captions to extract chapter information"""
    
    # Chapter indicator keywords (multilingual)
    CHAPTER_KEYWORDS = [
        # English
        'chapter', 'ch', 'lecture', 'lec', 'part', 'module', 'unit', 
        'section', 'lesson', 'episode', 'ep', 'session', 'class',
        # Bengali
        'পাঠ', 'অধ্যায়', 'পর্ব', 'মডিউল', 'ইউনিট', 'লেকচার', 
        'সেশন', 'ক্লাস', 'পার্ট'
    ]
    
    # Ordinal patterns (multilingual)
    ORDINAL_PATTERNS = [
        # English patterns
        r'(?:lecture|lec|lect)\s*[\-:.]?\s*(\d+)',
        r'(?:part|pt)\s*[\-:.]?\s*(\d+)',
        r'(?:episode|ep)\s*[\-:.]?\s*(\d+)',
        r'(?:chapter|ch)\s*[\-:.]?\s*(\d+)',
        r'(?:class|session)\s*[\-:.]?\s*(\d+)',
        # Bengali patterns
        r'পর্ব\s*[\-:.]?\s*(\d+)',
        r'লেকচার\s*[\-:.]?\s*(\d+)',
        r'অধ্যায়\s*[\-:.]?\s*(\d+)',
        r'পাঠ\s*[\-:.]?\s*(\d+)',
        # Bengali numerals
        r'পর্ব\s*[\-:.]?\s*([০-৯]+)',
        # Generic number at start or standalone
        r'^(\d+)[\s\.\-:]',
        r'\b(\d+)(?:st|nd|rd|th)\b',
    ]

    # Patterns to strip when cleaning chapter names (don't strip Chapter/Unit/Module)
    CLEANING_PATTERNS = [
        r'(?:lecture|lec|lect)\s*[\-:.]?\s*(\d+)',
        r'(?:part|pt)\s*[\-:.]?\s*(\d+)',
        r'(?:class|session)\s*[\-:.]?\s*(\d+)',
        r'পর্ব\s*[\-:.]?\s*(\d+)',
        r'লেকচার\s*[\-:.]?\s*(\d+)',
        r'পাঠ\s*[\-:.]?\s*(\d+)',
    ]
    
    @staticmethod
    def bengali_to_english_num(text: str) -> str:
        """Convert Bengali numerals to English"""
        bengali_nums = '০১২৩৪৫৬৭৮৯'
        english_nums = '0123456789'
        for b, e in zip(bengali_nums, english_nums):
            text = text.replace(b, e)
        return text
    
    @classmethod
    def extract_ordinal(cls, text: str) -> Optional[int]:
        """Extract ordinal number from caption"""
        if not text:
            return None
        
        text_normalized = cls.bengali_to_english_num(text.lower())
        
        for pattern in cls.ORDINAL_PATTERNS:
            match = re.search(pattern, text_normalized, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        
        return None
    
    @classmethod
    def has_chapter_keyword(cls, text: str) -> bool:
        """Check if text contains chapter-related keywords"""
        if not text:
            return False
        
        text_lower = text.lower()
        return any(kw in text_lower for kw in cls.CHAPTER_KEYWORDS)
    
    @classmethod
    def clean_chapter_name(cls, text: str) -> str:
        """Remove ordinal patterns from chapter name to get the base topic"""
        if not text:
            return ""
        
        # Remove ordinals like "Lecture 32", "Part 1", "পর্ব ১"
        cleaned = text
        for pattern in cls.CLEANING_PATTERNS:
            # Replace with empty string, but keep the text before it
            # We want "Organic Chemistry Lecture 32" -> "Organic Chemistry"
            # But the pattern matches "Lecture 32".
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Remove specific separate numbers that might remain at END of string
        # e.g. "Physics 1" -> "Physics" (maybe?) No, "Physics 1" is a paper.
        # "Chapter 4 2" (where 2 is lecture) -> "Chapter 4"
        # Be careful not to remove "Chapter 4"
        
        # Clean up whitespace and punctuation
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        cleaned = re.sub(r'[\-:|]+$', '', cleaned).strip()
        
        return cleaned

    @classmethod
    def extract_potential_chapter_name(cls, text: str) -> Optional[str]:
        """Extract potential chapter name from text"""
        if not text:
            return None
        
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        
        # Get first line or first sentence
        lines = text.strip().split('\n')
        first_line = lines[0].strip() if lines else text
        
        # Clean up
        first_line = re.sub(r'\s+', ' ', first_line)
        
        # Limit length
        if len(first_line) > 100:
            first_line = first_line[:100]
        
        return first_line if first_line else None


class CheckpointDetector:
    """Detects chapter indicator/checkpoint messages"""
    
    # Strong indicator phrases
    CHECKPOINT_PHRASES = [
        r'chapter\s*\d*\s*(?:starts?|begins?)',
        r'(?:starting|beginning)\s+chapter',
        r'অধ্যায়\s*\d*\s*শুরু',
        r'পর্ব\s*\d*\s*শুরু',
        r'শুরু\s+হচ্ছে',
        r'আজকের?\s+(?:টপিক|বিষয়)',
        r'new\s+(?:topic|chapter|section)',
    ]
    
    @classmethod
    def is_checkpoint_message(cls, text: str, has_media: bool) -> Tuple[bool, float]:
        """
        Determine if a message is a chapter checkpoint.
        Returns (is_checkpoint, confidence)
        """
        if not text or has_media:
            return False, 0.0
        
        text_lower = text.lower()
        
        # Check for strong indicator phrases
        for phrase in cls.CHECKPOINT_PHRASES:
            if re.search(phrase, text_lower, re.IGNORECASE):
                return True, 0.95
        
        # Check for chapter keywords with numbers
        if CaptionAnalyzer.has_chapter_keyword(text):
            # If it's a short message with chapter keyword, likely a checkpoint
            if len(text) < 200:
                return True, 0.80
            return True, 0.60
        
        return False, 0.0
    
    @classmethod
    def extract_chapter_from_checkpoint(cls, text: str, known_chapters: List[str]) -> Tuple[str, float]:
        """
        Extract chapter name from checkpoint message.
        Returns (chapter_name, confidence)
        """
        if not text:
            return "Unknown", 0.0
        
        # Try to match against known chapters first
        best_match = None
        best_score = 0.0
        
        for chapter in known_chapters:
            score = FuzzyMatcher.combined_similarity(text, chapter)
            if score > best_score and score > 0.4:
                best_score = score
                best_match = chapter
        
        if best_match:
            return best_match, min(0.95, best_score + 0.2)
        
        # Extract from text
        chapter_name = CaptionAnalyzer.extract_potential_chapter_name(text)
        if chapter_name:
            return chapter_name, 0.70
        
        return "Unknown", 0.30


class ChapterClassifier:
    """Main classification engine for videos"""
    
    def __init__(self):
        self.known_chapters: List[str] = []
        self.checkpoints: List[Dict] = []
        self.last_checkpoint_chapter: Optional[str] = None
        self.last_checkpoint_index: int = -1
        self.seen_videos: Dict[str, VideoClassification] = {}
    
    def extract_chapters_from_intro(self, messages: List[Dict]) -> List[str]:
        """Extract chapter list from intro message if present"""
        if not messages:
            return []
        
        # Check first few messages for intro with chapter list
        chapters = []
        
        for msg in messages[:5]:  # Check first 5 messages
            text = msg.get('text', '') or msg.get('caption', '')
            if not text:
                continue
            
            # Look for numbered lists or bullet points
            lines = text.split('\n')
            potential_chapters = []
            
            for line in lines:
                line = line.strip()
                # Check for numbered items like "1. Chapter Name" or "১। অধ্যায়"
                if re.match(r'^[\d০-৯]+[\.:\)\-।]\s*\S', line):
                    # Extract the chapter name part
                    chapter_text = re.sub(r'^[\d০-৯]+[\.:\)\-।]\s*', '', line)
                    if len(chapter_text) > 3:
                        potential_chapters.append(chapter_text.strip())
                # Check for bullet points
                elif re.match(r'^[•\-\*]\s*\S', line):
                    chapter_text = re.sub(r'^[•\-\*]\s*', '', line)
                    if len(chapter_text) > 3:
                        potential_chapters.append(chapter_text.strip())
            
            if len(potential_chapters) >= 3:  # At least 3 items suggests a list
                chapters.extend(potential_chapters)
                break
        
        self.known_chapters = list(set(chapters))
        return self.known_chapters
    
    def classify_video(self, video: Dict, all_messages: List[Dict], 
                       video_index: int) -> VideoClassification:
        """Classify a single video"""
        
        video_id = str(video.get('msg_id', ''))
        message_id = video_id
        caption = video.get('caption', '') or ''
        filename = video.get('filename', '')
        size = video.get('size', 0)
        date = video.get('date', '')
        
        # Check for duplicates
        video_key = f"{video_id}_{filename}"
        if video_key in self.seen_videos:
            existing = self.seen_videos[video_key]
            return VideoClassification(
                video_id=video_id,
                message_id=message_id,
                date_utc=date,
                caption_text=caption[:500],
                filename=filename,
                size=size,
                chapter_name=existing.chapter_name,
                chapter_source="propagated",
                ordinal_within_chapter=existing.ordinal_within_chapter,
                confidence=0.30,
                duplicate=True,
                notes=f"Duplicate of {existing.video_id}"
            )
        
        # 1. Check for checkpoint before this video
        checkpoint_chapter, checkpoint_conf = self._find_preceding_checkpoint(
            all_messages, video_index
        )
        
        # 2. Analyze caption for chapter info
        caption_chapter, caption_conf = self._analyze_caption_for_chapter(caption)
        
        # 3. Extract ordinal
        ordinal = CaptionAnalyzer.extract_ordinal(caption) or \
                  CaptionAnalyzer.extract_ordinal(filename)
        
        # 4. Determine final chapter assignment
        if checkpoint_conf > caption_conf and checkpoint_conf > 0.5:
            chapter_name = checkpoint_chapter
            chapter_source = "checkpoint"
            confidence = checkpoint_conf
        elif caption_conf > 0.5:
            chapter_name = caption_chapter
            chapter_source = "caption_inference"
            confidence = caption_conf
        elif self.last_checkpoint_chapter:
            chapter_name = self.last_checkpoint_chapter
            chapter_source = "propagated"
            # Confidence decreases with distance from checkpoint
            distance = video_index - self.last_checkpoint_index
            confidence = max(0.20, 0.60 - (distance * 0.05))
        else:
            chapter_name = self._infer_chapter_from_content(caption, filename)
            chapter_source = "caption_inference"
            confidence = 0.40
        
        # Generate notes
        notes = self._generate_notes(caption_chapter, checkpoint_chapter, 
                                     caption_conf, checkpoint_conf)
        
        classification = VideoClassification(
            video_id=video_id,
            message_id=message_id,
            date_utc=date,
            caption_text=caption[:500],
            filename=filename,
            size=size,
            chapter_name=chapter_name,
            chapter_source=chapter_source,
            ordinal_within_chapter=ordinal,
            confidence=round(confidence, 2),
            duplicate=False,
            notes=notes[:200]
        )
        
        self.seen_videos[video_key] = classification
        return classification
    
    def _find_preceding_checkpoint(self, messages: List[Dict], 
                                   video_index: int) -> Tuple[str, float]:
        """Find checkpoint message preceding this video"""
        # Look at messages before this video
        for i in range(video_index - 1, max(-1, video_index - 10), -1):
            if i < 0 or i >= len(messages):
                continue
            
            msg = messages[i]
            text = msg.get('text', '') or msg.get('caption', '')
            has_media = msg.get('has_video', False) or msg.get('has_media', False)
            
            is_checkpoint, conf = CheckpointDetector.is_checkpoint_message(
                text, has_media
            )
            
            if is_checkpoint:
                chapter, ch_conf = CheckpointDetector.extract_chapter_from_checkpoint(
                    text, self.known_chapters
                )
                self.last_checkpoint_chapter = chapter
                self.last_checkpoint_index = i
                return chapter, min(conf, ch_conf)
        
        return "", 0.0
    
    def _analyze_caption_for_chapter(self, caption: str) -> Tuple[str, float]:
        """Analyze caption to determine chapter"""
        if not caption:
            return "", 0.0
        
        # Try matching against known chapters
        if self.known_chapters:
            best_match = None
            best_score = 0.0
            
            for chapter in self.known_chapters:
                score = FuzzyMatcher.combined_similarity(caption, chapter)
                if score > best_score:
                    best_score = score
                    best_match = chapter
            
            if best_match and best_score > 0.35:
                return best_match, min(0.90, best_score + 0.3)
        
        # Extract chapter name from caption
        potential_name = CaptionAnalyzer.extract_potential_chapter_name(caption)
        if potential_name:
            # Clean it to remove "Lecture X" parts
            cleaned_name = CaptionAnalyzer.clean_chapter_name(potential_name)
            
            # Check if it has chapter-like keywords
            if CaptionAnalyzer.has_chapter_keyword(caption):
                # If we have a clean name, use it
                if len(cleaned_name) > 3:
                     return cleaned_name, 0.75
                return potential_name, 0.75
            
            # Use clean name if reasonable length
            if len(cleaned_name) > 3:
                return cleaned_name, 0.55
            return potential_name, 0.55
        
        return "", 0.0
    
    def _infer_chapter_from_content(self, caption: str, filename: str) -> str:
        """Infer chapter from caption or filename when no clear match"""
        content = f"{caption} {filename}"
        
        # Extract meaningful words
        words = FuzzyMatcher.extract_tokens(content)
        
        # Remove common noise words
        noise = {'video', 'mp4', 'mkv', 'lecture', 'lec', 'part', 'ep',
                 'class', 'session', 'পর্ব', 'লেকচার', 'ভিডিও',
                 'pdf', 'drive', 'google', 'link', 'https', 'http', 'com',
                 'file', 'download', 'click', 'here', 'join', 'channel',
                 'note', 'notes', 'slide', 'slides', 'sheet', 'sheets',
                 'no'}
        meaningful = [w for w in words if w not in noise and len(w) > 2]
        
        if meaningful:
            # Use first meaningful word as chapter
            # Check if there are consequent meaningful words that form a phrase
            # For now, just taking the first one or two might be better?
            # Let's try to capture multi-word topics if possible, but keep it simple
            return meaningful[0].capitalize()
        
        return "Uncategorized"
    
    def _generate_notes(self, caption_ch: str, checkpoint_ch: str,
                        caption_conf: float, checkpoint_conf: float) -> str:
        """Generate notes about classification decision"""
        notes = []
        
        if checkpoint_ch and caption_ch and checkpoint_ch != caption_ch:
            notes.append(f"Conflict: checkpoint='{checkpoint_ch}' vs caption='{caption_ch}'")
        
        if caption_conf < 0.5 and checkpoint_conf < 0.5:
            notes.append("Low confidence - inferred from context")
        
        return "; ".join(notes) if notes else ""
    
    def classify_all(self, messages: List[Dict], videos: List[Dict]) -> List[VideoClassification]:
        """Classify all videos from a channel"""
        
        # Reset state
        self.checkpoints = []
        self.last_checkpoint_chapter = None
        self.last_checkpoint_index = -1
        self.seen_videos = {}
        
        # Extract known chapters from intro
        self.extract_chapters_from_intro(messages)
        
        # Create message index for videos
        video_msg_ids = {v['msg_id'] for v in videos}
        
        # Build combined message list with video info
        combined = []
        for i, msg in enumerate(messages):
            msg_copy = dict(msg)
            msg_copy['_index'] = i
            msg_copy['has_video'] = msg.get('msg_id') in video_msg_ids
            combined.append(msg_copy)
        
        # Sort by date (oldest first) for proper checkpoint propagation
        combined.sort(key=lambda x: x.get('date', ''))
        
        # Classify each video
        results = []
        for video in videos:
            # Find video's position in message list
            video_index = next(
                (i for i, m in enumerate(combined) if m.get('msg_id') == video.get('msg_id')),
                len(combined) - 1
            )
            
            classification = self.classify_video(video, combined, video_index)
            results.append(classification)
        
        return results
