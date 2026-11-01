"""One-to-one pixel transport; unchecked mode never replaces RGB values."""

from dataclasses import dataclass
import math

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class PieceLayout:
    positions: np.ndarray
    correction: np.ndarray


def ease(value):
    value = np.clip(value, 0, 1)
    return value*value*(3-2*value)


class PieceTransition:
    def __init__(self, source: Image.Image, target: Image.Image, block_size=1,
                 background=(255, 255, 255), restore_target_colors=True):
        self.source, self.target = source, target
        self.width, self.height = source.size
        self.block_size = max(1, int(block_size))
        self.columns = math.ceil(self.width/self.block_size)
        self.rows = math.ceil(self.height/self.block_size)
        self.background = background
        self.restore_target_colors = restore_target_colors
        self.source_tiles = self._split(source)
        target_tiles = self._split(target)
        self.identical = source.tobytes() == target.tobytes()
        source_mean = self.source_tiles.mean(axis=1, dtype=np.float32)
        target_mean = target_tiles.mean(axis=1, dtype=np.float32)
        source_light = source_mean[:, 0]*.299+source_mean[:, 1]*.587+source_mean[:, 2]*.114
        target_light = target_mean[:, 0]*.299+target_mean[:, 1]*.587+target_mean[:, 2]*.114
        source_order = np.argsort(source_light, kind='stable')
        target_order = np.argsort(target_light, kind='stable')
        count = len(source_order)
        self.destinations = np.empty(count, dtype=np.int32)
        self.destinations[source_order] = target_order
        # In unchecked mode the entire payload is the original RGB data. Even
        # after landing, no target luminance or texture pixels replace it.
        self.target_tiles = target_tiles[self.destinations] if restore_target_colors else self.source_tiles
        ordered = np.empty_like(self.target_tiles)
        ordered[self.destinations] = self.target_tiles
        b = self.block_size
        result = ordered.reshape(self.rows, self.columns, b, b, 3).transpose(0, 2, 1, 3, 4).reshape(self.rows*b, self.columns*b, 3)
        self.result = target.copy() if restore_target_colors else Image.fromarray(result[:self.height, :self.width].copy())

        gx, gy = np.meshgrid(np.arange(self.columns, dtype=np.float32), np.arange(self.rows, dtype=np.float32))
        self.half = (b-1)/2
        self.starts = np.column_stack((gx.ravel()*b+self.half, gy.ravel()*b+self.half))
        self.ends = self.starts[self.destinations]
        dx, dy = np.meshgrid(np.arange(b, dtype=np.int32), np.arange(b, dtype=np.int32))
        self.pixel_x, self.pixel_y = dx.ravel(), dy.ravel()
        rng = np.random.default_rng(731)
        offsets = (rng.random((count, 2), dtype=np.float32)*2-1)*np.array([self.width*.035, self.height*.055], dtype=np.float32)
        upper = np.maximum([self.half, self.half], [self.width-1-self.half, self.height-1-self.half]).astype(np.float32)
        self.departures = np.clip(self.starts+offsets, self.half, upper)
        offsets = (rng.random((count, 2), dtype=np.float32)*2-1)*np.array([self.width*.04, self.height*.065], dtype=np.float32)
        self.approaches = np.clip(self.ends+offsets, self.half, upper)
        self.bends = (rng.random((count, 2), dtype=np.float32)*2-1)*np.array([self.width*.06, self.height*.085], dtype=np.float32)
        self.route_start = .18+rng.random(count, dtype=np.float32)*.035
        self.route_end = .54+rng.random(count, dtype=np.float32)*.06
        radial = np.linalg.norm((self.ends-np.array([self.width/2, self.height/2], dtype=np.float32))/np.array([self.width/2, self.height/2], dtype=np.float32), axis=1)/math.sqrt(2)
        self.dock_times = .70+.14*radial+rng.random(count, dtype=np.float32)*.045

    def _split(self, image):
        array = np.asarray(image.convert('RGB'))
        b = self.block_size
        padded = np.pad(array, ((0, self.rows*b-self.height), (0, self.columns*b-self.width), (0, 0)), mode='edge')
        return padded.reshape(self.rows, b, self.columns, b, 3).transpose(0, 2, 1, 3, 4).reshape(-1, b*b, 3).copy()

    def layout(self, progress: float) -> PieceLayout:
        progress = float(np.clip(progress, 0, 1))
        detached = float(ease(progress/.18))
        route = ease((progress-self.route_start)/(self.route_end-self.route_start))
        docking = ease((progress-self.route_end)/(self.dock_times-self.route_end))
        positions = self.starts+(self.departures-self.starts)*detached
        positions += (self.approaches-positions)*route[:, None]
        positions += self.bends*np.sin(route[:, None]*np.float32(math.pi))
        positions += (self.ends-positions)*docking[:, None]
        if self.restore_target_colors:
            color_time = np.clip((progress-self.dock_times)/(1-self.dock_times), 0, 1)
            correction = color_time**3*(color_time*(color_time*6-15)+10)
        else:
            correction = np.zeros(len(self.destinations), dtype=np.float32)
        landed = progress >= self.dock_times
        positions[landed] = self.ends[landed]
        return PieceLayout(positions, correction)

    def render(self, progress: float) -> Image.Image:
        if progress <= 0 or self.identical:
            return self.source.copy()
        if progress >= 1:
            return self.result.copy()
        state = self.layout(progress)
        colors = self.source_tiles
        correcting = state.correction > 0
        if correcting.any():
            colors = colors.copy()
            original = self.source_tiles[correcting].astype(np.float32)
            difference = self.target_tiles[correcting].astype(np.float32)-original
            colors[correcting] = np.uint8(np.clip(np.rint(original+difference*state.correction[correcting, None, None]), 0, 255))
        origins = np.rint(state.positions-self.half).astype(np.int32)
        if self.block_size == 1:
            xx, yy = origins[:, 0], origins[:, 1]
        else:
            xx = (origins[:, 0, None]+self.pixel_x).ravel()
            yy = (origins[:, 1, None]+self.pixel_y).ravel()
        valid = (xx >= 0) & (xx < self.width) & (yy >= 0) & (yy < self.height)
        frame = np.empty((self.height, self.width, 3), dtype=np.uint8)
        frame[:] = self.background
        frame[yy[valid], xx[valid]] = colors.reshape(-1, 3)[valid]
        return Image.fromarray(frame)
