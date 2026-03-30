# 200+页三主题教学PPT生成说明

## 目标

- 按 `docs/university-teaching-deck-100p-outline.md` 教学主线扩展到 200+ 页。
- 统一生成 3 个主题版本：
  - `dark-enterprise`
  - `dark-tech`
  - `light-gradient`（浅色渐变）
- 每页保持图文并茂，代码页/图片页包含简短讲解区域。

## 生成脚本

- `scripts/build_university_ppt_200_multi_theme.js`

## 输出文件

- `deliverables/Enterprise_Travel_Agent_University_210p_dark-enterprise.pptx`
- `deliverables/Enterprise_Travel_Agent_University_210p_dark-tech.pptx`
- `deliverables/Enterprise_Travel_Agent_University_210p_light-gradient.pptx`

## 快速运行

```powershell
Set-Location "D:\移动云盘同步盘\enterprise-travel-agent"
npm run build:ppt:teaching:200:themes
```

## 说明

- 页面总数按规划为 210 页（10个章节 * 20页 + 10页总览/导入）。
- 若后续需要“按截图逐页微调”，建议先记录页码和主题版本。
- 代码片段会自动截断为适合投影阅读的长度。

