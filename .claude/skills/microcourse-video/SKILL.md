---
name: microcourse-video
description: |
  Generate project microcourse video assets and renders from scripts, subtitles and narration.
  Use when user asks for microcourse videos, subtitle narration videos, project intro videos,
  digital-human-ready exports, or remotion-based educational video pipelines.
---

# microcourse-video

## Purpose

Create end-to-end microcourse videos for this project with:

- narration script
- subtitle file (.srt)
- voiceover audio
- remotion/ffmpeg render output
- digital-human-ready package (audio + srt + script)

## Recommended local workflow

1. Prepare script markdown (`video/microcourse/script.md`)
2. Build SRT subtitles (`video/microcourse/subtitles.srt`)
3. Generate narration audio (`video/microcourse/audio/narration.wav`)
4. Render video (`video/microcourse/output/microcourse.mp4`)
5. Export digital-human package (`video/microcourse/digital_human_package/*`)

## Commands

```bash
python3 video/microcourse/tools/generate_narration.py
python3 video/microcourse/tools/render_microcourse.py
```

## Outputs

- `video/microcourse/output/microcourse.mp4`
- `video/microcourse/output/microcourse_with_subtitles.mp4`
- `video/microcourse/digital_human_package/script.txt`
- `video/microcourse/digital_human_package/subtitles.srt`
- `video/microcourse/digital_human_package/narration.wav`
