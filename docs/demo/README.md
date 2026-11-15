# README demo provenance

The README animation is a deterministic, service-free visualization of the
repository's tested bug-class fixture. It is evidence of helper behavior, not a
recording of an autonomous live remediation. It makes no model, Linear,
CodeIntel, product-repository, pull-request mutation or deployment call.

`synthetic_trial.py` runs the real bug-class helper against the existing
disposable fixture. `synthetic-trial.json` is its checked-in structured output.
`render_assets.py` turns that result into paired light/dark SVG frames. Every
frame keeps the same Mermaid-like six-step flow visible and changes only the
active ticket handoff:

1. Report — Capture bug
2. Intake — Freeze scope
3. Assess — Qualify finding
4. Repair — Restore boundary
5. Verify — Prove candidate
6. Draft PR — Carry proof

Regenerate the source frames and media from the repository root:

```sh
python3 docs/demo/synthetic_trial.py --json > /tmp/synthetic-trial.json
diff -u docs/demo/synthetic-trial.json /tmp/synthetic-trial.json
python3 docs/demo/render_assets.py

for theme in dark light; do
  for frame in docs/demo/frames/$theme/*.svg; do
    rsvg-convert --width 1280 --height 720 "$frame" \
      --output "${frame%.svg}.png"
  done
done

ffmpeg -y -framerate 2/3 -i docs/demo/frames/dark/%02d.png \
  -vf "fps=8,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96[p];[s1][p]paletteuse=dither=bayer" \
  docs/assets/dark-factory-demo.gif

ffmpeg -y -framerate 2/3 -i docs/demo/frames/light/%02d.png \
  -vf "fps=8,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96[p];[s1][p]paletteuse=dither=bayer" \
  docs/assets/dark-factory-demo-light.gif

cp docs/demo/frames/dark/01.png docs/assets/dark-factory-demo-poster.png

magick docs/assets/dark-factory-logo.png -colorspace gray \
  +level-colors '#f5fff7','#006b2d' \
  docs/assets/dark-factory-logo-light.png
```

The generated PNG frame intermediates are ignored. The repository publishes the
paired GIFs, a dark poster, paired logo PNGs, exact ANSI logo source and both
sets of SVG source frames. Keep the persistent synthetic qualification on every
frame when revising the story.
