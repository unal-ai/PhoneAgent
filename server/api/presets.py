#!/usr/bin/env python3
"""
Presets API - Unified management for shortcuts and prompt cards

Consolidates shortcuts.py and prompt_cards.py into a single module.
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Presets"])

DATA_DIR = "data"
SHORTCUTS_FILE = os.path.join(DATA_DIR, "shortcuts.json")
PROMPT_CARDS_FILE = os.path.join(DATA_DIR, "prompt_cards.json")

os.makedirs(DATA_DIR, exist_ok=True)


# ============================================
# Generic JSON Store
# ============================================


class JSONStore:
    """Generic JSON file store with caching."""

    def __init__(self, filepath: str, cache_ttl: int = 60):
        self.filepath = filepath
        self.cache_ttl = cache_ttl
        self._cache: Optional[List[Dict]] = None
        self._cache_time = 0

    def load(self, force: bool = False) -> List[Dict]:
        """Load data with optional cache."""
        import time

        now = time.time()
        if not force and self._cache and (now - self._cache_time) < self.cache_ttl:
            return self._cache

        if not os.path.exists(self.filepath):
            return []

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
                self._cache_time = now
                return self._cache
        except Exception as e:
            logger.error(f"Failed to load {self.filepath}: {e}")
            return []

    def save(self, data: List[Dict]) -> bool:
        """Save data and update cache."""
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._cache = data
            import time

            self._cache_time = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to save {self.filepath}: {e}")
            return False


# Store instances
shortcuts_store = JSONStore(SHORTCUTS_FILE)
prompt_cards_store = JSONStore(PROMPT_CARDS_FILE)


# ============================================
# Shortcuts Models
# ============================================


class Shortcut(BaseModel):
    id: str
    title: str
    instruction: str
    category: str = "Custom"
    is_system: bool = False
    voice_keywords: List[str] = []
    created_at: str = ""
    updated_at: str = ""
    use_count: int = 0


class ShortcutCreate(BaseModel):
    title: str
    instruction: str
    category: str = "Custom"
    voice_keywords: List[str] = []


class ShortcutUpdate(BaseModel):
    title: Optional[str] = None
    instruction: Optional[str] = None
    category: Optional[str] = None
    voice_keywords: Optional[List[str]] = None


# ============================================
# Prompt Cards Models
# ============================================


class PromptCard(BaseModel):
    id: int
    title: str = Field(..., max_length=50)
    description: str = Field(..., max_length=200)
    content: str = Field(..., max_length=2000)
    category: str = "General"
    is_system: bool = False
    created_at: str = ""
    updated_at: str = ""


class PromptCardCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=2000)
    category: str = "General"


class PromptCardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None


# ============================================
# Shortcuts API
# ============================================


@router.get("/shortcuts")
def list_shortcuts(category: Optional[str] = None):
    """List all shortcuts, optionally filtered by category."""
    shortcuts = shortcuts_store.load()
    if category:
        shortcuts = [s for s in shortcuts if s.get("category") == category]
    return {"shortcuts": shortcuts, "total": len(shortcuts)}


@router.get("/shortcuts/{shortcut_id}")
def get_shortcut(shortcut_id: str):
    """Get a single shortcut by ID."""
    shortcuts = shortcuts_store.load()
    for s in shortcuts:
        if s.get("id") == shortcut_id:
            return s
    raise HTTPException(404, "Shortcut not found")


@router.post("/shortcuts")
def create_shortcut(request: ShortcutCreate):
    """Create a new shortcut."""
    import uuid

    shortcuts = shortcuts_store.load()
    now = datetime.now().isoformat()
    new_shortcut = {
        "id": str(uuid.uuid4())[:8],
        "title": request.title,
        "instruction": request.instruction,
        "category": request.category,
        "is_system": False,
        "voice_keywords": request.voice_keywords,
        "created_at": now,
        "updated_at": now,
        "use_count": 0,
    }
    shortcuts.append(new_shortcut)
    shortcuts_store.save(shortcuts)
    return new_shortcut


@router.put("/shortcuts/{shortcut_id}")
def update_shortcut(shortcut_id: str, request: ShortcutUpdate):
    """Update a shortcut."""
    shortcuts = shortcuts_store.load()
    for s in shortcuts:
        if s.get("id") == shortcut_id:
            if request.title is not None:
                s["title"] = request.title
            if request.instruction is not None:
                s["instruction"] = request.instruction
            if request.category is not None:
                s["category"] = request.category
            if request.voice_keywords is not None:
                s["voice_keywords"] = request.voice_keywords
            s["updated_at"] = datetime.now().isoformat()
            shortcuts_store.save(shortcuts)
            return s
    raise HTTPException(404, "Shortcut not found")


@router.delete("/shortcuts/{shortcut_id}")
def delete_shortcut(shortcut_id: str):
    """Delete a shortcut (system shortcuts cannot be deleted)."""
    shortcuts = shortcuts_store.load()
    for i, s in enumerate(shortcuts):
        if s.get("id") == shortcut_id:
            if s.get("is_system"):
                raise HTTPException(400, "Cannot delete system shortcut")
            shortcuts.pop(i)
            shortcuts_store.save(shortcuts)
            return {"message": "Deleted"}
    raise HTTPException(404, "Shortcut not found")


# ============================================
# Prompt Cards API
# ============================================


@router.get("/prompt-cards")
def list_prompt_cards(category: Optional[str] = None):
    """List all prompt cards, optionally filtered by category."""
    cards = prompt_cards_store.load()
    if category:
        cards = [c for c in cards if c.get("category") == category]
    return {"cards": cards, "total": len(cards)}


@router.get("/prompt-cards/{card_id}")
def get_prompt_card(card_id: int):
    """Get a single prompt card by ID."""
    cards = prompt_cards_store.load()
    for c in cards:
        if c.get("id") == card_id:
            return c
    raise HTTPException(404, "Prompt card not found")


@router.post("/prompt-cards")
def create_prompt_card(request: PromptCardCreate):
    """Create a new prompt card."""
    cards = prompt_cards_store.load()
    now = datetime.now().isoformat()
    max_id = max((c.get("id", 0) for c in cards), default=0)
    new_card = {
        "id": max_id + 1,
        "title": request.title,
        "description": request.description,
        "content": request.content,
        "category": request.category,
        "is_system": False,
        "created_at": now,
        "updated_at": now,
    }
    cards.append(new_card)
    prompt_cards_store.save(cards)
    return new_card


@router.put("/prompt-cards/{card_id}")
def update_prompt_card(card_id: int, request: PromptCardUpdate):
    """Update a prompt card."""
    cards = prompt_cards_store.load()
    for c in cards:
        if c.get("id") == card_id:
            if request.title is not None:
                c["title"] = request.title
            if request.description is not None:
                c["description"] = request.description
            if request.content is not None:
                c["content"] = request.content
            if request.category is not None:
                c["category"] = request.category
            c["updated_at"] = datetime.now().isoformat()
            prompt_cards_store.save(cards)
            return c
    raise HTTPException(404, "Prompt card not found")


@router.delete("/prompt-cards/{card_id}")
def delete_prompt_card(card_id: int):
    """Delete a prompt card (system cards cannot be deleted)."""
    cards = prompt_cards_store.load()
    for i, c in enumerate(cards):
        if c.get("id") == card_id:
            if c.get("is_system"):
                raise HTTPException(400, "Cannot delete system prompt card")
            cards.pop(i)
            prompt_cards_store.save(cards)
            return {"message": "Deleted"}
    raise HTTPException(404, "Prompt card not found")
