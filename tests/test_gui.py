import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path

from PIL import Image

from app import MorphApp
from morph_engine import fit_image, load_image


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = MorphApp(self.root)
        self.folder = tempfile.TemporaryDirectory()
        self.source = Path(self.folder.name)/'原图.png'
        self.target = Path(self.folder.name)/'目标.png'
        Image.new('RGB', (60, 40), 'red').save(self.source)
        Image.new('RGB', (40, 60), 'blue').save(self.target)

    def tearDown(self):
        self.app.close()
        self.folder.cleanup()

    def prepare(self):
        self.app.set_image('source', self.source)
        self.app.set_image('target', self.target)

    def test_default_target_is_loaded_and_only_source_is_required(self):
        self.assertEqual(self.root.title(), '讲解石生成器')
        self.assertIsNone(self.app.source_original)
        expected = load_image(Path(__file__).resolve().parents[1]/'assets'/'default_target.png')
        self.assertEqual(self.app.target_original.tobytes(), expected.tobytes())
        self.assertIn('默认', self.app.target_label.cget('text'))
        self.assertTrue(self.app.play_button.instate(['disabled']))
        self.app.set_image('source', self.source)
        self.assertFalse(self.app.play_button.instate(['disabled']))
        self.assertEqual(self.app.play_button.cget('text'), '开始')
        self.app.restore_target_colors.set(True)
        self.app.on_color_option()
        self.app.set_progress(1)
        self.assertEqual(self.app.current_frame.tobytes(), fit_image(expected, (960, 600)).tobytes())

    def test_custom_target_can_replace_default(self):
        self.app.set_image('target', self.target)
        self.assertEqual(self.app.target_original.getpixel((0, 0))[:3], (0, 0, 255))
        self.assertEqual(self.app.target_name, '目标.png')
        self.assertNotIn('默认', self.app.target_label.cget('text'))
        self.assertTrue(self.app.play_button.instate(['disabled']))
        self.app.set_image('source', self.source)
        self.assertFalse(self.app.play_button.instate(['disabled']))

    def test_animation_uses_finer_particles_and_shorter_duration(self):
        self.app.set_image('source', self.source)
        self.assertEqual(self.app.engine.block_size, 1)
        self.assertGreaterEqual(self.app.duration, 5)
        self.assertLessEqual(self.app.duration, 6)

    def test_color_option_defaults_to_source_colors_and_can_restore_target(self):
        self.assertFalse(self.app.restore_target_colors.get())
        self.app.set_image('source', self.source)
        self.app.set_progress(1)
        first = self.app.current_frame.tobytes()
        self.app.restore_target_colors.set(True)
        self.app.on_color_option()
        self.assertEqual(self.app.progress, 0)
        self.app.set_progress(1)
        expected = fit_image(self.app.target_original, (960, 600))
        self.assertEqual(self.app.current_frame.tobytes(), expected.tobytes())
        self.assertNotEqual(first, expected.tobytes())

    def test_invalid_upload_keeps_previous_image_and_progress(self):
        self.prepare()
        self.app.set_progress(.45)
        previous = self.app.source_original
        self.source.write_bytes(b'broken')
        with self.assertRaises(ValueError):
            self.app.set_image('source', self.source)
        self.assertIs(self.app.source_original, previous)
        self.assertEqual(self.app.progress, .45)

    def test_play_pause_resume_finish_and_restart(self):
        self.prepare()
        self.app.toggle_play()
        self.assertTrue(self.app.playing)
        self.app.tick(time.perf_counter()+1)
        self.assertGreater(self.app.progress, 0)
        self.app.toggle_play()
        self.assertFalse(self.app.playing)
        self.app.set_progress(.65)
        self.app.toggle_play()
        self.assertTrue(self.app.playing)
        self.app.tick(time.perf_counter()+20)
        self.assertEqual(self.app.progress, 1)
        self.assertFalse(self.app.playing)
        self.assertEqual(self.app.play_button.cget('text'), '重新开始')
        self.app.toggle_play()
        self.assertLess(self.app.progress, .01)

    def test_export_current_frame(self):
        self.prepare()
        self.app.set_progress(.5)
        path = Path(self.folder.name)/'frame.png'
        self.app.save_frame(path)
        with Image.open(path) as image:
            self.assertEqual(image.size, (960, 600))

    def test_only_two_visible_action_buttons(self):
        self.root.deiconify()
        self.root.update()
        self.assertEqual(len(self.app.button_bar.winfo_children()), 2)
        for button in self.app.button_bar.winfo_children():
            self.assertTrue(button.winfo_ismapped())


if __name__ == '__main__':
    unittest.main()
