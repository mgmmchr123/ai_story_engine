"""Tests for player world-state resolution behavior."""

import unittest

from models.scene_schema import (
    Character,
    CharacterData,
    CharacterDefinition,
    LocationDefinition,
    Mood,
    PipelineOutput,
    Scene,
    SceneRenderResult,
    Setting,
    StoryContent,
    StoryVisualBible,
    StyleDefinition,
)
from ui.story_player import StoryPlayer


class StoryPlayerWorldStateTests(unittest.TestCase):
    def test_get_scene_list_prefers_visual_bible_references(self) -> None:
        story = StoryContent(
            title="Story",
            author="Author",
            description="Desc",
            visual_bible=StoryVisualBible(
                title="Story",
                style=StyleDefinition(),
                characters=[
                    CharacterDefinition(
                        character_id="hero_001",
                        name="Aria",
                        role="hero",
                    )
                ],
                locations=[
                    LocationDefinition(
                        location_id="throne_room_001",
                        name="Throne Room",
                    )
                ],
            ),
            scenes=[
                Scene(
                    scene_id=1,
                    title="Finale",
                    description="Legacy stale setting says forest.",
                    characters=[
                        CharacterData(
                            name="Legacy Name",
                            type=Character.NPC,
                            emotion="neutral",
                            action="standing",
                        )
                    ],
                    setting=Setting.FOREST,
                    mood=Mood.CALM,
                    location_id="throne_room_001",
                    active_character_ids=["hero_001"],
                )
            ],
        )
        output = PipelineOutput(
            run_id="run_1",
            story=story,
            scene_results=[SceneRenderResult(scene_id=1, status="completed")],
        )
        player = StoryPlayer(output)
        scene_list = player.get_scene_list()

        self.assertEqual(scene_list[0]["setting"], "throne_room")
        self.assertEqual(scene_list[0]["location_name"], "Throne Room")
        self.assertEqual(scene_list[0]["characters"], ["Aria"])

    def test_get_scene_list_falls_back_to_legacy_fields(self) -> None:
        story = StoryContent(
            title="Story",
            author="Author",
            description="Desc",
            scenes=[
                Scene(
                    scene_id=1,
                    title="Legacy",
                    description="Legacy scene",
                    characters=[
                        CharacterData(
                            name="Legacy Hero",
                            type=Character.HERO,
                            emotion="focused",
                            action="walking",
                        )
                    ],
                    setting=Setting.CASTLE,
                    mood=Mood.HEROIC,
                )
            ],
        )
        output = PipelineOutput(
            run_id="run_2",
            story=story,
            scene_results=[SceneRenderResult(scene_id=1, status="completed")],
        )
        player = StoryPlayer(output)
        scene_list = player.get_scene_list()

        self.assertEqual(scene_list[0]["setting"], "castle")
        self.assertEqual(scene_list[0]["characters"], ["Legacy Hero"])

    def test_player_total_duration_falls_back_to_scene_media_durations(self) -> None:
        story = StoryContent(
            title="Story",
            author="Author",
            description="Desc",
            scenes=[
                Scene(
                    scene_id=1,
                    title="One",
                    description="Scene one",
                    characters=[],
                    setting=Setting.FOREST,
                    mood=Mood.CALM,
                ),
                Scene(
                    scene_id=2,
                    title="Two",
                    description="Scene two",
                    characters=[],
                    setting=Setting.FOREST,
                    mood=Mood.CALM,
                ),
            ],
        )
        output = PipelineOutput(
            run_id="run_duration",
            story=story,
            scene_results=[
                SceneRenderResult(scene_id=1, status="completed", media_duration_seconds=2.5),
                SceneRenderResult(scene_id=2, status="completed", media_duration_seconds=3.0),
            ],
            total_duration_seconds=0.0,
        )

        player = StoryPlayer(output)

        self.assertAlmostEqual(player.state.total_duration, 5.5, places=3)


if __name__ == "__main__":
    unittest.main()
