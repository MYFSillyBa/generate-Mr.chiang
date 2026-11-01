"""讲解石生成器：原生 Windows 窗口、两张图片、一段变换动画。"""

import ctypes
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from morph_engine import MorphEngine, fit_image, load_image


APP_NAME = '讲解石生成器'
DEFAULT_TARGET_PATH = Path(__file__).resolve().parent/'assets'/'default_target.png'


class MorphApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.source_original = None
        self.target_original = load_image(DEFAULT_TARGET_PATH)
        self.source_name = ''
        self.target_name = '讲解师.png（默认）'
        self.engine = None
        self.current_frame = None
        self.progress = 0.0
        self.playing = False
        self.duration = 5.5
        self.restore_target_colors = tk.BooleanVar(root, False)
        self._start_time = 0.0
        self._after_id = None
        self._resize_id = None
        self._closed = False
        self._photo = None
        root.title(APP_NAME)
        scale = max(1.0, root.winfo_fpixels('1i')/96)
        width = min(round(760*scale), root.winfo_screenwidth()-80)
        height = min(round(560*scale), root.winfo_screenheight()-100)
        root.geometry(f'{width}x{height}+{max(0, (root.winfo_screenwidth()-width)//2)}+{max(0, (root.winfo_screenheight()-height)//2)}')
        root.minsize(min(round(460*scale), width), min(round(340*scale), height))
        root.protocol('WM_DELETE_WINDOW', self.close)
        icon_path = Path(__file__).resolve().parent/'assets'/'app.ico'
        if icon_path.exists():
            root.iconbitmap(str(icon_path))
        style = ttk.Style(root)
        if 'vista' in style.theme_names():
            style.theme_use('vista')
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        container = ttk.Frame(root, padding=round(12*scale))
        container.grid(row=0, column=0, sticky='nsew')
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(container, bg='SystemWindow' if sys.platform == 'win32' else 'white', highlightthickness=0, bd=0, cursor='hand2')
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.canvas.bind('<Button-1>', lambda event: self.choose_image('source'))
        self.canvas.bind('<Configure>', self._resize_preview)
        self.canvas.bind('<Button-3>', self._show_context_menu)
        self.button_bar = ttk.Frame(container)
        self.button_bar.grid(row=1, column=0, pady=round(12*scale))
        self.play_button = ttk.Button(self.button_bar, text='开始', width=12, command=self.toggle_play, state='disabled')
        self.play_button.grid(row=0, column=0, padx=(0, round(12*scale)))
        self.target_button = ttk.Button(self.button_bar, text='更换目标图片…', command=lambda: self.choose_image('target'))
        self.target_button.grid(row=0, column=1)
        self.color_option = ttk.Checkbutton(container, text='还原目标图颜色', variable=self.restore_target_colors, command=self.on_color_option)
        self.color_option.grid(row=2, column=0, pady=(0, round(8*scale)))
        self.target_label = ttk.Label(container, text='目标图片：'+self.target_name, anchor='w')
        self.target_label.grid(row=3, column=0, sticky='ew', pady=(0, 4))
        self.status = ttk.Label(container, text='请点击虚线框上传原始图片。', anchor='w')
        self.status.grid(row=4, column=0, sticky='ew')
        self.context_menu = tk.Menu(root, tearoff=False)
        self.context_menu.add_command(label='上传原始图片…', command=lambda: self.choose_image('source'))
        self.context_menu.add_command(label='上传目标图片…', command=lambda: self.choose_image('target'))
        self.context_menu.add_separator()
        self.context_menu.add_command(label='保存当前图片…', command=self.export_dialog)
        root.bind('<space>', self._keyboard_play)
        self.play_button.bind('<space>', lambda event: self._keyboard_play(event, force=True))
        root.bind('<Control-o>', lambda event: self.choose_image('source'))
        root.bind('<Control-t>', lambda event: self.choose_image('target'))
        root.bind('<Control-s>', lambda event: self.export_dialog())
        root.bind('<Escape>', lambda event: self.pause())
        self._resize_id = root.after_idle(self._display_frame)

    def choose_image(self, slot):
        self.pause()
        path = filedialog.askopenfilename(parent=self.root, title='上传原始图片' if slot == 'source' else '上传目标图片', filetypes=[('图片文件', '*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif'), ('所有文件', '*.*')])
        if not path:
            return
        try:
            self.set_image(slot, path)
        except ValueError as error:
            messagebox.showerror(APP_NAME, str(error), parent=self.root)

    def set_image(self, slot: str, path: str | Path):
        if slot not in ('source', 'target'):
            raise ValueError('未知图片位置。')
        image = load_image(path)
        source = image if slot == 'source' else self.source_original
        target = image if slot == 'target' else self.target_original
        engine = MorphEngine(source, target, block_size=1, restore_target_colors=self.restore_target_colors.get()) if source is not None and target is not None else None
        # Commit only after decoding and preparation succeed.
        self.pause()
        setattr(self, f'{slot}_original', image)
        setattr(self, f'{slot}_name', Path(path).name)
        self.engine = engine
        self.progress = 0.0
        self.current_frame = engine.render(0) if engine is not None else (fit_image(source, (960, 600)) if source is not None else None)
        name = self.target_name
        self.target_label.configure(text='目标图片：'+(name if len(name) < 48 else name[:22]+'…'+name[-20:]) if name else '目标图片：未选择')
        self.target_button.configure(text='更换目标图片…' if self.target_original is not None else '上传目标图片…')
        self.play_button.configure(state='normal' if engine is not None else 'disabled', text='开始')
        self._display_frame()
        self._update_status()

    def on_color_option(self):
        if self.source_original is None or self.target_original is None:
            return
        self.pause()
        self.engine = MorphEngine(self.source_original, self.target_original, block_size=1, restore_target_colors=self.restore_target_colors.get())
        self.set_progress(0)

    def _keyboard_play(self, event, force=False):
        if not force and isinstance(event.widget, ttk.Button):
            return None
        self.toggle_play()
        return 'break'

    def toggle_play(self):
        if self.engine is None:
            return
        if self.playing:
            self.pause()
            return
        if self.progress >= 1:
            self.set_progress(0)
        self.playing = True
        self._start_time = time.perf_counter()-self.progress*self.duration
        self.play_button.configure(text='暂停')
        self._update_status()
        self._schedule_tick()

    def _schedule_tick(self, delay_ms=16):
        if self.playing and not self._closed and self._after_id is None:
            self._after_id = self.root.after(delay_ms, self._tick_callback)

    def _tick_callback(self):
        self._after_id = None
        started = time.perf_counter()
        self.tick()
        elapsed_ms = int((time.perf_counter()-started)*1000)
        self._schedule_tick(max(1, 16-elapsed_ms))

    def tick(self, now=None):
        if not self.playing:
            return
        now = time.perf_counter() if now is None else now
        self.progress = max(0, min(1, (now-self._start_time)/self.duration))
        self.current_frame = self.engine.render(self.progress, 'pixels')
        self._display_frame()
        if self.progress >= 1:
            self.pause()
        self._update_status()

    def pause(self):
        self.playing = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        if self.progress >= 1:
            text = '重新开始'
        elif self.progress > 0:
            text = '继续'
        else:
            text = '开始'
        self.play_button.configure(text=text)
        self._update_status()

    def set_progress(self, progress):
        self.pause()
        self.progress = max(0, min(1, float(progress)))
        if self.engine is not None:
            self.current_frame = self.engine.render(self.progress, 'pixels')
        self._display_frame()
        self.pause()

    def _update_status(self):
        if self.engine is None:
            text = '请点击虚线框上传原始图片。' if self.source_original is None else '请上传目标图片。'
        elif self.progress >= 1:
            text = '已完成。右键点击画面可保存图片。' if self.restore_target_colors.get() else '已完成：仅重排原图像素，颜色和亮度未改变。'
        elif self.playing:
            text = f'正在生成… {self.progress:.0%}'
        elif self.progress > 0:
            text = f'已暂停。{self.progress:.0%}'
        else:
            text = '已就绪，点击“开始”。' + ('将还原目标图颜色。' if self.restore_target_colors.get() else '仅重排原图像素，颜色和亮度不变。')
        self.status.configure(text=text)

    def _resize_preview(self, event):
        if self._resize_id is not None:
            self.root.after_cancel(self._resize_id)
        self._resize_id = self.root.after(50, self._display_frame)

    def _display_frame(self):
        if self._resize_id is not None:
            self.root.after_cancel(self._resize_id)
            self._resize_id = None
        if self._closed:
            return
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width < 16 or height < 16:
            return
        self.canvas.delete('all')
        if self.current_frame is None:
            self.canvas.create_text(width/2, height/2, text='点击此处上传原始图片', fill='SystemGrayText' if sys.platform == 'win32' else '#777777', font='TkDefaultFont')
        else:
            available = (max(1, width-24), max(1, height-24))
            ratio = min(available[0]/self.current_frame.width, available[1]/self.current_frame.height)
            size = (max(1, int(self.current_frame.width*ratio)), max(1, int(self.current_frame.height*ratio)))
            self._photo = ImageTk.PhotoImage(self.current_frame.resize(size, Image.Resampling.BILINEAR), master=self.root)
            self.canvas.create_image(width/2, height/2, image=self._photo)
        self.canvas.create_rectangle(3, 3, width-4, height-4, outline='SystemGrayText' if sys.platform == 'win32' else '#999999', dash=(5, 4), width=1)

    def _show_context_menu(self, event):
        self.context_menu.entryconfigure(3, state='normal' if self.current_frame is not None else 'disabled')
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def save_frame(self, path):
        if self.current_frame is None:
            raise ValueError('请先上传原始图片。')
        self.current_frame.save(path, format='PNG')

    def export_dialog(self):
        if self.current_frame is None:
            return
        self.pause()
        path = filedialog.asksaveasfilename(parent=self.root, title='保存当前图片（960 × 600）', initialfile=f'讲解石_{round(self.progress*100):03d}.png', defaultextension='.png', filetypes=[('PNG 图片', '*.png')])
        if path:
            try:
                self.save_frame(path)
                self.status.configure(text='图片已保存。')
            except OSError as error:
                messagebox.showerror(APP_NAME, f'保存失败，请选择可写入的位置。\n{error}', parent=self.root)

    def close(self):
        self._closed = True
        self.pause()
        if self._resize_id is not None:
            self.root.after_cancel(self._resize_id)
            self._resize_id = None
        self.root.update_idletasks()
        self.root.destroy()


def main():
    if sys.platform == 'win32':
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    app = MorphApp(root)
    smoke_errors = []
    if '--smoke-test' in sys.argv:
        def smoke_error(exception_type, exception, traceback_object):
            import traceback
            smoke_errors.append(str(exception))
            Path('smoke-test-error.log').write_text(''.join(traceback.format_exception(exception_type, exception, traceback_object)), encoding='utf-8')
            app.close()

        root.report_callback_exception = smoke_error

        def finish_smoke_test():
            app.tick(app._start_time+app.duration+.01)
            assert app.progress == 1 and not app.playing
            assert app.current_frame.tobytes() == app.engine.target.tobytes()
            import numpy as np
            def palette(image):
                rgb = np.asarray(image).reshape(-1, 3).astype(np.uint32)
                return np.sort((rgb[:, 0]<<16)|(rgb[:, 1]<<8)|rgb[:, 2])
            assert np.array_equal(palette(app.current_frame), palette(app.engine.source))
            assert app.engine.block_size == 1
            app.restore_target_colors.set(True)
            app.on_color_option()
            assert app.progress == 0
            app.set_progress(1)
            assert app.current_frame.tobytes() == fit_image(app.target_original, (960, 600)).tobytes()
            app.close()

        def smoke_test():
            import tempfile
            from morph_engine import make_demo_images
            try:
                with tempfile.TemporaryDirectory() as folder:
                    if '--smoke-source' in sys.argv:
                        path = Path(sys.argv[sys.argv.index('--smoke-source')+1])
                    else:
                        path = Path(folder)/'source.png'
                        make_demo_images()[0].save(path)
                    app.set_image('source', path)
                    assert app.target_original.tobytes() == load_image(DEFAULT_TARGET_PATH).tobytes()
                    assert not app.play_button.instate(['disabled'])
                    app.set_progress(.5)
                    app.save_frame(Path(folder)/'output.png')
                    app.toggle_play()
                    root.after(350, finish_smoke_test)
            except Exception:
                smoke_error(*sys.exc_info())
        root.after(250, smoke_test)
    root.mainloop()
    if smoke_errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
