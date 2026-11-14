# README demo provenance

The README animation is a deterministic, service-free visualization of the
repository's tested bug-class fixture. It is evidence of helper behavior, not a
recording of an autonomous live remediation. It makes no model, Linear,
CodeIntel, product-repository, pull-request mutation or deployment call.

`synthetic_trial.py` runs the real bug-class helper against the existing
disposable fixture. `synthetic-trial.json` is its checked-in structured output.
`render_assets.py` turns that result into five source SVG frames which explain
the handoffs without exposing a local host path or private ticket.

Regenerate the source frames and media from the repository root:

```sh
python3 docs/demo/synthetic_trial.py --json > /tmp/synthetic-trial.json
diff -u docs/demo/synthetic-trial.json /tmp/synthetic-trial.json
python3 docs/demo/render_assets.py
for frame in docs/demo/frames/*.svg; do
  rsvg-convert --width 1280 --height 720 "$frame" --output "${frame%.svg}.png"
done
ffmpeg -y -framerate 1/2 -i docs/demo/frames/%02d.png \
  -vf "fps=8,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=64[p];[s1][p]paletteuse=dither=bayer" \
  docs/assets/dark-factory-demo.gif
ffmpeg -y -framerate 1/2 -i docs/demo/frames/%02d.png \
  -vf "fps=30,scale=1280:-2:flags=lanczos,format=yuv420p" \
  -c:v libvpx-vp9 -crf 34 -b:v 0 docs/assets/dark-factory-demo.webm
cp docs/demo/frames/01.png docs/assets/dark-factory-demo-poster.png
cp docs/demo/frames/01.png docs/assets/dark-factory-demo-report.png
cp docs/demo/frames/03.png docs/assets/dark-factory-demo-repair.png
cp docs/demo/frames/05.png docs/assets/dark-factory-demo-learn.png
rsvg-convert --width 1200 --height 400 docs/assets/dark-factory-logo.svg \
  --output docs/assets/dark-factory-logo.png
```

The PNG frames are reproducible intermediates and are ignored. Three named
static frames, the poster, source SVGs, GIF and WebM are published. Keep the
persistent synthetic qualification on every frame when revising the story.
