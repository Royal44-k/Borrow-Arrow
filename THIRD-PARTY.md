# 来源与许可边界

仓库保留 Royal44 原有的 MIT LICENSE，适用于本项目原创软件代码；以下第三方组件、素材与合成声音分别遵循其原有许可和权利边界。

- Vue 3.5.44、Three.js 0.180.0：MIT，完整许可见 `licenses/`。三维船只通过项目代码构建，不包含从参考视频提取的模型。
- Pyodide 314.0.7：Mozilla Public License 2.0。发布的核心运行文件来自官方文档列出的 jsDelivr 固定版本路径；清单、URL 和 SHA-256 见 `docs/runtime-manifest.json`，完整许可见 `licenses/Pyodide-LICENSE.txt`。源码：[pyodide/pyodide 314.0.7](https://github.com/pyodide/pyodide/tree/314.0.7)。本项目未修改其运行时文件。
- 离线启动器内的 CPython 3.12.10 Windows x64 来自 [Python 官方下载](https://www.python.org/ftp/python/3.12.10/)，完整 PSF 及捆绑许可随包保留。它只用于在本机提供静态文件，不运行外部 AI 服务。
- 船身木纹 `wood_planks_dirt` 三张贴图来自 Poly Haven，CC0；原始地址、尺寸与 SHA-256 见 `docs/material-sources.json`，许可见 [Poly Haven License](https://polyhaven.com/license)。
- 场景与人物画面为项目设计过程中生成、编辑的素材；最新原图位于 `design-assets/v16/`，运行图在 `public/`。已有提示与来源记录保存在 `docs/assets.json`。生成素材不能被描述为历史影像或真人表演。
- 已生成对白音频与程序环境声为本课件体验资产；语音的合成来源和人物映射延续原版本记录。音频不会被标为真人录制，也不对合成服务或模型声音额外授予商用转授权。
- 汉代战争背景、小说情节及教学改编的依据与边界见 `docs/research-notes.md`；公开版试题内亦保留来源说明。引用文献不代表其作者背书本课件。

没有将用户提供的参考录像、平台完整课件、带其他创作者水印的截图作为网站资产上传。公开仓库可浏览与体验，不等于取得所有资源的无限再分发权。
