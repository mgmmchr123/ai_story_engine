# AI Storytelling Engine

Convert stories into illustrated scenes with narration and background music.

## Overview

The AI Storytelling Engine is a modular Python application that processes raw story text and transforms it into a multimedia experience. The engine follows a clean pipeline architecture with clear separation of concerns.

**Pipeline Flow:**
```
Story Text → Scene Parser → Illustration Generator → TTS Generator → BGM Selector → Story Player
```

## Features

- **Modular Architecture**: Each pipeline stage is a separate, independent module
- **Dataclass Models**: Type-safe data structures using Python dataclasses
- **Placeholder Integration Points**: Ready for AI model integration (OpenAI, Stable Diffusion, etc.)
- **Logging System**: Comprehensive logging at each pipeline stage
- **Story Player UI**: Interactive playback with scene navigation
- **No External Dependencies**: Uses only Python standard library (for now)

## Project Structure

```
ai_story_engine/
├── app.py                    # Main application entry point
├── config.py                 # Configuration and constants
├── __init__.py               # Package initialization
│
├── pipeline/                 # Content generation pipeline
│   ├── __init__.py
│   ├── story_parser.py       # Parse text into scenes
│   ├── prompt_builder.py     # Build AI prompts
│   ├── image_generator.py    # Generate illustrations
│   ├── tts_generator.py      # Generate narration audio
│   └── bgm_selector.py       # Select background music
│
├── models/                   # Data models
│   ├── __init__.py
│   └── scene_schema.py       # Scene and story dataclasses
│
├── ui/                       # User interface
│   ├── __init__.py
│   └── story_player.py       # Story playback player
│
├── assets/                   # Asset directories
│   ├── characters/           # Character assets
│   ├── scenes/               # Scene assets
│   ├── effects/              # Visual effects
│   └── bgm/                  # Background music files
│
└── output/                   # Generated content
    ├── images/               # Generated illustrations
    └── audio/                # Generated audio files
```

## Architecture

### Core Modules

#### 1. **Scene Schema** (`models/scene_schema.py`)
- `Scene`: Individual story scenes with metadata
- `StoryContent`: Complete story structure
- `GeneratedAssets`: Output from generation stages
- `PipelineOutput`: Final pipeline result

#### 2. **Story Parser** (`pipeline/story_parser.py`)
- Converts raw story text into structured scenes
- Placeholder for NLP-based enhancement
- Extracts characters, settings, and mood

#### 3. **Prompt Builder** (`pipeline/prompt_builder.py`)
- Generates detailed prompts for AI models
- Creates image generation prompts
- Builds narration parameters
- Generates BGM selection parameters

#### 4. **Image Generator** (`pipeline/image_generator.py`)
- Generates illustrations from text-based prompts
- Supports multiple AI models (placeholder framework)
- Image optimization and effects
- Configurable styles and quality

#### 5. **TTS Generator** (`pipeline/tts_generator.py`)
- Converts narration text to speech
- Voice profile management
- Audio normalization and speed adjustment
- Emotion-aware narration

#### 6. **BGM Selector** (`pipeline/bgm_selector.py`)
- Selects appropriate background music
- Rule-based selection engine
- Music library management
- Placeholder for AI-driven selection

#### 7. **Story Player** (`ui/story_player.py`)
- Interactive story playback interface
- Scene navigation (next, previous, jump to)
- Playback controls (play, pause, stop)
- Volume control and state management

### Configuration

Edit `config.py` to:
- Set asset directories
- Configure AI model providers
- Adjust generation parameters (resolution, audio format, etc.)
- Control logging behavior

## Installation

### Requirements
- Python 3.11+

### Setup

```bash
# Clone or navigate to the project
cd ai_story_engine

# No external dependencies needed for core functionality
# Python standard library only
```

## Usage

### Basic Usage

```python
from app import run_pipeline, play_story

# Define your story
story_text = """
The hero ventured into the forest...
A mysterious creature appeared...
"""

# Run the pipeline
output = run_pipeline(
    story_text=story_text,
    story_title="My Story",
    story_author="Author Name"
)

# Play the generated story
play_story(output)
```

### Run the Sample Story

```bash
python app.py
```

The sample story in `app.py` demonstrates the complete pipeline with a predefined story.

### Custom Story

Edit `app.py` and modify `SAMPLE_STORY_TEXT` or use the `run_pipeline()` function with your own story.

## Integration Points for AI Models

The engine is designed to integrate with AI services. Placeholders are marked with `TODO` comments:

### Image Generation
- **`pipeline/image_generator.py`**: `generate_illustration()`
  - Integrate with: OpenAI DALL-E, Stable Diffusion, Midjourney
  
### Text-to-Speech
- **`pipeline/tts_generator.py`**: `generate_narration()`
  - Integrate with: OpenAI TTS, ElevenLabs, Google Cloud TTS, Azure Speech

### Background Music
- **`pipeline/bgm_selector.py`**: `DynamicMusicComposer`
  - Integrate with: Music generation models, custom synthesis

## Logging

All pipeline stages produce detailed logs:

```
[PARSER] Starting story parsing for 'Title'
[PROMPT_BUILDER] Building image prompt for scene 1
[IMAGE_GEN] Generating illustration for scene 1
[TTS] Generating narration for scene 1
[BGM] Selecting BGM for mood=epic, setting=castle
[PLAYER] Starting playback
```

Logs are written to both console and `story_engine.log`.

## Configuration Examples

### Configure AI Model Provider

```python
# config.py
ILLUSTRATION_MODEL = "stable_diffusion"  # or "openai", "custom"
TTS_MODEL = "elevenlabs"                  # or "openai", "google_cloud"
BGM_MODEL = "custom_ai"                   # or "rule_based"
```

### Adjust Generation Parameters

```python
# config.py
IMAGE_RESOLUTION = (2560, 1440)  # Ultra HD
AUDIO_FORMAT = "wav"              # Alternative format
BGM_VOLUME = 0.4                  # Louder BGM
NARRATION_VOLUME = 0.7            # Quieter narration
```

## Data Models

### Scene
```python
@dataclass
class Scene:
    scene_id: int
    title: str
    description: str
    characters: List[Character_Data]
    setting: Setting
    mood: Mood
    narration_text: str
    image_path: Optional[str]
    audio_path: Optional[str]
    bgm_path: Optional[str]
```

### StoryContent
```python
@dataclass
class StoryContent:
    title: str
    author: str
    description: str
    scenes: List[Scene]
```

## Player Controls

The story player provides:
- **Play/Pause/Stop**: Control playback
- **Next/Previous**: Navigate scenes
- **Go to Scene**: Jump to specific scene
- **Volume Control**: Adjust playback volume
- **Fullscreen**: Toggle fullscreen mode

## Future Enhancements

- [ ] Integrate with real AI model APIs
- [ ] Web-based UI/player
- [ ] Interactive story branching
- [ ] Character voice modeling
- [ ] Real-time subtitle generation
- [ ] Video compilation from scenes
- [ ] Advanced NLP for better scene parsing
- [ ] Music composition generation
- [ ] Cloud storage integration

## Development

### Adding a New Pipeline Stage

1. Create a new module in `pipeline/`
2. Define placeholder functions with clear integration points
3. Add logging statements for debugging
4. Update `app.py` to call your stage
5. Add data models to `models/scene_schema.py` if needed

### Example Template

```python
# pipeline/new_stage.py
import logging

logger = logging.getLogger(__name__)

def process_data(input_data):
    """
    Process input data.
    
    TODO: Integrate with actual service
    """
    logger.info("[NEW_STAGE] Processing data")
    logger.debug(f"[NEW_STAGE] Input: {input_data}")
    
    # Placeholder implementation
    result = {"status": "completed"}
    
    logger.info("[NEW_STAGE] Complete")
    return result
```

## Python Version

- **Minimum**: Python 3.11
- **Tested**: Python 3.11+

## License

MIT License

## Contributing

Contributions welcome! Please maintain the modular architecture and add appropriate logging.

## Support

For issues or questions, check the inline documentation in each module and the comprehensive docstrings.
