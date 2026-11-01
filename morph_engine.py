"""Local, deterministic image transitions. No network or model downloads."""

from pathlib import Path
import math
import warnings

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, UnidentifiedImageError

from piece_transition import PieceTransition


BACKGROUND = (16, 23, 29)
MAX_PIXELS = 40_000_000
OUTPUT_SIZE = (960, 600)


def load_image(path: str | Path) -> Image.Image:
    """Decode and orient a still image, retaining the previous image on UI failure."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(path) as image:
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError('图片超过 4000 万像素，请先缩小后再上传。')
                image.load()
                return ImageOps.exif_transpose(image).convert('RGBA')
    except ValueError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError('图片尺寸过大，请先缩小后再上传。') from error
    except (OSError, UnidentifiedImageError, SyntaxError) as error:
        raise ValueError('无法读取这张图片，请选择有效的 PNG、JPG、WebP 或 BMP 图片。') from error


def fit_image(image: Image.Image, size: tuple[int, int], background=BACKGROUND) -> Image.Image:
    """Contain the entire image, preserving its aspect ratio and alpha."""
    rgba = image.convert('RGBA')
    fitted = ImageOps.contain(rgba, size, Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', size, background)
    canvas.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2), fitted)
    return canvas


def source_background(image: Image.Image) -> tuple[int, int, int]:
    """Choose an existing border color instead of inventing dark padding."""
    rgba = image.convert('RGBA')
    flat = Image.new('RGBA', image.size, 'white')
    flat.alpha_composite(rgba)
    rgb = flat.convert('RGB')
    edges = np.concatenate([
        np.asarray(rgb.crop((0, 0, rgb.width, 1))).reshape(-1, 3),
        np.asarray(rgb.crop((0, rgb.height-1, rgb.width, rgb.height))).reshape(-1, 3),
        np.asarray(rgb.crop((0, 0, 1, rgb.height))).reshape(-1, 3),
        np.asarray(rgb.crop((rgb.width-1, 0, rgb.width, rgb.height))).reshape(-1, 3),
    ]).astype(np.float32)
    median = np.median(edges, axis=0)
    return tuple(map(int, edges[np.argmin(np.sum((edges-median)**2, axis=1))]))


def make_demo_images(size: tuple[int, int] = OUTPUT_SIZE) -> tuple[Image.Image, Image.Image]:
    """Original procedural landscapes, available offline on first launch."""
    width, height = size
    x, y = np.meshgrid(np.linspace(0, 1, width), np.linspace(0, 1, height))
    rng = np.random.default_rng(1145)
    noise = rng.normal(0, .8, (height, width, 1))
    images = []
    for warm in (True, False):
        top, bottom = (([39, 35, 57], [230, 142, 103]) if warm else ([9, 32, 56], [70, 145, 161]))
        sky = np.array(top)[None, None, :] * (1-y[..., None]) + np.array(bottom)[None, None, :] * y[..., None]
        image = Image.fromarray(np.uint8(np.clip(sky + noise, 0, 255)))
        draw = ImageDraw.Draw(image)
        cx, cy, radius = (.70, .32, .115) if warm else (.29, .28, .095)
        for step in range(12, 0, -1):
            rr = radius + step * .009
            halo = Image.new('RGBA', size)
            ImageDraw.Draw(halo).ellipse(((cx-rr)*width, cy*height-rr*width, (cx+rr)*width, cy*height+rr*width), fill=(255, 186, 133, 3) if warm else (141, 232, 229, 3))
            image = Image.alpha_composite(image.convert('RGBA'), halo).convert('RGB')
        draw = ImageDraw.Draw(image)
        draw.ellipse(((cx-radius)*width, cy*height-radius*width, (cx+radius)*width, cy*height+radius*width), fill='#ffd5a0' if warm else '#c5f5e8')
        colors = ['#a77379', '#905e70', '#6d4e63', '#483e57', '#292c43'] if warm else ['#3f8791', '#306c7c', '#235366', '#193d50', '#112d3d']
        for layer, color in enumerate(colors):
            points = []
            for xx in np.linspace(-.05, 1.05, 100):
                yy = .48 + layer * .092 + math.sin(xx*7.6 + layer*1.6)*(.08 if warm else .1)
                yy += math.sin(xx*17 + layer)*.018
                points.append((xx*width, yy*height))
            draw.polygon(points + [(width, height), (0, height)], fill=color)
        # Thin contour lines make the tile movement easier to follow.
        for layer in range(9):
            points = [(xx*width, (.81 + layer*.025 + math.sin(xx*5 + layer*.22)*.045)*height) for xx in np.linspace(0, 1, 120)]
            draw.line(points, fill='#635163' if warm else '#225063', width=max(1, width//900))
        images.append(image)
    return tuple(images)


def smoothstep(value):
    value = np.clip(value, 0, 1)
    return value * value * (3 - 2 * value)


class MorphEngine:
    def __init__(self, source: Image.Image, target: Image.Image,
                 size: tuple[int, int] = OUTPUT_SIZE, block_size: int = 1,
                 restore_target_colors: bool = True):
        self.size = size
        self.background = source_background(source)
        self.source = fit_image(source, size, self.background)
        self.target = fit_image(target, size)
        self.width, self.height = size
        self.block_size = max(1, int(block_size))
        columns = math.ceil(self.width / self.block_size)
        rows = math.ceil(self.height / self.block_size)
        self.columns, self.rows = columns, rows
        self.parts = PieceTransition(self.source, self.target, self.block_size, self.background, restore_target_colors)
        self.target = self.parts.result
        self.destinations = self.parts.destinations
        coarse = self.target.resize((max(4, columns//2), max(4, rows//2)), Image.Resampling.BOX).resize(size, Image.Resampling.NEAREST).filter(ImageFilter.GaussianBlur(3))
        edges = np.asarray(self.target.filter(ImageFilter.FIND_EDGES)).astype(float)
        features = Image.fromarray(np.uint8(np.clip(np.asarray(self.target)*.7 + edges*.8 + np.array([0, 13, 16]), 0, 255)))
        self.layers = [self.source, coarse, features, self.target]
        self.layer_arrays = [np.asarray(layer).astype(np.float32) for layer in self.layers]
        self.horizontal = np.linspace(0, 1, self.width)[None, :, None]

    def render(self, progress: float, mode: str = 'pixels') -> Image.Image:
        progress = float(np.clip(progress, 0, 1))
        if progress <= 0:
            return self.source.copy()
        if progress >= 1:
            return self.target.copy()
        if mode == 'convolution':
            return self._convolution(progress)
        return self._pixels(progress)

    def _pixels(self, progress: float) -> Image.Image:
        return self.parts.render(progress)

    def _convolution(self, progress: float) -> Image.Image:
        stage = min(2, int(progress*3))
        fraction = progress*3-stage
        mask = smoothstep((fraction*1.12 - .06 - self.horizontal)/.065 + .5)
        array = self.layer_arrays[stage]*(1-mask) + self.layer_arrays[stage+1]*mask
        frame = Image.fromarray(np.uint8(np.clip(array, 0, 255)))
        overlay = Image.new('RGBA', self.size)
        draw = ImageDraw.Draw(overlay)
        alpha = int(210 * min(1, fraction*12, (1-fraction)*12))
        scan_x = int((fraction*1.12-.06)*self.width)
        for offset in range(-12, 13):
            draw.line((scan_x+offset, 0, scan_x+offset, self.height), fill=(100, 244, 213, int(alpha*.13*(1-abs(offset)/13))))
        draw.line((scan_x, 0, scan_x, self.height), fill=(133, 255, 224, alpha), width=2)
        kernel = max(18, self.block_size*2)
        center_y = int((.5-.42*math.cos(fraction*math.pi*8))*self.height)
        left, top = scan_x-kernel*1.5, center_y-kernel*1.5
        for axis in range(4):
            draw.line((left+axis*kernel, top, left+axis*kernel, top+3*kernel), fill=(177, 255, 233, alpha), width=1)
            draw.line((left, top+axis*kernel, left+3*kernel, top+axis*kernel), fill=(177, 255, 233, alpha), width=1)
        draw.rectangle((left+kernel, top+kernel, left+kernel*2, top+kernel*2), fill=(128, 255, 216, int(alpha*.28)))
        return Image.alpha_composite(frame.convert('RGBA'), overlay).convert('RGB')
