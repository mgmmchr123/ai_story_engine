# ai_story_engine - AI Context

## Current phase
Phase: rerun/reporting foundation

## Core pipeline
raw text
-> StoryParser (pluggable extractor)
-> canonical story_json
-> validate_story_json
-> SceneBuilderStage
-> scene instructions
-> scene instruction cache artifacts
-> SceneRenderStage

## Extractors
- DeterministicStoryExtractor (default)
- OllamaStoryExtractor (stub)
- GPTStoryExtractor (stub)

## Config
- parser.extractor_kind
- parser.extractor_kwargs

## Artifacts
- scene_{id}.json

## Rerun stack
- prepare_scene_rerun
- bootstrap_scene_rerun_context
- rerun_selected_scenes

## Reporting
- scene_render_summary

## Stable contracts
- canonical story_json
- scene_instruction schema
- scene_instruction cache naming: scene_{id:03d}.json

## Current focus
- run-level reporting
