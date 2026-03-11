"""Legacy image generation helpers kept for backward compatibility."""

import logging

from config import OUTPUT_DIR
from models.scene_schema import Scene
from providers.image_provider import PlaceholderImageProvider

logger = logging.getLogger(__name__)


def generate_illustration(scene: Scene, prompt: str) -> str:
    """Generate a placeholder image artifact and return path."""
    image_path = OUTPUT_DIR / "images" / f"scene_{scene.scene_id:03d}.txt"
    logger.info("[IMAGE_GEN] Generating illustration for scene %s", scene.scene_id)
    provider = PlaceholderImageProvider()
    return str(provider.generate(scene, prompt, image_path))


def optimize_image(image_path: str, resolution: tuple = (1920, 1080)) -> str:
    """Return a derived optimized placeholder path."""
    _ = resolution
    return image_path.replace(".txt", "_optimized.txt")


def apply_visual_effects(image_path: str, effects: list | None = None) -> str:
    """Return a derived effects placeholder path."""
    _ = effects or []
    return image_path.replace(".txt", "_with_effects.txt")


class IllustrationStyle:
    """Predefined illustration styles."""

    STYLES = {
        "realistic": "Photorealistic, highly detailed, cinematographic",
        "watercolor": "Watercolor painting, soft colors, artistic",
        "comic": "Comic book style, bold lines, vibrant colors",
        "anime": "Anime style, expressive characters, detailed backgrounds",
        "oil_painting": "Oil painting, classic art style, rich textures",
        "digital_art": "Modern digital art, vector-like, stylized",
    }

    @staticmethod
    def get_style_prompt(style: str) -> str:
        return IllustrationStyle.STYLES.get(style, IllustrationStyle.STYLES["realistic"])


class ImageGenerationConfig:
    """Configuration for image generation."""

    def __init__(self, model: str = "placeholder", style: str = "realistic"):
        self.model = model
        self.style = style
        self.quality = "hd"
        self.aspect_ratio = "16:9"
        self.num_images = 1
        self.seed = None

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "style": self.style,
            "quality": self.quality,
            "aspect_ratio": self.aspect_ratio,
            "num_images": self.num_images,
            "seed": self.seed,
        }
