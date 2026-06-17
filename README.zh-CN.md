<p align="center">
  <img src="https://github.com/user-attachments/assets/d4f48f71-d76e-4ffe-9fb1-0b075d79bf05" alt="forza-painter FH6 logo" width="720">
</p>

<h1 align="center">forza-painter FH6</h1>

<p align="center">
  <strong>把图片转换成 Forza Horizon 6 Vinyl Group 的生成与导入工具。</strong>
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.zh-CN.md">中文</a> ·
  <a href="README.ko-KR.md">한국어</a>
</p>

<p align="center">
  <code>v1.9.1</code> · <code>Windows</code> · <code>Forza Horizon 6</code> · <code>GPU/OpenCL</code> · <code>单文件 EXE</code>
</p>

<p align="center">
  <a href="https://github.com/bvzrays/forza-painter-fh6/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=bvzrays/forza-painter-fh6" alt="Contributors" />
  </a>
</p>

把 PNG/JPG/BMP 图片转换成 Forza Horizon 6 的 Vinyl Group 图层。软件内完成生成、预览和导入，普通用户不需要 Python、`.venv`、批处理文件，也不需要手动填写内存地址。

> **下载 EXE：** 从 [Releases](https://github.com/bvzrays/forza-painter-fh6/releases) 下载 `forza-painter-fh6-v1.9.1.exe`，直接运行。

> **预设市场：** 可以在 https://painter6.com 浏览玩家分享的图片、预设和 JSON 包，也可以通过软件内的新市场横幅直接打开。

> **画面发糊先看这里：** 优先提高生成页里的 `Random samples / 随机样本`。随机样本数在 **200000 以上** 通常会有明显质变；数值越高越清晰，但生成时间也会明显增加。

> **导入可能需要等待：** v1.4.1 起会依次尝试多套 FH6 模板定位逻辑，最长可能需要 5 分钟。请保持 FH6 停留在 Vinyl Group Editor，不要切换菜单；若仍失败，请导出详细日志。

| 功能 | 说明 |
| --- | --- |
| 生成 JSON | 使用内置 GPU/OpenCL 生成器把图片转换成 geometry JSON。 |
| 预览结果 | 在软件内预览原图和生成后的几何图形。 |
| 导入 FH6 | 把 JSON 导入当前打开的 FH6 Vinyl Group Editor。 |
| 安全写入 | 写入前自动定位并验证当前可编辑图层表。 |
| 预设市场 | 从软件内打开 https://painter6.com，浏览玩家分享的图片、预设和 JSON 包。 |
| 自动更新 | 启动时检查新版本，发现更新时显示更新内容。 |

## 快速开始

1. 从 [Releases](https://github.com/bvzrays/forza-painter-fh6/releases) 下载 `forza-painter-fh6-v1.9.1.exe`。
2. 把 EXE 放在普通可写目录里，例如 `Desktop\forza-painter-fh6`。
3. 双击 EXE 启动。导入 FH6 时如果被 Windows 拦截进程访问，请用管理员身份运行 EXE。
4. 在游戏里进入 `Create Vinyl Group` / `Vinyl Group Editor`，加载球形模板并 `Ungroup`。
5. 在软件里生成 JSON，切到 `Import` 页面，填写游戏里显示的真实模板层数后导入。

不要下载 GitHub 自动生成的 `Source code` ZIP，除非你要开发项目。普通用户只需要 `.exe`。

## 效果预览

<table>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/app-import-preview.png" alt="软件导入页面"><br>
      <strong>软件导入页面</strong>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-template-ready.png" alt="FH6 模板准备"><br>
      <strong>游戏里准备模板</strong>
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-import-result.png" alt="FH6 导入效果"><br>
      <strong>导入完成效果</strong>
    </td>
    <td align="center" width="50%">
      <img src="docs/screenshots/fh6-car-applied.png" alt="FH6 车身贴图效果"><br>
      <strong>贴到车身效果</strong>
    </td>
  </tr>
</table>

## 生成 JSON

1. 进入 `Generate JSON` 页面。
2. 点击 `Add images`，添加 PNG/JPG/BMP 图片。
3. 选择品质配置。
4. 可选：开启 `Use custom settings`，修改输出层数、分辨率、随机样本和变异样本。
5. 点击底部固定的 `Start generating`。
6. 等待生成完成，右侧会显示预览，底部会显示日志。

生成的文件会保存在原图片旁边，例如 `image.500.json`、`image.1000.json`、`image.3000.json`。

同一张图片可能会生成多个 checkpoint JSON。导入时优先使用层数最高、最接近模板层数的 JSON；例如 3000 层模板应优先导入 `image.3000.json` 或最终 `image.json`。如果把 500 层 JSON 导入 3000 层模板，画面会明显发糊。

| 预设 | 输出层数 | 随机样本 | 用途 |
| --- | ---: | ---: | --- |
| extremely fast | 500 | 30000 | 快速看构图 |
| fast | 1000 | 60000 | 快速出可用稿 |
| balanced | 1800 | 120000 | 默认建议 |
| slow | 2500 | 220000 | 成品质量，开始进入 200k+ 提升区间 |
| super slow | 3000 | 350000 | 最高清晰度，耗时很长 |

## 导入 JSON

1. 启动 FH6，并保持 `Vinyl Group Editor` 打开。
2. 加载或创建一个由大量简单 sphere 图层组成的模板。
3. 把模板 `Ungroup`，并记住游戏里显示的真实层数。
4. 在软件 `Import` 页面点击 `Refresh`，选择正在运行的 `forzahorizon6.exe`。
5. 填写游戏里的真实模板层数。
6. 添加生成好的 `.json`，或者点击 `Use generated JSON`。
7. 高级地址输入框保持空白，点击 `Import JSON`。

FH 需要额外 4 个边界层来正确保存封面和贴车范围。例如：1000 层 JSON 建议使用至少 1004 层模板；3000 层模板实际可导入约 2996 个可绘制图形。

## 实验性区域绘制 (Region Paint)

区域绘制是一种迭代式绘画工作流，先生成全图基础图层，然后使用矩形或椭圆工具选择区域，仅对选中区域添加额外的细化图层。

- 添加单张图片，选择质量预设（将根据 `stopAt` 自动设置总预算），调整首轮和区域图层数量。
- 点击 `Start First Pass` 生成基础图层。预览将显示在右侧画布上。
- 在左侧画布上使用矩形或椭圆工具绘制选择区域。红色叠加层显示当前选区。
- 点击 `Paint Selected Region` 仅对所选区域添加更多图层。可重复操作每个区域。
- 所有轮次完成后，使用 `Open Result Folder` 或 `Save Result JSON` 获取最终的 `base.json`。
- 使用 `Import` 页面导入结果 JSON —— 与标准生成流程相同。
- 剩余预算显示在 `Remaining` 旁边。每次区域绘制都会消耗预算中的图层数。

## 必须注意

- 模板必须已经 Ungroup。
- 软件里的层数必须和游戏里的层数完全一致。
- 导入过程中不要切换菜单。
- 如果重启游戏、重新加载模板、改变模板层数，请用新的正确层数重新导入。
- 如果 JSON 比模板小，未使用的模板层会被隐藏。
- 如果 JSON 比模板大，超出的图形会被裁剪。
- 透明 PNG 的透明背景不会作为可见底色导入。

## 运行文件位置

单文件 EXE 会临时解压内部文件，并把正常运行数据放在 EXE 外部。软件启动日志会显示具体路径。

EXE 旁边可能出现这些外部文件夹：

- `runtime/`：日志、会话数据和临时文件。
- `webui-data/`：本地浏览器/UI 缓存。

关闭软件后可以删除这些文件夹，用于重置本地运行数据。

## 常见问题

- **无法导入 FH6：** 关闭软件，用管理员身份运行 EXE。
- **GPU/OpenCL 报错：** 更新 NVIDIA/AMD/Intel 显卡驱动。内置生成器使用 OpenCL。
- **定位不到模板：** 确认你在 Vinyl Group Editor，模板已经 Ungroup，层数填写完全正确，扫描期间没有切换菜单。
- **导入效果发糊：** 使用更高层数的 JSON，或提高 `Output layers` / `Random samples`。
- **需要排查问题：** 在软件里点击 `Export detailed log`，把导出的日志附到 issue。

## 资源链接

- 导入参考视频：https://www.bilibili.com/video/BV1hG5Z6nENZ
- 预设市场：https://painter6.com
- 内置 GPU 生成器来源/参考：https://github.com/zjl88858/forza-painter-geometrize-gpu
- 完整更新记录：[CHANGELOG.md](CHANGELOG.md)

## 更新日志

这里仅保留带版本号的发布记录。用于软件更新弹窗的完整记录见 [CHANGELOG.md](CHANGELOG.md)。

### v1.9.1 / 2026-06-17

- **区域绘制检查点** — 每次运行（首轮和每次区域绘制）现在都会保存独立的检查点 JSON、预览和热力图。可通过轮次历史列表在任意历史检查点之间自由切换，不会丢失数据。
  - 回滚后重新运行同一轮次会创建新的 attempt，不会覆盖之前的结果。
  - 在轮次历史中选择任意检查点，点击"恢复检查点"即可即时切换活跃状态、预览和热力图。
  - Step 4 操作按钮、轮次历史和结果按钮现在位于 Steps 1–3 下方的独立滚动区域中，改善小屏幕可用性。

### v1.9.0 / 2026-06-14

- **Text Vinyl（文字涂装）** — 新增Text标签页，支持从输入的Unicode文本生成FH6类型码JSON。支持拉丁字母、日文、韩文、中文（简体/繁体），界面已本地化。
  - 输入或粘贴文字即可生成涂装图层；可上传字体文件或浏览系统已安装的CJK字体（按字母排序）。
  - 集成DxBang颜色转换器，支持十六进制色值精确选色。
  - 已接入现有导入流程，并提供可关闭的圆形模板兼容性指引。
  - 像素艺术图像追踪器，可将图像转换为缩放类型码几何。
  - 跨标签页共享颜色色板系统，方便在不同工作流中复用颜色。

### v1.8.5 / 2026-06-13

- **区域绘制预算防呆**：当首轮图层数超过总预算时点击 `Start First Pass`，或已用图层数 + 区域图层数超过总预算时点击 `Paint Selected Region`，现在会显示明确的日志警告并停止，而非静默超出预算。
- **多方向拖拽支持**：区域绘制中的矩形和椭圆选择工具现支持任意方向拖拽（如从右下到左上）。此前非左上到右下方向的拖拽会导致蒙版生成错误。
- **清除蒙版改进**：`Clear All` 按钮（由 "Clear Mask" 重命名）清除所有选择蒙版。新增 `Clear Selected` 按钮仅删除当前选中的蒙版，未选中时会在日志中提示。
- **小屏幕无障碍支持**：在可滚动的 Step 3 区域内新增了 `Open Result Folder` 和 `Save Result JSON` 重复按钮，并带有 "(for small screens)" 提示，使笔记本用户在下部按钮不可见时仍能执行结果操作。

### v1.8.4 / 2026-06-07

- 区域绘制（Region Paint）所选形状现已支持**拖拽移动**、**角点缩放**和**旋转**（滑块、滚轮、输入框或画布手柄）。
- 新增一个推荐预设，可用相对较少的算力获得良好效果。

### v1.8.3 / 2026-06-06

- 在区域绘制（Region Paint）画布中新增**热力图**标签页，以颜色标尺展示生成图像中各区域的形状密度。每次轮次完成后自动生成热力图，并缓存以便即时切换。
- 显著提升区域绘制预览图像的生成速度。

### v1.8.2 / 2026-06-06

- 移除了区域绘制（Region Paint）第 3 步选择工具中的"羽化"控件。选择蒙版现在始终为硬边缘（0 羽化），修复了羽化导致"绘制选中区域"功能异常的问题。

### v1.8.1 / 2026-06-05

- 新增区域绘制（Region Paint）—— 全新的迭代式绘画工作流。首先生成全图基础图层，然后使用矩形或椭圆工具选择区域，仅对选中区域添加额外的细化图层。包含图层预算管理、轮次历史、实时预览画布和结果 JSON 导出。
- 修复了底部日志区域被 Notebook 标签页部分遮挡的问题。

### v1.8.0 / 2026-06-01

- 更新软件版本到 `v1.8.0`；发布文件现在使用 `forza-painter-fh6-v1.8.0.exe`。
- 新增实验性的全图形导入/导出流程：全图形导入并入 `导入` 页，当前游戏组导出放在 `导出` 页。
- 全图形导入/导出使用图层偏移 `0x7A` 的 16-bit 形状 word，并避免复制 `0xA8` 之类的易失资源指针。
- 加入 Kloudy's FH6 Painter custom-importer 归属说明和字体形状 registry，用于 type-code JSON 支持。

### v1.7.0 / 2026-06-01

- 更新软件版本到 `v1.7.0`；发布文件现在使用 `forza-painter-fh6-v1.7.0.exe`。
- 在生成、导入、工具和教程页面增加醒目的预设市场横幅。
- 新市场按钮会打开 https://painter6.com，方便用户直接浏览玩家分享的图片、预设和 JSON 包。

### v1.6.8 / 2026-05-28

- 更新软件版本到 `v1.6.8`；发布文件现在使用 `forza-painter-fh6-v1.6.8.exe`。
- 合并 GitHub `main` 最新改动，保留椭圆宽高浮点数，提高游戏内导入精度。
- 在预览区域增加提示：v1.6.8 会优先保证局内效果，预览仅供近似参考。
- JSON 预览改为超采样渲染，尽量降低浮点尺寸椭圆在预览里的锯齿和劣化。

### v1.6.7 / 2026-05-27

- 更新软件版本到 `v1.6.7`；发布文件现在使用 `forza-painter-fh6-v1.6.7.exe`。
- 内置 GPU 生成器更新到上游 `canary-26052702`。
- 将 FH6 导入缩放里的魔法数字改为圆形和矩形基准尺寸常量，方便后续明确调整游戏内圆形基准大小。
- 改进生成 ETA 估算，避免生成器批量输出或前期慢速阶段导致剩余时间长期严重不准。

### v1.6.6 / 2026-05-26

- 更新软件版本到 `v1.6.6`；发布文件现在使用 `forza-painter-fh6-v1.6.6.exe`。
- 增加繁体中文 UI 翻译，并改进右上角语言选择器布局。
- 修复 RGB 图片的 `luma_band` 预处理，预处理图片写入改为更安全的原子写入，并增加几何/颜色数据测试。
- 单文件 EXE 现在会打包 OpenCV 和 NumPy，确保 release 版也能使用 `luma_band` 预处理。
- 导入前现在必须填写 FH6 模板层数，避免空层数字段导致难以理解的自动定位或导入失败。
- 重构核心模块，加入类型化异常和共享工具函数。

### v1.6.5 / 2026-05-25

- 更新软件版本到 `v1.6.5`；发布文件现在使用 `forza-painter-fh6-v1.6.5.exe`。
- 内置 GPU 生成器更新到上游 `v1.2-Canary-20260525`。
- 内置预设默认设置 `forceOpaqueShapes = false`。
- 降低主程序在生成期间的额外开销：生成器使用清理后的环境变量，文件轮询频率降低，最重预设减少预览 PNG 写入。
- 修复开启预处理后生成输出追踪使用原图路径的问题。

### v1.6.1 / 2026-05-24

- 更新软件版本到 `v1.6.1`；发布文件现在使用 `forza-painter-fh6-v1.6.1.exe`。
- 内置预设默认关闭 `luma_band` 预处理。
- 导入时不再复用 `webui-data` 里的旧 FH6 会话定位数据，写入前会重新定位当前模板。
- JSON 预览改为使用稳定的单一路径渲染，避免不同打包环境下椭圆预览出现拉伸错乱。

### v1.6.0 / 2026-05-24

- 更新软件版本到 `v1.6.0`；发布文件现在使用 `forza-painter-fh6-v1.6.0.exe`。
- 内置 GPU 生成器更新到上游 `canary-26052401`。
- 加入上游 `errorGridSize` 预设参数支持。
- 集成上游透明区域防外溢算法调整。
- 透明图片最底部大椭圆的生成质量得到显著改善。

### v1.5.4 / 2026-05-23

- 修复高分辨率原图、生成器预览 PNG 和 JSON 预览的缩放显示，预览会按当前预览框等比适配，不再拉伸或只显示局部。
- 修复 JSON 预览里 type 16 旋转椭圆的绘制方式，Import 页预览不再把椭圆笔触压扁或错误旋转。

### v1.5.3 / 2026-05-22

- 增加适配单文件 EXE 的自定义预设导入、图片/JSON 列表移除、checkpoint 复用、输出命名修复和 Pillow 预览 fallback。

### v1.5.2 / 2026-05-22

- 增加真正的单文件 EXE，普通用户不再需要 Python、`.venv` 或额外 helper 文件。
- GUI EXE 可用自身的隐藏 helper 模式执行导入和 FH6 内存定位。
- Tools 页面和启动日志会显示外部运行/缓存文件保存位置。

### v1.5.1 / 2026-05-22

- 修复项目 `.venv` 已存在但其中 Python 缺少 `pip` 时的依赖安装失败问题。
- 改进源码包启动脚本的缺文件诊断提示。

### v1.5.0 / 2026-05-22

- 内置 GPU/OpenCL 生成器更新到上游 `canary-26052102`。
- 引入上游 PR #4 的 work-group evaluation 算法，加速 GPU 候选图形评估。
- 增加启动自动更新检查、根目录 `CHANGELOG.md` 和深色桌面 UI。

### v1.4.1 / 2026-05-21

- FH6 模板自动定位会先后尝试 v1.3 和 v1.4 两套扫描方案。
- 增加 RTTI vtable fallback，并拉长自动定位等待预算。

### v1.4.0 / 2026-05-21

- 增加“导出详细日志”按钮，导出内容上限为 50000 字符。
- 改进 FH6 大块可写内存区域的模板自动定位逻辑。

### v1.3.0 / 2026-05-21

- 内置 GPU/OpenCL 生成器更新到上游 `canary-26052101`。
- 引入上游显卡选择修复，并在生成日志中显示选中的 OpenCL 设备。

### v1.2.0 / 2026-05-20

- 内置 GPU/OpenCL 生成器更新到上游 `canary-26052001`。
- 内置预设和自定义生成配置会显式写入 `forceOpaqueShapes = true`。

### v1.1.1 / 2026-05-20

- 增加集中版本号管理，统一窗口标题、命令行和发布包名称。
- 整理仓库目录和发布包脚本。
