# generate-Mr.chiang

**讲解石生成器：像素已经集结，优势在我。**

> 来自中原一群伙伴
>
> —— [《东南苦行山》](https://www.mulanci.org/lyric/sl88034/)

这次集合的，是你硬盘里的 576000 个像素。

给委座一张图片，让他亲自微操：拆开、调动、重新排列。大约 5.5 秒以后，你的猫、表情包或者风景照，就会逐渐长出一种熟悉的气质。

没什么正经用途，主要负责让人看完说一句：**怎么又是你啊。**

## 先把委座请到电脑里

- [下载 generate-Mr.chiang.exe](https://github.com/MYFSillyBa/generate-Mr.chiang/releases/download/v1.0.0/generate-Mr.chiang.exe)：单文件，双击就能指挥。
- [下载便携 ZIP](https://github.com/MYFSillyBa/generate-Mr.chiang/releases/download/v1.0.0/generate-Mr.chiang-v1.0.0-windows-x64.zip)：整支部队打包带走，解压后打开“讲解石生成器.exe”。

Windows 上直接运行，不用先给电脑补习 Python。[其他版本在这里。](https://github.com/MYFSillyBa/generate-Mr.chiang/releases)

## 三步完成战略转进

1. **点击虚线框，征召一张图片。** 猫猫、风景、奇怪的表情包，都可以。
2. **确认指挥官。** 默认目标图已经内置，委座正在待命。想换别人，就点“更换目标图片”。
3. **点击“开始”。** 接下来是约 5.5 秒的像素级微操，颗粒细到 1 像素。

过程中可以暂停、继续，结束后还能重新来一遍。战局不满意，随时换张原图。

## 那个颜色框，决定要不要全体换装

- **不勾“还原目标图颜色”**：只调兵，不换军装。每个像素只挪位置，颜色和亮度都保留。黄的还是黄，白的还是白。
- **勾上“还原目标图颜色”**：全体换装，拼到最后连颜色也一起还原成目标图。

所以，纯白图片不会凭空变出一件黑西装。委座可以调动像素，但不能无中生有地征兵。

## 微操战果

左边是原图，右边是不勾选还原颜色的结果。黄色部队还在，排列已经被接管。

![左：原图；右：保留原色的像素重排结果](assets/reported-image-comparison.png)

## 还能再微操两下

- **空格**：开始 / 暂停。先别急，容委座看一眼地图。
- **右键画面 → 保存当前图片**：把战果带走，导出为 960×600 的 PNG。
- **Ctrl+O / Ctrl+T**：分别更换原图 / 目标图。
- **Ctrl+S**：保存当前画面。
- **Esc**：暂停，先稳住阵脚。

图片全在本机处理，你的猫不会被征调到什么神秘服务器。

<details>
<summary>会 Python 的参谋，请进指挥部</summary>

Python 3.11 或更新版本，带 Tkinter。安装依赖后直接运行：

```powershell
python -m pip install -r requirements.txt
python app.py
```

查查微操有没有出岔子，再打包：

```powershell
python -m unittest discover -s tests -v
powershell -ExecutionPolicy Bypass -File .\build.ps1
python tools/package_release.py
```

`app.py` 管窗口，`morph_engine.py` 管读图，`piece_transition.py` 管调兵。关着颜色选项时，只排列原有像素，不偷偷往部队里塞目标图的颜色或灰度。

</details>
