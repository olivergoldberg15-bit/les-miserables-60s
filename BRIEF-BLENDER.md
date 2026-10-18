# BRIEF-BLENDER: the film, rebuilt as one Blender world rendered in the cloud

This supersedes BRIEF.md for all new work. SCRIPT.md has the narration and the fact check; `data/timing.json` has the word timings (stand-in voice; the user's own voiceover will replace it, so every time comes from the timing file).

Nobody can run Blender on the local machine. You write Blender Python (bpy) blind; it runs in GitHub Actions on Ubuntu. Keep code defensive, log clearly, and fail loudly with the step name.

## 1. Deliverable

- 1920x1080, **24 fps** (film), duration = `timing.json.duration` (about 59.6 s, about 1430 frames).
- Blender **4.2 LTS**, an exact pinned version downloaded from download.blender.org in CI. Cycles on CPU (CI has no GPU), OpenImageDenoise, adaptive sampling (final about 96 max samples, noise threshold 0.03; stills mode 24 samples at 960x540), motion blur on, camera depth of field on every shot, AgX view transform with a "Medium High Contrast" look, light film grain and vignette added in post.
- Everything is built from scratch by one entry script: `blender -b --factory-startup -P blender/build.py -- --out build/lesmis.blend`.

## 2. Look: a real period film, not a game

- One coherent world: every location below is a place in the SAME modeled town, with consistent scale, materials, weather and time of day per shot. Cameras move through it like a film crew would.
- Real, CC0 assets for surfaces, sky and props (section 4). No flat colors on anything the camera can see.
- Lighting like a cinematographer: HDRI sky for the exterior base, one motivated key per shot (low dusk sun, lantern, candle, moon, dawn), soft fill, rim to separate people from the background, volumetric haze where light shafts help (light world volume, not fog everywhere).
- **Faces**: background people (gendarmes, townspeople) keep faces in shadow. **Valjean and the bishop get half-lit faces** (split or Rembrandt lighting from the motivated key), never flat front light. Bodies and clothing are fully real.
- Period: France, 1815. Digne is a Provençal hill town at the foot of the Alps: pale limestone and lime-plaster houses (ochre, cream), terracotta barrel-tile roofs, wooden shutters, narrow cobbled streets, a cathedral with a square bell tower and clock face, dry hills and mountains behind. Gendarmes: dark blue long coats, crossbelts, bicorne hats. Valjean: heavy worn greatcoat, wide hat, knapsack, iron-shod stick. The bishop: old, white hair, black cassock.

## 3. The town layout (meters, +Z up, origin = cathedral square)

| Place | Position | Notes |
|---|---|---|
| Road from the hills | from (-180, -60) descending to the town gate at (-70, -8) | dirt road with ruts, low stone walls, dry grass, view of the Alps to the north and east |
| Main street | (-70, -8) to (0, 0), about 6 m wide | cobbles, two- to four-storey attached houses both sides, lanterns on brackets |
| Inn (Jacquin Labarre's) | north side at (-45, 4) | warm lit windows, door that closes on Valjean |
| Prison | south side at (-25, -7) | heavy iron-bound door, wicket, chain hanging to a bell |
| Dog kennel | yard at (-12, 6) | wooden kennel, two eyes catching the light |
| Cathedral + clock tower | north of the square at (0, 22), tower about 35 m | clock face readable, strikes two in shot 9 |
| Hospital (the old palace) | east at (90, 0) | large, many windows, garden |
| Bishop's house | east at (60, -4), small two-storey house adjoining the hospital | street door facing south (never locked); ground floor: dining room with fireplace and mantel, the bishop's bedroom with a cupboard (the silver) and a window onto a walled garden north of the house; an alcove bed for the guest |
| Garden + wall | north of the bishop's house, wall about 2.2 m of rubble stone | flower beds, a path; Valjean vaults it in shot 11 |
| Flashback sets | outside the town, 1796 bakery window (Brie) and the Toulon galley cell | small separate sets with a desaturated "memory" grade |

`blender/world.py` must expose `LOCATIONS = {name: {"origin": (x,y,z), "anchors": {...}}}` and `LOOKDEV_CAMERAS = {name: {"loc": (x,y,z), "target": (x,y,z), "lens_mm": n, "time": "dusk|night|dawn|interior_candle|interior_moon"}}` with one camera per place, used by the stills workflow before shots exist.

## 4. Assets (open licenses only; downloaded in CI and cached, never committed)

- **Poly Haven (CC0)** via `https://api.polyhaven.com/assets?t=...` and `https://api.polyhaven.com/files/<id>`: HDRIs (a dusk/sunset sky, a moonlit night sky, a dawn sky, an interior/neutral), PBR textures at 2k (lime plaster, rough limestone wall, rubble stone, cobblestones, terracotta roof tiles, weathered wood planks, dirt road, dry grass, forest floor), models where they exist (wooden table and chairs, stools, barrels, crates, rocks, shrubs, candles or candle holders, lanterns). Record every chosen id, type, resolution and license in `blender/assets.json`; verify each id exists through the API in CI and fail with a clear message if not.
- **Microsoft Rocketbox (MIT)**, `github.com/microsoft/Microsoft-Rocketbox`: realistic rigged humans that all share one skeleton, plus hundreds of FBX animations in `Assets/Animations/all_animations_max_motextr_*` (male clips start with `m_`). Download only the files needed with raw URLs (`Assets/Avatars/<Group>/<Name>/Export/<Name>.fbx` and `/Textures/*`). Pick: an adult man with a heavy build for Valjean, the oldest-looking adult man for the bishop, `Military_Male_0x` bodies for three gendarmes. Period costume (greatcoat, cape, cassock, hats, bicornes) is modeled in Blender and fitted to the bodies (parented to bones, or cloth simulation baked in CI with pinned shoulders), so no modern clothing ever shows.
- Fonts for titles/captions: EB Garamond (SIL OFL) TTFs fetched in CI from the Google Fonts GitHub repo.
- Never use Higgsfield, never use paid APIs, never download anything that is not CC0, CC-BY, MIT, OFL or public domain, and log every download URL.

## 5. Shots (24 fps; times come from `timing.json` cue words; shot k runs from the midpoint of the gap before its line to the midpoint of the gap after)

| # | id | Place | Action | Camera | Light |
|---|----|-------|--------|--------|-------|
| 1 | open | road from the hills -> town gate | Valjean walks the road toward Digne, long shadow | aerial crane down from high over the valley to a low tracking shot behind him | low dusk sun behind the mountains, warm rim on him, town lights coming on |
| 2 | bread | bakery flashback | night: a fist breaks a pane, an arm takes a loaf | slow push on the window | memory grade, cold street, warm bakery glow |
| 3 | years | galley cell | tally marks scratched into stone, iron chain, Valjean's hands | slow lateral dolly | shaft of light from a barred window, dust in the beam |
| 4 | passport | main street, under a lantern | the yellow passport in his hands, text and stamp readable | close-up, shallow focus | lantern key, half-lit face |
| 5 | rejected | main street at night | inn door shuts and its light collapses ("Inns"), prison wicket shuts ("prison"), kennel eyes glint and he backs off ("kennel") | three locked-off setups along the street | lantern pools, moonlight fill |
| 6 | bishop | bishop's house, interior then street | the bishop by the fire reading, then the unlocked street door from outside | slow push in, then exterior wide | firelight, half-lit face for the bishop |
| 7 | door | bishop's door | Valjean knocks; door opens; warm light floods over him | low angle from inside the street | warm interior spill on his half-lit face |
| 8 | dinner | dining room | the two silver candlesticks set down and lit on "lights"; six silver place settings; bread, soup; the two men at the table | slow dolly along the table, end close on the candlesticks | candles as key, both men half-lit |
| 9 | night | guest alcove + clock tower | clock tower strikes two (exterior), Valjean's eyes open (interior) | exterior push on the clock, interior close | moonlight through the window |
| 10 | bedside | bishop's bedroom | moonlight on the sleeping bishop's face; Valjean's silhouette above him with the iron candlestick | slow push, tension | moon ray as the only key |
| 11 | steal | bedroom cupboard -> garden | basket of silver lifted; he throws the basket into a flower bed and vaults the wall | push-in, then wide on the wall | moonlight, rim on the silhouette |
| 12 | caught | main street at dawn | three gendarmes drag Valjean toward the bishop's house | tracking, backlit | dawn light down the street, mist |
| 13 | cliff | dining room, facing the street door | the door opens: the group on the threshold, backlit; the bishop turns (half-lit), looks at the silver, at Valjean; **hard cut to black on "says..."**; then "To be continued" | slow push on the bishop, then cut | morning light through the door |

Overlays (captions with the current word in gold, chapter tag top left, callouts) are added in post from `timing.json` (ASS subtitles via ffmpeg/libass with EB Garamond): never bake text into the Blender render.

## 6. Code layout and interfaces

```
.github/workflows/render.yml   CI: build, stills, full render matrix, assemble
blender/build.py               entry: assets -> world -> props -> actors -> shots -> save .blend
blender/assets.py              Poly Haven + Rocketbox + font downloads, cache dir from env ASSET_DIR
blender/assets.json            manifest of chosen assets (id, type, res, license, url)
blender/world.py               the town and all sets: LOCATIONS, LOOKDEV_CAMERAS, lighting rigs per time of day
blender/props.py               silver candlesticks, iron candlestick, silver place settings + ladle, wicker basket, yellow passport, loaf, chain, etc.
blender/actors.py              Rocketbox import, retargeted animations, period costumes, face-lighting helpers
blender/shots.py               the 13 shots: cameras, actor blocking, keyframes from timing.json, per-shot lighting and world settings
blender/render.py              render a frame range or a list of frames; modes: stills | lookdev | full
post/captions.py               timing.json -> captions.ass (+ tags/callouts/title/"To be continued")
post/assemble.sh               frames -> video (24 fps) + grain/vignette + captions + audio/mix.wav -> MP4
```

- Every module exposes `build(ctx)` where `ctx` carries the asset paths, timing and shared collections, and is idempotent on a fresh `--factory-startup` scene.
- Collections: one per location, plus `ACTORS`, `PROPS`, `CAMERAS`. Shots toggle visibility per frame range (keyframed `hide_render`) so one .blend renders the whole film.
- Determinism: fixed seeds everywhere (`random.seed`, noise seeds); Cycles seed fixed per frame.
- Performance: each frame must render in under about 3 minutes on a 4-vCPU runner at final settings (simplify far geometry, use instancing, 2k textures, limit light bounces to 6, caustics off).

## 7. CI contract (`.github/workflows/render.yml`)

- `workflow_dispatch` inputs: `mode` (`lookdev` | `stills` | `full`), `frames` (comma list for stills), `chunks` (default 20).
- Job `build`: cache Blender and assets (actions/cache keyed on version + assets.json hash), run build.py, upload `build/lesmis.blend` + assets as an artifact.
- Job `render` (matrix over chunks, max-parallel 20): download the build artifact, render its frame range, upload PNGs.
- Job `assemble`: ffmpeg frames -> 24 fps video, add grain/vignette, burn captions.ass, mux `audio/mix.wav`, upload `lesmis.mp4`.
- `lookdev` and `stills` modes upload PNGs only (960x540, 24 samples), so the coordinator can review in minutes.
- Fail loudly: any missing asset, missing bone, missing cue word, or Python exception fails the job with the step name in the log.

## 8. Rules for every step

- Only touch your step's allowed paths. UTF-8 only. `python -m py_compile` on every Python file you write.
- Never start a browser, never open windows on the local machine, never run Blender locally (it is not installed).
- Say what you could not verify because you could not run Blender.
