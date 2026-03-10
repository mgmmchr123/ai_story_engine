"""
AI Storytelling Engine - Main Package
"""

__version__ = "1.0.0"
__author__ = "AI Storyteller"
__description__ = "Convert stories into illustrated scenes with narration and background music"

from models.scene_schema import StoryContent, Scene, PipelineOutput
from pipeline.story_parser import parse_story
from ui.story_player import StoryPlayer

__all__ = [
    "StoryContent",
    "Scene",
    "PipelineOutput",
    "parse_story",
    "StoryPlayer"
]
