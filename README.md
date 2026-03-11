# AI Storytelling Engine

AI Storytelling Engine is a modular Python 3.11+ pipeline that parses story text into scenes, renders per-scene artifacts, and persists a resumable run manifest.

## Refactored Architecture

```text
ai_story_engine/
  app.py
  config.py
  engine/
    context.py
    stage.py
    runner.py
    manifest.py
    errors.py
    logging_utils.py
  providers/
    image_provider.py
    tts_provider.py
    bgm_provider.py
  pipeline/
    parse_stage.py
    render_stage.py
    story_parser.py
    prompt_builder.py
  models/
    scene_schema.py
  ui/
    story_player.py
  tests/
```

## Key Design Changes

- `Scene` is now domain-only (no generated file paths).
- Generated artifacts are modeled separately with `SceneAssets` and `SceneRenderResult`.
- Pipeline execution uses explicit stage contracts via `PipelineStage`.
- Run-scoped state lives in `PipelineContext`.
- Provider interfaces decouple rendering logic from concrete implementations.
- Each run writes outputs to `output/runs/<run_id>/` and stores `manifest.json`.
- Stage-level retry/timeout and scene-level partial failure handling are built in.
- Resume mode can skip scenes already rendered in a previous manifest.

## Default Pipeline

1. `StoryParseStage`
2. `SceneRenderStage`
3. `ManifestPersistStage`

## Output Layout

```text
output/runs/<run_id>/
  images/
  audio/
  bgm/
  manifest.json
```

## Usage

### Run demo

```bash
python app.py
```

### Run programmatically

```python
from app import run_pipeline

output = run_pipeline(
    story_text="A hero enters the forest.\nA storm rises.",
    story_title="My Story",
    story_author="Author",
    resume=False,
    run_id=None,
)

print(output.run_id)
print(output.status)
print(output.manifest_path)
```

### Resume a previous run

```python
from app import run_pipeline

output = run_pipeline(
    story_text="A hero enters the forest.\nA storm rises.",
    story_title="My Story",
    story_author="Author",
    resume=True,
    run_id="20260311_120000_abcd1234",
)
```

## Configuration

`config.py` centralizes settings in dataclasses:

- `EngineSettings`
- `RetrySettings`
- `OutputSettings`
- `ProviderSettings`

You can change retry/timeouts, output directories, and provider selections from one place.

## Testing

Run all tests:

```bash
python -m unittest discover -s tests -v
```

Included tests:
- parser unit tests
- prompt builder unit tests
- manifest persistence unit tests
- runner integration test with placeholder providers
