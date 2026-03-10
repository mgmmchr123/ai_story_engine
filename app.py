"""
Main Application - AI Storytelling Engine
Orchestrates the complete pipeline: Story → Scene Parser → Illustration Generator → 
TTS Generator → BGM Selector → Story Player
"""
from pathlib import Path
import logging
from datetime import datetime
from pathlib import Path

# Import pipeline modules
from pipeline import (
    parse_story,
    build_image_prompt,
    build_narration_prompt,
    build_bgm_prompt,
    generate_illustration,
    generate_narration,
    select_bgm
)

# Import models and UI
from models.scene_schema import StoryContent, Scene, PipelineOutput, GeneratedAssets
from ui.story_player import StoryPlayer, PlaybackController
from config import CONFIG_SAMPLE_STORY, PROJECT_ROOT

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / 'story_engine.log')
    ]
)

logger = logging.getLogger(__name__)
SAMPLE_STORY_PATH = PROJECT_ROOT / "assets" / "sample_story.txt"


# ============================================================================
# SAMPLE STORIES
# ============================================================================




# ============================================================================
# PIPELINE ORCHESTRATION
# ============================================================================

def run_pipeline(story_text: str, story_title: str = "Default Story",
                story_author: str = "Anonymous") -> PipelineOutput:
    """
    Run the complete storytelling pipeline.
    
    Pipeline flow:
    1. Parse story into scenes
    2. Build prompts for each generation stage
    3. Generate illustrations
    4. Generate narration audio
    5. Select background music
    6. Compile output
    
    Args:
        story_text: Raw story content
        story_title: Title of the story
        story_author: Author name
        
    Returns:
        PipelineOutput with all generated content
    """
    logger.info("="*70)
    logger.info("STARTING AI STORYTELLING PIPELINE")
    logger.info("="*70)
    
    start_time = datetime.now()
    generated_assets = []
    
    try:
        # ====== STAGE 1: PARSE STORY ======
        logger.info("\n[STAGE 1] STORY PARSING")
        logger.info("-" * 70)
        story = parse_story(story_text, story_title, story_author)
        logger.info(f"[OK] Parsed {len(story.scenes)} scenes from story")
        
        # ====== STAGE 2: GENERATE CONTENT FOR EACH SCENE ======
        logger.info("\n[STAGE 2] SCENE CONTENT GENERATION")
        logger.info("-" * 70)
        
        for idx, scene in enumerate(story.scenes, 1):
            logger.info(f"\nProcessing Scene {idx}/{len(story.scenes)}: {scene.title}")
            
            # Build prompts
            image_prompt = build_image_prompt(scene)
            narration_prompt = build_narration_prompt(scene)
            bgm_params = build_bgm_prompt(scene) or {}
            
            # Generate illustration
            logger.info(f"  → Generating illustration...")
            image_path = generate_illustration(scene, image_prompt)
            scene.image_path = image_path
            logger.info(f"  [OK] Illustration: {Path(image_path).name}")
            
            # Generate narration
            logger.info(f"  → Generating narration...")
            narration_path = generate_narration(scene.scene_id, narration_prompt)
            scene.audio_path = narration_path
            logger.info(f"  [OK] Narration: {Path(narration_path).name}")
            
            # Select background music
            logger.info(f"  → Selecting background music...")
            bgm_path = select_bgm(
                mood=scene.mood.value,
                setting=scene.setting.value,
                intensity=bgm_params.get("intensity", "medium"),
                tempo=bgm_params.get("tempo", "moderate")
            )
            scene.bgm_path = bgm_path
            logger.info(f"  [OK] BGM: {Path(bgm_path).name}")
            
            # Record generated assets
            asset = GeneratedAssets(
                scene_id=scene.scene_id,
                image_path=image_path,
                narration_path=narration_path,
                bgm_path=bgm_path,
                generation_timestamp=datetime.now().isoformat()
            )
            generated_assets.append(asset)
            
            logger.info(f"  [OK] Scene {idx} complete")
        
        # ====== COMPILE PIPELINE OUTPUT ======
        logger.info("\n[STAGE 3] PIPELINE OUTPUT COMPILATION")
        logger.info("-" * 70)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        output = PipelineOutput(
            story=story,
            generated_assets=generated_assets,
            status="completed",
            total_duration_seconds=duration
        )
        
        logger.info(f"[OK] Pipeline completed successfully")
        logger.info(f"[OK] Total processing time: {duration:.2f} seconds")
        logger.info(f"[OK] Generated assets: {len(generated_assets)}")
        
    except Exception as e:
        logger.error(f"[ERROR] Pipeline failed: {str(e)}", exc_info=True)
        output = PipelineOutput(
            story=story if 'story' in locals() else StoryContent(
            title=story_title,
            author=story_author,
            description="",
            scenes=[]
        ),
            generated_assets=generated_assets,
            status="failed",
            total_duration_seconds=(datetime.now() - start_time).total_seconds()
        )
    
    logger.info("="*70)
    return output


# ============================================================================
# STORY PLAYBACK
# ============================================================================

def play_story(pipeline_output: PipelineOutput) -> None:
    """
    Initialize and play the generated story.
    
    Args:
        pipeline_output: Output from the pipeline
    """
    logger.info("\n" + "="*70)
    logger.info("LAUNCHING STORY PLAYER")
    logger.info("="*70)
    
    # Initialize player
    player = StoryPlayer(pipeline_output)
    controller = PlaybackController(player)
    
    # Display story info
    player.display_story_info()
    
    # Play story
    logger.info("Starting automated playback...")
    player.play()
    
    # Iterate through scenes
    for idx in range(len(player.story.scenes)):
        scene = player.story.scenes[idx]
        player.goto_scene(idx)
        logger.info(f"\n[SCENE {idx + 1}] {scene.title}")
        logger.info("-" * 70)
        
        # Display scene details
        logger.info(f"Setting: {scene.setting.value} | Mood: {scene.mood.value}")
        logger.info(f"Characters: {', '.join([c.name for c in scene.characters])}")
        logger.info(f"\nNarration: {scene.narration_text[:100]}...")
        
        if scene.image_path:
            logger.info(f"Image: {scene.image_path}")
        if scene.audio_path:
            logger.info(f"Audio: {scene.audio_path}")
        if scene.bgm_path:
            logger.info(f"BGM: {scene.bgm_path}")
    
    # Playback summary
    logger.info("\n" + "="*70)
    logger.info("PLAYBACK COMPLETE")
    playback_info = controller.get_playback_info()
    logger.info(f"Story: {playback_info['story']}")
    logger.info(f"Scenes: {playback_info['current_scene']}/{playback_info['total_scenes']}")
    logger.info(f"Total Duration: {playback_info['total_duration']:.2f}s")
    logger.info("="*70)


# ============================================================================
# MAIN APPLICATION ENTRY POINT
# ============================================================================
def load_story(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
    
def main():
    """Main application entry point."""
    logger.info(f"AI Storytelling Engine started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Project root: {PROJECT_ROOT}")
    
    # Run with sample story
    if CONFIG_SAMPLE_STORY:
        logger.info("\nLoading sample story...")

        pipeline_output = run_pipeline(
            story_text = load_story(SAMPLE_STORY_PATH),
            story_title="The Quest for the Lost Artifact",
            story_author="AI Storyteller"
        )
        
        # Play the generated story
        play_story(pipeline_output)
        
    else:
        logger.info("Sample story disabled in configuration")
    
    logger.info(f"\nApplication finished at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
