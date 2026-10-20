# Instrument Atelier：正式显示层接回

## 接收身份

- 基线：`42bd919a5a7cb60baec219d4716987e63458f5fc`，PR39 网页分支；目标 base 仍为 `codex-remote-stage-20261011-integration`。
- 用户提供 ZIP：`VICO_仪表工作室_完整交付.zip`，SHA256 `376e98cf8a82350de40d4403ce31f5de4c0938d16d2805645dd3ef36c43f1ff5`。
- 实际包内根目录 `VICO_Instrument_Atelier`；声明的1个HTML、25张截图、4个integration文件，共30项哈希全部匹配。未把粘贴文本里另一轮 Studio 版本当作本次输入。

## 接入内容

采用包内四个正式候选：`index.html`、`style.css`、`src/cockpit.js`、`src/factory-display.js`。保留六声音车型、五独立显示预设、明暗主题、数字布局和手机专用紧凑仪表。

本地接回时清除了候选中残留的预览/无声音文案、示例ARIA声明、预览专用存储分支和GPS示例选择器样式。正式控制器继续负责播放、输入、GPS、停止和诊断；生产页面不包含预览 adapter、示例 catalog、VicoPreview或测试状态开关。

`app.mjs`、`session.mjs`、`core.mjs`、`worklet.mjs`、`appearance.js` 保持原字节。真实声库从固定父Git对象 `477913e7500bb3ff13c3b72cf5b1a3cac1b28145` 构建；不修改WAV、manifest、gain、Android或main。

## 实际接线与测试

- 旧 cockpit 测试曾测试不走生产路径的备用 renderer。现在共享夹具加载实际 cockpit+factory 两个脚本，保留所有DOM监听器并从真实页面/SVG建立节点。
- Node覆盖实际模型读数、针角/量程饱和、完整主刻度/真实红线、偏好容错、主题/布局/响应式重绘、GPS未知、NaN失效与无声音/GPS所有权。
- `browser_factory_review.py`：六真实声库的实际AudioWorklet，六车/五预设/双主题/六尺寸，切换时验证runId、context、node、bank、volume、GPS身份与帧增长。
- `browser_atelier_review.py`：1,320项边界数值布局组合、GPS未知切风格/布局、车库尺寸与对比度。使用明确标注的显示API注入，**不是音频或实车测量**；检查真实字形尺寸、全部读数/单位、刻度/针轴碰撞、内部裁切、完整主刻度和停止命中。
- 原 `browser_factory_regressions.py` 入口委托到上述新结构完整检查，不再用不存在的R4选择器空跑。
- 原 cockpit、smoke 的结构选择器更新为新单位和转速段；输入失效、真实静音/停止、哈希错误恢复、加载取消和历史诊断检查保留。
- `browser_lifecycle.py` 继续在44.1/48/96kHz运行原33项检查；定位、隐藏页事件等注入边界仍按原回执标注。

远端离线验证只作为导入证据；Windows本机运行结果、失败日志、最终SHA/构建身份和CI状态记录于 workspace：`reports/vico-web-0cb610e8/atelier-reception-20261020/`。最终构建以其 `build-manifest.json` 中的干净提交为准。

## 交付边界

本阶段为用户要求的仓库提交，不自动更新服务器。实体Tesla浏览器/触控、真实道路GPS、人耳与声学资格不因显示层接入升级为通过。既有Kotlin/JS数字等价只在冻结算法/资产不变的前提下继承，不冒充本轮重跑。
