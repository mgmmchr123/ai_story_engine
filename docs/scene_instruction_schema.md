# Scene Instruction Schema

Scene instructions are the normalized handoff between `scene_builder` and downstream generation stages. They represent one renderable scene in a provider-friendly form without changing the canonical `story.json`.

## Producer And Consumer

- Produced by `pipeline.scene_builder_stage.SceneBuilderStage`
- Built from `engine.scene_builder.scene_builder.build_scene()`
- Validated by `engine.scene_builder.scene_instruction_validator.validate_scene_instruction()`
- Consumed today by `pipeline.render_stage.SceneRenderStage`

## Required Fields

```json
{
  "scene_id": 1,
  "image_prompt": "string",
  "characters": ["character_id"],
  "location": "location_id",
  "camera": {
    "shot": "string",
    "angle": "string"
  },
  "duration_sec": 5,
  "dialogue": [],
  "actions": []
}
```

## Field Meaning

- `scene_id`: Integer scene identifier. Must be unique within a batch.
- `image_prompt`: Non-empty prompt sent to image generation.
- `characters`: List of participating canonical character IDs.
- `location`: Canonical location ID for the scene.
- `camera.shot`: Shot framing label such as `medium shot` or `close-up`.
- `camera.angle`: Camera angle label such as `eye level` or `high angle`.
- `duration_sec`: Positive integer target scene duration.
- `dialogue`: List of dialogue objects carried forward from canonical story scene data.
- `actions`: List of action objects carried forward from canonical story scene data.

## Validation And Normalization

- `scene_id` must exist.
- `image_prompt` must be a non-empty string after trimming.
- `duration_sec` must be a positive integer.
- `camera` must be an object containing both `shot` and `angle`.
- `characters` is normalized to a list of non-empty strings.
- `dialogue` and `actions` are normalized to lists of objects.

If validation fails, the current runtime raises `ValueError` instead of guessing a replacement shape.
