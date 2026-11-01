import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from morph_engine import MorphEngine, fit_image, load_image, make_demo_images


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.size = (192, 120)
        self.source, self.target = make_demo_images(self.size)
        self.engine = MorphEngine(self.source, self.target, self.size, 12)

    def test_endpoints_match_images_exactly_in_both_modes(self):
        for mode in ('pixels', 'convolution'):
            np.testing.assert_array_equal(self.engine.render(0, mode), self.source)
            np.testing.assert_array_equal(self.engine.render(1, mode), self.target)

    def test_middle_frame_changes_and_is_deterministic(self):
        for mode in ('pixels', 'convolution'):
            frame = np.asarray(self.engine.render(.5, mode))
            self.assertGreater(np.mean(np.abs(frame.astype(float) - np.asarray(self.source))), 5)
            self.assertGreater(np.mean(np.abs(frame.astype(float) - np.asarray(self.target))), 5)
            np.testing.assert_array_equal(frame, self.engine.render(.5, mode))

    def test_modes_produce_different_middle_frames(self):
        self.assertFalse(np.array_equal(self.engine.render(.5, 'pixels'), self.engine.render(.5, 'convolution')))

    def test_destination_assignment_is_one_to_one(self):
        self.assertEqual(len(set(self.engine.destinations.tolist())), len(self.engine.destinations))
        self.assertEqual(sorted(self.engine.destinations.tolist()), list(range(len(self.engine.destinations))))

    def test_progress_is_clamped(self):
        np.testing.assert_array_equal(self.engine.render(-2, 'pixels'), self.source)
        np.testing.assert_array_equal(self.engine.render(9, 'pixels'), self.target)

    def test_uniform_image_does_not_darken_during_particle_motion(self):
        image = Image.new('RGB', (96, 60), (160, 130, 105))
        engine = MorphEngine(image, image, (96, 60), 8)
        for progress in (.1, .3, .5, .7, .9):
            np.testing.assert_array_equal(engine.render(progress), image)

    def test_original_texture_and_colors_survive_disassembly_and_transport(self):
        array = np.zeros((64, 96, 3), dtype=np.uint8)
        array[:, ::2] = (230, 40, 20)
        array[:, 1::2] = (30, 50, 220)
        source = Image.fromarray(array)
        target = Image.new('RGB', source.size, (10, 240, 80))
        engine = MorphEngine(source, target, source.size, 8)
        palette = {(230, 40, 20), (30, 50, 220), (16, 23, 29)}
        for progress in (.12, .35, .55):
            frame = np.asarray(engine.render(progress))
            actual = set(map(tuple, frame.reshape(-1, 3).tolist()))
            self.assertTrue(actual <= palette, 'Moving parts must keep their original pixels, without target-image underlay')
            self.assertIn((230, 40, 20), actual)
            self.assertIn((30, 50, 220), actual)

    def test_pieces_disassemble_then_all_dock_at_unique_destinations(self):
        parts = self.engine.parts
        count = self.engine.rows*self.engine.columns
        for progress in (.0, .2, .5, .8, 1):
            state = parts.layout(progress)
            self.assertEqual(len(state.positions), count)
            self.assertTrue(np.isfinite(state.positions).all())
        np.testing.assert_allclose(parts.layout(0).positions, parts.starts)
        np.testing.assert_allclose(parts.layout(1).positions, parts.ends)
        self.assertGreater(np.linalg.norm(parts.layout(.2).positions-parts.starts, axis=1).mean(), 1)
        self.assertEqual(len(np.unique(parts.layout(1).positions, axis=0)), count)

    def test_details_change_only_when_individual_pieces_have_docked(self):
        parts = self.engine.parts
        for progress in (.2, .5, .72, .85, .95):
            state = parts.layout(progress)
            correcting = state.correction > 0
            np.testing.assert_allclose(state.positions[correcting], parts.ends[correcting], atol=.001)
        self.assertFalse(np.any(parts.layout(.55).correction))
        np.testing.assert_allclose(parts.layout(1).correction, 1)

    def test_unchecked_mode_does_not_replace_white_source_with_target_grays(self):
        source = Image.new('RGB', (96, 64), (248, 246, 242))
        target = make_demo_images(source.size)[1]
        engine = MorphEngine(source, target, (120, 80), 1, restore_target_colors=False)
        np.testing.assert_array_equal(np.asarray(engine.render(1)), np.full((80, 120, 3), (248, 246, 242), dtype=np.uint8))
        self.assertFalse(np.any(engine.parts.layout(.95).correction))

    def test_unchecked_mode_preserves_every_source_pixel_color_and_brightness(self):
        rng = np.random.default_rng(16)
        source = Image.fromarray(rng.integers(180, 256, (48, 64, 3), dtype=np.uint8))
        target = make_demo_images(source.size)[1]
        engine = MorphEngine(source, target, source.size, 1, restore_target_colors=False)
        def rgb_counts(image):
            colors, counts = np.unique(np.asarray(image).reshape(-1, 3), axis=0, return_counts=True)
            return colors, counts
        expected_colors, expected_counts = rgb_counts(source)
        colors, counts = rgb_counts(engine.render(1))
        np.testing.assert_array_equal(colors, expected_colors)
        np.testing.assert_array_equal(counts, expected_counts)
        for progress in (.2, .5, .85, .98):
            self.assertFalse(np.any(engine.parts.layout(progress).correction))

    def test_one_pixel_pieces_are_supported_and_checked_mode_restores_target(self):
        source, target = make_demo_images((96, 64))
        full_color = MorphEngine(source, target, source.size, 1, restore_target_colors=True)
        self.assertEqual(full_color.block_size, 1)
        self.assertEqual(full_color.parts.source_tiles.shape, (96*64, 1, 3))
        np.testing.assert_array_equal(full_color.render(1), target)

    def test_reported_white_background_image_retains_exact_pixel_counts(self):
        source = load_image(Path(__file__).parent/'fixtures'/'white-background-source.png')
        target = load_image(Path(__file__).resolve().parents[1]/'assets'/'default_target.png')
        engine = MorphEngine(source, target, (144, 90), 1, restore_target_colors=False)
        original_colors, original_counts = np.unique(np.asarray(engine.source).reshape(-1, 3), axis=0, return_counts=True)
        final_colors, final_counts = np.unique(np.asarray(engine.render(1)).reshape(-1, 3), axis=0, return_counts=True)
        np.testing.assert_array_equal(final_colors, original_colors)
        np.testing.assert_array_equal(final_counts, original_counts)
        self.assertGreater(np.asarray(engine.render(1)).mean(), 180)

    def test_fit_preserves_entire_image_without_stretching(self):
        original = Image.new('RGB', (40, 80), 'red')
        fitted = fit_image(original, (100, 100))
        self.assertEqual(fitted.size, (100, 100))
        self.assertEqual(fitted.getpixel((50, 0)), (255, 0, 0))
        self.assertNotEqual(fitted.getpixel((0, 50)), (255, 0, 0))

    def test_transparent_pixels_are_composited(self):
        fitted = fit_image(Image.new('RGBA', (20, 20), (255, 0, 0, 0)), (20, 20))
        self.assertEqual(fitted.mode, 'RGB')
        self.assertNotEqual(fitted.getpixel((5, 5)), (255, 0, 0))

    def test_load_image_and_invalid_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'image.png'
            Image.new('RGB', (32, 40), 'red').save(path)
            self.assertEqual(load_image(path).size, (32, 40))
            path.write_bytes(b'not an image')
            with self.assertRaises(ValueError):
                load_image(path)

    def test_exif_orientation_is_applied(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'rotated.jpg'
            exif = Image.Exif()
            exif[274] = 6
            Image.new('RGB', (30, 50), 'blue').save(path, exif=exif)
            self.assertEqual(load_image(path).size, (50, 30))


if __name__ == '__main__':
    unittest.main()
