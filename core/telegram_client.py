#!/usr/bin/env python3
"""
Telegram Client Wrapper for Telegram Tools Unified
Handles connection, authentication, and basic Telegram operations
"""

import asyncio
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError, TimeoutError as TelethonTimeoutError
from typing import Optional, List


class TelegramClientWrapper:
    """Wrapper around Telethon client with error handling and reconnection"""
    
    def __init__(self, config):
        self.config = config
        self.client = None
        self.connected = False
    
    async def connect(self) -> bool:
        """Connect to Telegram with authentication"""
        try:
            self.client = TelegramClient(
                self.config.session_name,
                self.config.api_id,
                self.config.api_hash,
                timeout=self.config.connection_timeout,
                connection_retries=5,
                retry_delay=2
            )
            
            await self.client.start(phone=self.config.phone)
            
            if not await self.client.is_user_authorized():
                await self.client.send_code_request(self.config.phone)
                try:
                    code = input('Enter verification code: ')
                    await self.client.sign_in(self.config.phone, code)
                except SessionPasswordNeededError:
                    password = input('Enter 2FA password: ')
                    await self.client.sign_in(password=password)
            
            self.connected = True
            print("✅ Connected to Telegram")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connected = False
            return False
    
    async def reconnect(self) -> bool:
        """Reconnect to Telegram after connection loss"""
        print("🔄 Reconnecting...")
        try:
            if self.client:
                await self.client.disconnect()
            await asyncio.sleep(2)
            return await self.connect()
        except Exception as e:
            print(f"❌ Reconnection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from Telegram"""
        if self.client and self.connected:
            await self.client.disconnect()
            self.connected = False
            print("✅ Disconnected from Telegram")
    
    async def get_dialogs(self):
        """Get all dialogs (channels, groups, chats)"""
        if not self.connected:
            await self.connect()
        return await self.client.get_dialogs()
    
    async def get_entity(self, channel):
        """Get entity for a channel/group"""
        if not self.connected:
            await self.connect()
        return await self.client.get_entity(channel)
    
    async def iter_messages(self, entity, limit=None):
        """Iterate through messages in a channel/group"""
        if not self.connected:
            await self.connect()
        async for message in self.client.iter_messages(entity, limit=limit):
            yield message
    
    async def get_messages(self, entity, ids):
        """Get specific messages by ID"""
        if not self.connected:
            await self.connect()
        return await self.client.get_messages(entity, ids=ids)
    
    async def download_media(self, message, file, progress_callback=None):
        """Download media from a message"""
        if not self.connected:
            await self.connect()
        return await self.client.download_media(
            message,
            file=file,
            progress_callback=progress_callback
        )
