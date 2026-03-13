# Story Schema

`story.json` is the canonical structured story representation used inside the pipeline after parsing and before scene instruction generation.

## Top-Level Shape

```json
{
  "story_id": "string",
  "title": "string",
  "style": "anime | cartoon | realistic",
  "characters": [],
  "locations": [],
  "scenes": []
}
```

## Required Top-Level Fields

- `story_id`: Stable story identifier.
- `title`: Story title.
- `style`: Global visual style label.
- `characters`: List of canonical character definitions.
- `locations`: List of canonical location definitions.
- `scenes`: List of canonical scene objects.

## Character Object

```json
{
  "id": "string",
  "name": "string",
  "appearance": "string",
  "voice": "string"
}
```

## Location Object

```json
{
  "id": "string",
  "description": "string",
  "time_of_day": "string"
}
```

## Scene Object

```json
{
  "scene_id": 1,
  "location": "location_id",
  "duration_sec": 5,
  "characters": ["character_id"],
  "camera": {
    "shot": "medium shot",
    "angle": "eye level"
  },
  "actions": [],
  "dialogue": []
}
```

## Validation And Defaults

- Missing top-level arrays are normalized to empty lists.
- Missing or malformed `camera` is normalized to `{"shot": "medium shot", "angle": "eye level"}`.
- Missing or invalid `duration_sec` is normalized to `5`.
- Missing scene `location` falls back to `unknown_location`.
- Missing scene `characters` falls back to `["narrator"]`.
- Missing or invalid scene list results in one default scene.

## Relation To Scene Builder

- `pipeline.parse_stage.StoryParseStage` stores validated `story.json` in `PipelineContext.story_json`.
- `pipeline.scene_builder_stage.SceneBuilderStage` converts each story scene into a validated scene instruction artifact used by downstream render stages.
