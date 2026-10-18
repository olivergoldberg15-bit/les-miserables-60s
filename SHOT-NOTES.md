# Coordinator notes for the shots step (read with BRIEF.md)

These come from rendering every kit in `tools/lookdev.html`. Reference stills: `snaps/sets4`, `snaps/silver`, `snaps/figure2` are not in git; the camera values below are what looked right.

## Kit API (all accepted and merged)

- `js/kit/silver.js`: `makeCandlestick({lit})`, `makePlaceSetting()`, `makeSilverBasket()`, `makeCoin40Sous()`. Excellent quality; use them big in frame.
- `js/kit/town.js`: `makeTownDusk`, `makeNightStreet`, `makeInnDoor`, `makePrisonDoor`, `makeKennel`, `makeBishopDoor`, `makeBakeryWindow` (+ `ironChain`). Doors/wicket/inn light/pane shatter animate through `update(t, p)`.
- `js/kit/interior.js`: `makeDiningRoom({moonlit})` (anchors `candlestick1`, `candlestick2`, `placeSettings`, ...), `makeCellWall` (tally marks via `update(t, p)`), `makePassportTable`.
- `js/kit/land.js`: `makeGardenWall` (anchors `wallTop`, `flowerBed`, `basket`), `makePlain` (anchors `coin`, `boy`, `path`), `makeCrossroads` (anchors `stone`, `figure`), `makeSky`.
- `js/kit/figure.js`: `await loadFigures()` -> `{makeValjean, makeBoy, makeGendarme}`; each `{group, update, pose(name, phase)}` with poses `walk`, `stand`, `knock`, `vault`, `kneel_collapse`, `held`.
- Every builder returns `look` (bg, fog, exposure): pass it to `setLook` and adjust per shot.

## Cameras that rendered well (set-local coordinates, fov in degrees)

- Town dusk: cam `0,2.2,30` -> target `0,5,-18`, fov 38. Crane down from about y=14 to y=2.2.
- Night street: cam `0,1.7,9` -> target `0,2,-10`, fov 40. This set is strong: use it for shot 5.
- Dining room: cam `1.2,1.25,1.4` -> target `0,0.85,0`, fov 34; for shot 7 dolly along the table toward the candlestick anchors and end tight on them (fov 28-30).
- Silver close-ups: candlestick from about 0.35-0.5 m away, fov 30-32; coin from 0.05 m, fov 30.

## Known defects: frame around them

- `makePlain`: a dark curved band shows in the far background. Shot 12 is low and tight on the coin and boot: keep the horizon out of frame or push fog density up so it disappears.
- `makeGardenWall`: leaf cards look blocky up close. Shot 8 garden: keep it wide, moonlit, plants in shadow; the hero is the wall top and the basket landing.
- Dining room fireplace is a brick grid: keep it soft in the background or out of frame.
- `makeBoy` is broken (bare mannequin, floating cap/jacket). Do NOT use it. For the boy in shot 12 use `makeValjean()` scaled about 0.55 with the hat hidden, far away (anchor `boy`), backlit by the sunset so it reads only as a small silhouette.

## Look

- Grain and vignette from core on every shot; keep exposure low enough that skies never clip to white.
- People are always silhouettes: put the key light behind them or to the side, never frontal.
