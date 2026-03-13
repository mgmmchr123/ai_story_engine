# ai_story_engine - AI Context

## Project snapshot
Project snapshot: ai_story_engine

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
parser.extractor_kind
parser.extractor_kwargs

## Artifacts
scene_{id}.json

## Rerun stack
prepare_scene_rerun
bootstrap_scene_rerun_context
rerun_selected_scenes

## Reporting
scene_render_summary
run_report

## Capabilities
- scene artifact cache
- artifact lookup helpers
- selective scene rendering
- scene-level rerun
- rerun metadata traceability
- scene execution summary
- run-level report
