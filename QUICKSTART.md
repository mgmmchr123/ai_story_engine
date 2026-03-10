# Quick Start Guide

## 🚀 Run the Demo

```bash
cd ai_story_engine
python app.py
```

Expected output: 8 scenes processed through the full pipeline with logging.

---

## 📚 File Overview

### Main Entry Point
- **app.py** - Run this to execute the complete pipeline with sample story

### Configuration
- **config.py** - Edit paths, AI model settings, parameters

### Pipeline (processing stages)
- **pipeline/story_parser.py** - Converts text to scenes
- **pipeline/prompt_builder.py** - Creates AI prompts
- **pipeline/image_generator.py** - Generates illustrations
- **pipeline/tts_generator.py** - Generates narration
- **pipeline/bgm_selector.py** - Selects background music

### Data Models
- **models/scene_schema.py** - Scene, Story, Asset dataclasses

### User Interface
- **ui/story_player.py** - Story playback player

### Documentation
- **README.md** - Complete documentation
- **PROJECT_SUMMARY.md** - This file with overview

---

## 🔧 Key Classes

### StoryContent
```python
story = StoryContent(
    title="My Story",
    author="Author Name",
    description="Story description",
    scenes=[scene1, scene2, ...]
)
```

### Scene
```python
scene = Scene(
    scene_id=1,
    title="Scene Title",
    description="Scene description",
    characters=[Character_Data(...)],
    setting=Setting.FOREST,
    mood=Mood.EPIC,
    narration_text="Narration content"
)
```

### StoryPlayer
```python
player = StoryPlayer(pipeline_output)
player.play()               # Start playback
player.next_scene()         # Next scene
player.previous_scene()     # Previous scene
player.goto_scene(3)        # Jump to scene 3
player.set_volume(0.8)      # Set volume (0.0-1.0)
```

---

## 🎬 Pipeline Stages

1. **Story Parser** - `story_parser.py`
   - Input: Raw text
   - Output: List of Scene objects

2. **Prompt Builder** - `prompt_builder.py`
   - Input: Scene object
   - Output: Image, narration, and BGM prompts

3. **Image Generator** - `image_generator.py`
   - Input: Image prompt
   - Output: PNG image path

4. **TTS Generator** - `tts_generator.py`
   - Input: Narration text, voice settings
   - Output: MP3 audio path

5. **BGM Selector** - `bgm_selector.py`
   - Input: Mood, setting, intensity parameters
   - Output: BGM file path

6. **Story Player** - `ui/story_player.py`
   - Input: PipelineOutput with all assets
   - Output: Interactive playback interface

---

## 💡 Integration Points (Marked with TODO)

### For OpenAI Integration
1. **Image Generation** (`pipeline/image_generator.py`, line ~45)
   ```python
   # TODO: Replace with OpenAI DALL-E
   response = openai.Image.create(prompt=prompt, n=1)
   ```

2. **Text-to-Speech** (`pipeline/tts_generator.py`, line ~55)
   ```python
   # TODO: Replace with OpenAI TTS
   response = client.audio.speech.create(model="tts-1-hd", voice=voice)
   ```

### For Stable Diffusion
- Edit `pipeline/image_generator.py`
- Modify `generate_illustration()` function

### For Music Library
- Populate `assets/bgm/` with music files
- Update `MusicLibrary._load_track_metadata()` in `pipeline/bgm_selector.py`

---

## 🔍 Configuration

Edit **config.py** to customize:

```python
# AI Model Selection
ILLUSTRATION_MODEL = "openai"  # or "stable_diffusion"
TTS_MODEL = "openai"           # or "elevenlabs"
BGM_MODEL = "rule_based"       # or "custom_ai"

# Generation Parameters
IMAGE_RESOLUTION = (1920, 1080)
AUDIO_FORMAT = "mp3"
BGM_VOLUME = 0.3
NARRATION_VOLUME = 0.8

# Logging
LOG_LEVEL = "INFO"

# Demo
CONFIG_SAMPLE_STORY = True  # Set to False to disable
```

---

## 📊 Output Structure

Generated files are organized as:

```
output/
├── images/
│   ├── scene_001_Scene_1.png
│   ├── scene_002_Scene_2.png
│   └── ...
└── audio/
    ├── scene_001_narration.mp3
    ├── scene_002_narration.mp3
    └── ...
```

---

## 🧪 Writing Tests

Example test:

```python
from pipeline.story_parser import parse_story
from models.scene_schema import StoryContent

def test_story_parsing():
    text = "Scene one. Scene two."
    result = parse_story(text, "Test", "Author")
    
    assert isinstance(result, StoryContent)
    assert len(result.scenes) == 2
    assert result.scenes[0].title == "Scene 1"
```

---

## 📝 Logging

Check logs in:
- **Console output** - Real-time processing
- **story_engine.log** - File log with full details

Log format: `[STAGE] MESSAGE`
- `[PARSER]` - Story parsing stage
- `[PROMPT_BUILDER]` - Prompt generation
- `[IMAGE_GEN]` - Image generation
- `[TTS]` - Text-to-speech generation
- `[BGM]` - BGM selection
- `[PLAYER]` - Story playback

---

## ⚙️ Dependencies

**Current:** None (standard library only)

**For AI Integration, you'll need:**
```bash
# For OpenAI
pip install openai

# For Stable Diffusion
pip install stability-sdk

# For ElevenLabs TTS
pip install elevenlabs

# For audio processing (optional)
pip install pydub librosa

# For NLP enhancement (optional)
pip install spacy nltk
```

---

## 🎯 Example: Custom Story

```python
from app import run_pipeline, play_story

my_story = """
The ancient castle stood atop the misty mountain.
A brave knight entered the grand hall.
The dragon's eyes glowed with ancient fury.
The final battle would determine the kingdom's fate.
"""

output = run_pipeline(
    story_text=my_story,
    story_title="Dragon's Challenge",
    story_author="You"
)

play_story(output)
```

---

## 🐛 Troubleshooting

### Character Encoding Issues
- Windows console might have issues with Unicode
- Use ASCII characters in logs (already done)

### Path Issues
- Project uses pathlib - works on Windows/Mac/Linux
- All paths relative to project root

### Module Not Found
- Ensure you're in the project directory
- Python path should include project root

---

## 📖 Extended Reading

- **README.md** - Complete documentation (850+ lines)
- **PROJECT_SUMMARY.md** - Detailed overview
- Inline docstrings - All functions documented
- config.py comments - Configuration explained

---

## 💬 Key Commands

```bash
# Run the full pipeline
python app.py

# Check configuration
cat config.py

# View logs
cat story_engine.log

# List all scenes in output
ls output/images/    # See all generated illustrations
ls output/audio/     # See all narration files
```

---

## ✅ What's Included

- ✅ 13 Python modules (~2000 lines)
- ✅ Full pipeline (6 stages)
- ✅ Data models (7 dataclasses)
- ✅ Interactive player
- ✅ Comprehensive logging
- ✅ Configuration system
- ✅ Documentation (1000+ lines)
- ✅ Sample story
- ✅ Placeholder integration points
- ✅ No external dependencies

---

## 🚀 Next: Integrate AI Models

1. Get API credentials for your chosen service
2. Add to `config.py`
3. Implement actual calls in placeholder functions (marked with TODO)
4. Test with `python app.py`

See **README.md → "Integration Points for AI Models"** for detailed guidance.

---

**You're ready to go!** 🎉
