#!/usr/bin/env python3
"""
Configuration Manager for Telegram Tools Unified
Handles loading, validation, and management of configuration settings
"""

import json
import os
from pathlib import Path
from typing import Optional


class ConfigManager:
    """Manages configuration for Telegram Tools Unified"""
    
    def __init__(self, config_path: str = 'config.json'):
        self.config_path = config_path
        self.load_config()
    
    def load_config(self):
        """Load configuration from file or environment variables"""
        # Priority: Environment variables > config file > defaults
        
        # Try environment variables first (more secure)
        self.api_id = os.environ.get('TELEGRAM_API_ID', '')
        self.api_hash = os.environ.get('TELEGRAM_API_HASH', '')
        self.phone = os.environ.get('TELEGRAM_PHONE', '')
        
        # Load from config file if exists
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Use config file values if env vars not set
                    if not self.api_id:
                        self.api_id = str(data.get('api_id', ''))
                    if not self.api_hash:
                        self.api_hash = data.get('api_hash', '')
                    if not self.phone:
                        self.phone = data.get('phone', '')
                    
                    # Load other settings
                    self.download_path = data.get('download_path', 'downloads')
                    self.max_parallel = data.get('max_parallel_downloads', 3)
                    self.chunk_size = data.get('chunk_size_kb', 512) * 1024
                    self.max_retries = data.get('max_retries', 5)
                    self.retry_delay = data.get('retry_delay_seconds', 3)
                    self.size_warning_mb = data.get('size_warning_mb', 500)
                    self.session_name = data.get('session_name', 'telegram_session')
                    self.connection_timeout = data.get('connection_timeout_seconds', 30)
                    
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️  Warning: Error reading config file: {e}")
                self._set_defaults()
        else:
            # No config file, check if we have env vars
            if not (self.api_id and self.api_hash and self.phone):
                print(f"❌ Error: {self.config_path} not found!")
                print("\nCreate a config.json file with:")
                print(json.dumps({
                    "api_id": "YOUR_API_ID",
                    "api_hash": "YOUR_API_HASH",
                    "phone": "+1234567890"
                }, indent=2))
                print("\nOr set environment variables:")
                print("  TELEGRAM_API_ID")
                print("  TELEGRAM_API_HASH")
                print("  TELEGRAM_PHONE")
                raise FileNotFoundError(f"Configuration file {self.config_path} not found")
            
            self._set_defaults()
    
    def _set_defaults(self):
        """Set default values for optional settings"""
        if not hasattr(self, 'download_path'):
            self.download_path = 'downloads'
        if not hasattr(self, 'max_parallel'):
            self.max_parallel = 3
        if not hasattr(self, 'chunk_size'):
            self.chunk_size = 512 * 1024
        if not hasattr(self, 'max_retries'):
            self.max_retries = 5
        if not hasattr(self, 'retry_delay'):
            self.retry_delay = 3
        if not hasattr(self, 'size_warning_mb'):
            self.size_warning_mb = 500
        if not hasattr(self, 'session_name'):
            self.session_name = 'telegram_session'
        if not hasattr(self, 'connection_timeout'):
            self.connection_timeout = 30
    
    def validate(self) -> bool:
        """Validate that required configuration is present"""
        if not self.api_id or not self.api_hash or not self.phone:
            print("❌ Error: Missing required configuration!")
            print("Required: api_id, api_hash, phone")
            return False
        
        # Validate types and ranges
        try:
            int(self.api_id)
        except ValueError:
            print("❌ Error: api_id must be a number")
            return False
        
        if not self.phone.startswith('+'):
            print("⚠️  Warning: Phone number should start with + and country code")
        
        if self.max_parallel < 1 or self.max_parallel > 10:
            print("⚠️  Warning: max_parallel_downloads should be between 1 and 10")
            self.max_parallel = max(1, min(10, self.max_parallel))
        
        return True
    
    def save_config(self):
        """Save current configuration to file"""
        data = {
            'api_id': self.api_id,
            'api_hash': self.api_hash,
            'phone': self.phone,
            'download_path': self.download_path,
            'max_parallel_downloads': self.max_parallel,
            'chunk_size_kb': self.chunk_size // 1024,
            'max_retries': self.max_retries,
            'retry_delay_seconds': self.retry_delay,
            'size_warning_mb': self.size_warning_mb,
            'session_name': self.session_name,
            'connection_timeout_seconds': self.connection_timeout
        }
        
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Configuration saved to {self.config_path}")
        except IOError as e:
            print(f"❌ Error saving configuration: {e}")
    
    def update_setting(self, key: str, value):
        """Update a single configuration setting"""
        valid_settings = {
            'download_path': str,
            'max_parallel_downloads': int,
            'chunk_size_kb': int,
            'max_retries': int,
            'retry_delay_seconds': int,
            'size_warning_mb': int,
            'connection_timeout_seconds': int
        }
        
        if key not in valid_settings:
            print(f"❌ Error: Unknown setting '{key}'")
            print(f"Valid settings: {', '.join(valid_settings.keys())}")
            return False
        
        try:
            # Convert to appropriate type
            typed_value = valid_settings[key](value)
            
            # Map to internal attribute names
            attr_map = {
                'download_path': 'download_path',
                'max_parallel_downloads': 'max_parallel',
                'chunk_size_kb': 'chunk_size',
                'max_retries': 'max_retries',
                'retry_delay_seconds': 'retry_delay',
                'size_warning_mb': 'size_warning_mb',
                'connection_timeout_seconds': 'connection_timeout'
            }
            
            attr_name = attr_map[key]
            
            # Special handling for chunk_size (stored in bytes internally)
            if key == 'chunk_size_kb':
                setattr(self, attr_name, typed_value * 1024)
            else:
                setattr(self, attr_name, typed_value)
            
            print(f"✅ Updated {key} = {typed_value}")
            return True
            
        except ValueError:
            print(f"❌ Error: Invalid value for {key} (expected {valid_settings[key].__name__})")
            return False
    
    def show_config(self):
        """Display current configuration"""
        print("\n" + "="*60)
        print("CURRENT CONFIGURATION")
        print("="*60)
        print(f"API ID:              {self.api_id}")
        print(f"API Hash:            {self.api_hash[:8]}..." if self.api_hash else "API Hash:            (not set)")
        print(f"Phone:               {self.phone}")
        print(f"Download Path:       {self.download_path}")
        print(f"Max Parallel:        {self.max_parallel}")
        print(f"Chunk Size:          {self.chunk_size // 1024} KB")
        print(f"Max Retries:         {self.max_retries}")
        print(f"Retry Delay:         {self.retry_delay}s")
        print(f"Size Warning:        {self.size_warning_mb} MB")
        print(f"Session Name:        {self.session_name}")
        print(f"Connection Timeout:  {self.connection_timeout}s")
        print("="*60 + "\n")
