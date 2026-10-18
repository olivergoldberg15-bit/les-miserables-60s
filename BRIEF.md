# BRIEF: "Les Misérables in 60 seconds" (build contract for every worker)

Read this whole file before writing code. SCRIPT.md has the narration and the fact check.
You cannot open a browser in your workspace, so write simple, robust code; the coordinator renders and reviews every frame.

## 1. Deliverable

- 1920x1080, 30 fps, about 60 s. HyperFrames composition rendered from `index.html`.
- 3D in code with three.js r181 (`node_modules/three`, import map `"three"` and `"three/addons/"`). No external images, no downloads, no AI-generated media. Textures are procedural (canvas 2D or data textures).
- One rigged asset exists: `vendor/Xbot.glb` (Mixamo X Bot from the three.js repo; clips include idle, walk, run; it faces +Z).
- Narration is the user's own voice, recorded later. `data/timing.js` sets `window.TIMING = {duration, lines:[{id,text,start,end,words:[{w,s,e}]}]}`. It is a stand-in now and WILL change. Never hard-code a time: every time comes from `cue()`, `lineStart()`, `lineEnd()` or the shot boundaries.

## 2. Look: "realistic", like a period film shot on a real camera

- Photographic, not cartoon, not neon. ACES Filmic tone mapping, sRGB output, physically based materials (MeshStandardMaterial / MeshPhysicalMaterial) with procedural roughness and normal detail so nothing is a flat color.
- Light like a cinematographer: one motivated key per shot (low dusk sun, candle, lantern, moon, dawn), soft fill, rim to separate silhouettes. Candle and lantern light warm (#ffb36b, slight deterministic flicker); moonlight cool (#9db4ff); dusk sun #ff9a55; dawn #ffd9a8.
- Atmosphere: exponential fog per set, dust or mist where it fits, never empty black voids.
- Faceless on purpose: nobody's face is ever seen. People are backlit silhouettes, shadows, hands, boots, a cloak, a staff. This is the creative call, because modeled faces read as a video game and kill the realism.
- Post: subtle bloom (high threshold, only flames, lamps, sky), vignette, deterministic film grain, gentle lens falloff. Depth of field may be faked with fog and focus framing; do not use a real-time DOF pass unless cheap.
- Camera: slow, motivated moves (dolly, crane, push-in) with ease-in-out. No spinning, no whip pans. Lens about 28 to 50 mm equivalent (vertical FOV 24 to 45 degrees).
- Period accuracy: France, 1815. Digne is a small Provençal hill town at the foot of the Alps: pale limestone and ochre plaster houses, terracotta tile roofs, wooden shutters, narrow cobbled streets, a cathedral bell tower, dry hills and mountains behind. Gendarmes wear bicorne hats and long coats. Candlesticks are tall Empire-style silver, lathe-turned, with a round foot, baluster stem, bobèche and drip pan.

Palette: dusk amber and slate blue outside, candle amber and umber inside, steel blue at night, pale gold at dawn.

## 3. Overlay (HTML on top of the canvas)

- Fonts (local): EB Garamond 400/500/600 and italics from `node_modules/@fontsource/eb-garamond/files/eb-garamond-latin-<w>-<normal|italic>.woff2`; Inter 600 from `node_modules/@fontsource/inter/files/inter-latin-600-normal.woff2`.
- Captions: bottom center, EB Garamond 500, 46 px, white with a soft dark shadow, max 2 lines, built from TIMING words; the word being spoken is gold #e8c37a. Captions are on for the whole video.
- Chapter tag, top left, Inter 600 22 px, letter-spacing .18em, uppercase, 70% white: the citation for the current shot (column "Tag" below).
- Data callouts (column "Callout"): EB Garamond, appear on their cue word with a 0.4 s fade and slight rise, gone by the shot end. Real numbers only, exactly as written below.
- Title card in shot 1 and end card in shot 14 (EB Garamond 600, large, letter-spaced).

## 4. Shot list

Shot boundaries: each shot runs from the midpoint of the gap before its line to the midpoint of the gap after it (first starts at 0, last ends at TIMING.duration). Cue words below are from SCRIPT.md; use `cue(id, word)`.

| # | id | Set | What we see | Camera | Tag | Callout (on cue) |
|---|----|-----|-------------|--------|-----|------------------|
| 1 | open | town (dusk) | Digne from above at dusk, sun just behind the mountains, a lone cloaked figure with staff and knapsack walking the road into town, long shadow | high wide crane down toward the road | VOL. I · BOOK 2 · CH. I | Title "LES MISÉRABLES" + "Victor Hugo · 1862" fades out by "walks"; "Digne · October 1815" on "October" |
| 2 | bread | bakery (night, 1796) | A baker's shop window at night; a pane cracks and shatters (deterministic shards), a loaf is pulled out through the hole | slow push-in on the pane | CH. VI · 1796 | "1796" on "Jean"; "7 children" on "seven" |
| 3 | years | prison wall | Rough stone wall in a cell lit by a barred window; tally marks scratch in as a counter climbs 5 → 8 → 13 → 16 → 19; an iron chain in the foreground | slow lateral dolly | CH. VI | "5 years" on "Five"; then "+3 +5 +3 +3" one per escape starting on "Four"; "= 19 years" on "nineteen" |
| 4 | passport | table (lamp) | The yellow passport: aged yellow paper, handwritten text "Jean Valjean · forçat libéré · 19 ans au bagne" and a red stamp, on a rough table by an oil lamp, a few coins beside it | top-down slow rotate and push | CH. III · IX | "109 francs 15 sous for 19 years of work" on "convict" |
| 5 | rejected | town (night street) | Three refusals in sequence on the cue words: an inn door slams and its warm spill of light collapses ("Inns"); a prison door with a wicket and an iron chain on a bell, the wicket shuts ("prison"); a wooden dog kennel, two eyes catch the light, the figure backs off ("kennel") | locked-off shots, quick dissolves | CH. I | counter "Turned away: 1 / 2 / 3" ticking on each cue |
| 6 | door | bishop's door | A modest door in a stone wall at night; the figure's hand knocks; the door opens and warm light floods over him | low angle from inside the street | CH. III | none |
| 7 | dinner | interior (candle) | The bishop's table: two silver candlesticks are set down and their candles light on "lights"; six silver place settings, a loaf of rye bread, cheese, soup, wine; hero realism shot | slow dolly along the table, end close on the candlesticks | CH. III | "Monsieur" on "sir" |
| 8 | steal | interior (moon) then garden (night) | Moonlit room: the cupboard, the basket of silver lifted out of frame; then the garden under the moon: the empty basket drops into a flower bed and a silhouette clears the wall | push-in, then wide on the wall | CH. XI | none |
| 9 | caught | bishop's door (dawn) | Dawn light; three gendarme silhouettes in bicornes hold the figure at the doorway | slow push-in, backlit | CH. XII | none |
| 10 | gift | interior (morning) | The two candlesticks are taken from the chimney-piece and held out toward camera (toward Valjean) | close, then pull back | CH. XII | "≈ 200 francs" on "candlesticks" |
| 11 | soul | interior (candle) | Extreme close-up of one candle flame on its silver candlestick; the frame warms and slowly brightens | very slow push-in | CH. XII | the quote in italics: "You no longer belong to evil, but to good." on "You" |
| 12 | coin | plain (sunset) | Dry brushwood on a plain at sunset; a silver 40-sou coin rolls across the dirt and a heavy boot comes down on it; a small boy silhouette far off | low ground-level shot | CH. XIII | "40 sous = 2 francs" on "coin" |
| 13 | weep | crossroads (moonrise) | Three paths meet; the moon has risen; the figure collapses onto a large stone, head in hands | crane up and back to reveal the three paths | CH. XIII | "First tears in 19 years" on "nineteen" |
| 14 | end | interior (dark) | The two candlesticks alone in the dark, flames burning | slow push | VOL. I · BOOK 2 | End card "LES MISÉRABLES" on "Les"; "Victor Hugo · 1862" under it |

## 5. Code layout and interfaces

```
index.html          HyperFrames root + canvas + overlay DOM + scripts (core step)
js/core.js          renderer, scene, camera, composer + post, timing helpers, math, rng, shared materials/textures (core step)
js/overlay.js       captions, chapter tag, callouts, title/end cards (core step)
js/main.js          entry: builds everything, frame dispatcher, hooks (core step)
js/kit/silver.js    candlesticks, place settings, basket, coin (silver step)
js/kit/figure.js    cloaked figure, boy, gendarmes from Xbot.glb (figure step)
js/kit/town.js      Digne exteriors: dusk town, night street, inn door, prison door, kennel, bishop's door, bakery window (sets step)
js/kit/interior.js  bishop's dining room + bedroom cupboard + chimney-piece, cell wall, passport table (sets step)
js/kit/land.js      garden wall + flower bed, sunset plain, crossroads with large stone, sky/moon (sets step)
js/shots.js         the 14 shots (shots step)
tools/score.py      music + SFX keyed to TIMING (score step)
```

### Kit module contract (every `js/kit/*.js`)

```js
import * as THREE from "three";
// Each builder is pure: no globals, no scene access, deterministic.
export function makeX(opts = {}) {
  return { group /* THREE.Group, origin on the floor, +Y up, meters */, update /* optional (t, p) */, anchors /* optional {name: THREE.Vector3} */ };
}
```
- Units are meters, +Y up, real-world scale (a candlestick is about 0.30 m tall, a door 2.1 m).
- Builders create their own materials and canvas textures; cache textures inside the module.
- Determinism: never `Math.random()`, `Date.now()` or `performance.now()`. Use a seeded generator (mulberry32) defined in the module or imported from core.
- Budget: each set under about 400k triangles; at most 2 shadow-casting lights per set, 2048 shadow maps.
- Lights that belong to a set (candles, lanterns) are children of its group, so hiding the group hides them.

### core.js exports (core step must provide exactly these)

```js
export const W = 1920, H = 1080, FPS = 30;
export { THREE };                       // re-export
export const renderer, scene, camera, composer;
export const TM;                        // window.TIMING
export function cue(lineId, word, nth = 1);   // word start time (s), tolerant of punctuation and case
export function lineStart(id), lineEnd(id);
export function shotRange(id);          // [a, b] shot boundaries per section 4
export const cl, seg, lerp, eio, eo, smooth, win, rng;   // clamp, 0..1 ramp, lerp, ease-in-out, ease-out, smoothstep, window, mulberry32
export function setCam(pos, target, fovDeg);
export function setLook({ bg, fog, exposure, bloom, grain, vignette }); // per-shot grade
export function flicker(t, seed);       // deterministic candle flicker 0.85..1.15
```

### shots.js contract

```js
export const SHOTS = { open: { sets: ["townDusk", "figure"], render(t, k) {} }, ... };
// k = local progress 0..1 across the shot. render() places camera, animates objects, sets look, and calls overlay helpers.
```
main.js hides every set group, shows `SHOTS[id].sets`, calls `render`, updates overlay, then `composer.render()`.

### HyperFrames contract (index.html)

```html
<div id="root" data-composition-id="lesmis" data-start="0" data-width="1920" data-height="1080" data-duration="DURATION">
  <canvas id="gl" width="1920" height="1080"></canvas>
  <div id="ov"> overlay DOM </div>
  <audio id="mix" src="audio/mix.wav" data-start="0" data-duration="DURATION" data-track-index="1"></audio>
</div>
<script src="vendor/gsap.min.js"></script>
<script src="data/timing.js"></script>
<script>
  window.__hf = window.__hf || {}; window.__hf.buildReady = window.__hf.buildReady || {};
  window.__hf.buildReady.lesmis = new Promise((res) => { window.__lmReady = res; });
  window.__timelines = window.__timelines || {};
  const tl = gsap.timeline({ paused: true, onUpdate: () => window.__lmRender && window.__lmRender(tl.time()) });
  tl.to({ t: 0 }, { t: 1, duration: DURATION, ease: "none" });
  window.__timelines["lesmis"] = tl;
</script>
<script type="module" src="js/main.js"></script>
```
- DURATION is written into index.html in 3 places; keep it equal to TIMING.duration rounded to 2 decimals.
- main.js: `window.__lmRender = renderAt;` listen for `hf-seek` (`e.detail.time`); after all async loads (Xbot), render once and call `window.__lmReady()`.
- Preview mode: `index.html?t=12.5` renders exactly that time once everything is loaded and then sets `document.title = "ready"`. `?shot=dinner&k=0.5` renders that shot at that progress.

## 6. Rules for every step

- Only touch the paths your step lists. Do not reformat or "improve" other files.
- UTF-8 files only (the accents in Misérables, forçat, ≈ must survive).
- `node --check` must pass on every JS file you write.
- Say in your final message what you could not verify because you could not see a render.
