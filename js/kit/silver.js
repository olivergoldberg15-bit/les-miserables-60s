import * as THREE from 'three';

// Deterministic seeded PRNG (mulberry32)
const rng = (seed = 1) => () => {
  let t = (seed += 0x6d2b79f5);
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

// Deterministic candle flicker matching core.js (around 0.85..1.15)
const flicker = (t = 0, seed = 0) =>
  1 +
  0.075 * Math.sin(t * 8.71 + seed) +
  0.045 * Math.sin(t * 17.31 + seed * 2) +
  0.03 * Math.sin(t * 31.7 + seed * 3);

const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a, b, k) => a + (b - a) * k;
const smoothstep = (a, b, x) => {
  const t = clamp((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};

// Module-level texture and material cache
const CACHE = {
  silverTex: null,
  silverMat: null,
  coinTex: null,
  coinMat: null,
  wickerTex: null,
  wickerMat: null,
  linerMat: null,
  waxTex: null,
  waxMat: null,
  wickMat: null,
  flameTex: null,
  forkGeo: null,
  spoonGeo: null,
  ladleGroupProto: null,
};

function makeTextureFromRGBA(width, height, rgba, isSRGB = false, repeatX = 1, repeatY = 1) {
  let tex;
  if (typeof document !== 'undefined' && typeof document.createElement === 'function') {
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (ctx && typeof ctx.createImageData === 'function') {
      const img = ctx.createImageData(width, height);
      img.data.set(rgba);
      ctx.putImageData(img, 0, 0);
      tex = new THREE.CanvasTexture(canvas);
    }
  }
  if (!tex) {
    tex = new THREE.DataTexture(rgba, width, height, THREE.RGBAFormat);
  }
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(repeatX, repeatY);
  tex.colorSpace = isSRGB ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  tex.needsUpdate = true;
  return tex;
}

// 2D value noise helper for deterministic procedural surface detail
function makeNoise2D(seed = 101, gridSize = 64) {
  const rand = rng(seed);
  const table = new Float32Array(gridSize * gridSize);
  for (let i = 0; i < table.length; i++) table[i] = rand();

  const sampleGrid = (u, v, freq) => {
    const x = ((u * freq) % gridSize + gridSize) % gridSize;
    const y = ((v * freq) % gridSize + gridSize) % gridSize;
    const x0 = Math.floor(x);
    const y0 = Math.floor(y);
    const x1 = (x0 + 1) % gridSize;
    const y1 = (y0 + 1) % gridSize;
    const fx = x - x0;
    const fy = y - y0;
    const sx = fx * fx * (3 - 2 * fx);
    const sy = fy * fy * (3 - 2 * fy);
    const n00 = table[y0 * gridSize + x0];
    const n10 = table[y0 * gridSize + x1];
    const n01 = table[y1 * gridSize + x0];
    const n11 = table[y1 * gridSize + x1];
    return lerp(lerp(n00, n10, sx), lerp(n01, n11, sx), sy);
  };

  return (u, v) =>
    0.52 * sampleGrid(u, v, 6) +
    0.28 * sampleGrid(u, v, 15) +
    0.14 * sampleGrid(u, v, 31) +
    0.06 * sampleGrid(u, v, 59);
}

// Build realistic antique silver procedural textures (albedo with crevice tarnish, roughness variation, bump/normal)
function getSilverTextures() {
  if (CACHE.silverTex) return CACHE.silverTex;

  const W = 256;
  const H = 256;
  const albedoData = new Uint8Array(W * H * 4);
  const roughData = new Uint8Array(W * H * 4);
  const bumpData = new Uint8Array(W * H * 4);
  const normalData = new Uint8Array(W * H * 4);
  const heightField = new Float32Array(W * H);

  const noiseA = makeNoise2D(1815, 64);
  const noiseB = makeNoise2D(4027, 64);
  const scratchRng = rng(9182);

  // Pre-generate subtle lathe/polishing circular brush lines along U and patina pockets
  const lineOffsets = new Float32Array(H);
  for (let y = 0; y < H; y++) {
    lineOffsets[y] = (scratchRng() - 0.5) * 0.14;
  }

  for (let y = 0; y < H; y++) {
    const v = y / H;
    // Periodic recess/crevice bands so UV-mapped mouldings pick up warm-dark silver sulfide tarnish
    const ringWave = Math.pow(0.5 - 0.5 * Math.cos(v * Math.PI * 12), 3.0);
    for (let x = 0; x < W; x++) {
      const u = x / W;
      const n1 = noiseA(u, v);
      const n2 = noiseB(u * 2.5 + 0.17, v * 2.5 + 0.31);
      // Fine horizontal lathe/polish micro-streaks
      const brush =
        0.5 +
        0.25 * Math.sin((v * 96 + n1 * 1.8) * Math.PI * 2) +
        0.25 * Math.cos((u * 12 + v * 64) * Math.PI * 2) +
        lineOffsets[y];

      // Tarnish factor concentrates in micro-pits and groove bands
      const creviceMask = clamp((ringWave * 0.42 + (1 - n1) * 0.45 + (1 - n2) * 0.25 - 0.46) * 2.1, 0, 1);
      const h = clamp(0.55 + (brush - 0.5) * 0.18 + (n2 - 0.5) * 0.16 - creviceMask * 0.22, 0, 1);
      heightField[y * W + x] = h;

      // Sterling silver base (#f7f4ee) darkened in tarnished crevices toward warm dark umber-slate (#5a5147)
      const r = Math.round(lerp(248, 108, creviceMask * 0.72) - (1 - n1) * 8);
      const g = Math.round(lerp(244, 98, creviceMask * 0.75) - (1 - n1) * 9);
      const b = Math.round(lerp(236, 86, creviceMask * 0.78) - (1 - n1) * 10);

      // Roughness map modulates base roughness=0.18:
      // values around 0.78..1.0 on polished areas (~0.14..0.18 effective), higher in tarnished pits
      const roughVal = Math.round(clamp(lerp(205, 255, creviceMask * 0.75 + (1 - brush) * 0.28), 175, 255));
      const bumpVal = Math.round(h * 255);

      const idx = (y * W + x) * 4;
      albedoData[idx] = clamp(r, 0, 255);
      albedoData[idx + 1] = clamp(g, 0, 255);
      albedoData[idx + 2] = clamp(b, 0, 255);
      albedoData[idx + 3] = 255;

      roughData[idx] = roughVal;
      roughData[idx + 1] = roughVal;
      roughData[idx + 2] = roughVal;
      roughData[idx + 3] = 255;

      bumpData[idx] = bumpVal;
      bumpData[idx + 1] = bumpVal;
      bumpData[idx + 2] = bumpVal;
      bumpData[idx + 3] = 255;
    }
  }

  // Compute tangent-space normal map from heightField
  const strength = 2.6;
  for (let y = 0; y < H; y++) {
    const ym = (y - 1 + H) % H;
    const yp = (y + 1) % H;
    for (let x = 0; x < W; x++) {
      const xm = (x - 1 + W) % W;
      const xp = (x + 1) % W;
      const dx = (heightField[y * W + xp] - heightField[y * W + xm]) * strength;
      const dy = (heightField[yp * W + x] - heightField[ym * W + x]) * strength;
      const invLen = 1 / Math.hypot(dx, dy, 1);
      const nx = -dx * invLen;
      const ny = -dy * invLen;
      const nz = invLen;
      const idx = (y * W + x) * 4;
      normalData[idx] = Math.round((nx * 0.5 + 0.5) * 255);
      normalData[idx + 1] = Math.round((ny * 0.5 + 0.5) * 255);
      normalData[idx + 2] = Math.round((nz * 0.5 + 0.5) * 255);
      normalData[idx + 3] = 255;
    }
  }

  CACHE.silverTex = {
    map: makeTextureFromRGBA(W, H, albedoData, true, 2, 2),
    roughnessMap: makeTextureFromRGBA(W, H, roughData, false, 2, 2),
    bumpMap: makeTextureFromRGBA(W, H, bumpData, false, 2, 2),
    normalMap: makeTextureFromRGBA(W, H, normalData, false, 2, 2),
  };
  return CACHE.silverTex;
}

// Shared realistic silver MeshPhysicalMaterial (metalness 1, roughness 0.18, procedural variation + crevice tarnish)
function getSilverMaterial(useVertexColors = true) {
  const key = useVertexColors ? 'silverMatVC' : 'silverMat';
  if (CACHE[key]) return CACHE[key];
  const tex = getSilverTextures();
  const mat = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(0xf6f2ea),
    map: tex.map,
    metalness: 1.0,
    roughness: 0.18,
    roughnessMap: tex.roughnessMap,
    normalMap: tex.normalMap,
    normalScale: new THREE.Vector2(0.08, 0.08),
    bumpMap: tex.bumpMap,
    bumpScale: 0.0012,
    clearcoat: 0.14,
    clearcoatRoughness: 0.2,
    reflectivity: 1.0,
    envMapIntensity: 1.35,
    vertexColors: useVertexColors,
  });
  CACHE[key] = mat;
  return mat;
}

// Apply vertex-color crevice tarnish based on curvature/concavity or explicit crevice weights
function applyCreviceTarnishColors(geometry, creviceEvaluator) {
  const pos = geometry.attributes.position;
  const count = pos.count;
  const colors = new Float32Array(count * 3);
  const v = new THREE.Vector3();
  const n = geometry.attributes.normal;
  const nv = new THREE.Vector3();

  for (let i = 0; i < count; i++) {
    v.fromBufferAttribute(pos, i);
    if (n) nv.fromBufferAttribute(n, i);
    const tarnish = clamp(creviceEvaluator(v, nv, i), 0, 1);
    // Bright polished silver (1, 0.99, 0.97) -> tarnished crevice (0.36, 0.32, 0.28)
    colors[i * 3] = lerp(1.0, 0.36, tarnish);
    colors[i * 3 + 1] = lerp(0.99, 0.32, tarnish);
    colors[i * 3 + 2] = lerp(0.97, 0.28, tarnish);
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  return geometry;
}

// Beeswax material + subtle procedural wax grain texture
function getBeeswaxMaterial() {
  if (CACHE.waxMat) return CACHE.waxMat;
  const W = 128;
  const H = 128;
  const rgba = new Uint8Array(W * H * 4);
  const bump = new Uint8Array(W * H * 4);
  const noise = makeNoise2D(3141, 32);

  for (let y = 0; y < H; y++) {
    const v = y / H;
    for (let x = 0; x < W; x++) {
      const u = x / W;
      const n = noise(u, v);
      const streak = 0.5 + 0.5 * Math.sin((v * 18 + n * 1.4) * Math.PI * 2);
      const idx = (y * W + x) * 4;
      rgba[idx] = Math.round(lerp(240, 250, n));
      rgba[idx + 1] = Math.round(lerp(231, 243, n));
      rgba[idx + 2] = Math.round(lerp(208, 224, n));
      rgba[idx + 3] = 255;

      const b = Math.round(clamp((n * 0.7 + streak * 0.3) * 255, 0, 255));
      bump[idx] = b;
      bump[idx + 1] = b;
      bump[idx + 2] = b;
      bump[idx + 3] = 255;
    }
  }

  const map = makeTextureFromRGBA(W, H, rgba, true, 1, 2);
  const bumpMap = makeTextureFromRGBA(W, H, bump, false, 1, 2);

  CACHE.waxMat = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(0xf6efe0),
    map,
    bumpMap,
    bumpScale: 0.0008,
    metalness: 0.0,
    roughness: 0.38,
    transmission: 0.16,
    thickness: 0.018,
    ior: 1.44,
    clearcoat: 0.08,
    clearcoatRoughness: 0.35,
    emissive: new THREE.Color(0xff9d3b),
    emissiveIntensity: 0.12,
  });
  return CACHE.waxMat;
}

// Flame gradient texture for realistic candle flame
function getFlameTexture() {
  if (CACHE.flameTex) return CACHE.flameTex;
  const W = 64;
  const H = 128;
  const rgba = new Uint8Array(W * H * 4);
  for (let y = 0; y < H; y++) {
    const v = y / (H - 1); // 0 at bottom (wick), 1 at tip
    for (let x = 0; x < W; x++) {
      const idx = (y * W + x) * 4;
      let r, g, b;
      if (v < 0.22) {
        // Blue-violet oxygen-rich base shifting into warm amber
        const k = v / 0.22;
        r = lerp(65, 255, k);
        g = lerp(120, 175, k);
        b = lerp(255, 70, k);
      } else if (v < 0.72) {
        // Luminous white-gold core
        const k = (v - 0.22) / 0.5;
        r = 255;
        g = lerp(185, 248, Math.sin(k * Math.PI));
        b = lerp(75, 210, Math.sin(k * Math.PI));
      } else {
        // Soft amber-orange flame tip
        const k = (v - 0.72) / 0.28;
        r = lerp(255, 235, k);
        g = lerp(215, 115, k);
        b = lerp(140, 25, k);
      }
      rgba[idx] = Math.round(clamp(r, 0, 255));
      rgba[idx + 1] = Math.round(clamp(g, 0, 255));
      rgba[idx + 2] = Math.round(clamp(b, 0, 255));
      rgba[idx + 3] = 255;
    }
  }
  CACHE.flameTex = makeTextureFromRGBA(W, H, rgba, true, 1, 1);
  return CACHE.flameTex;
}

/**
 * 1. makeCandlestick(opts = {})
 * Empire-style lathe-turned silver candlestick (~0.30 m total height),
 * round foot, baluster stem, bobèche, drip pan, white beeswax candle with wick,
 * optional flame mesh plus warm PointLight child whose intensity can be scaled by update.
 */
export function makeCandlestick(opts = {}) {
  const seed = Number.isFinite(opts.seed) ? opts.seed : 1;
  const includeFlame = opts.flame !== false && opts.includeFlame !== false;
  const initiallyLit = opts.lit !== false && opts.flame !== false;
  const baseIntensity = Number.isFinite(opts.intensity) ? opts.intensity : 2.2;

  const group = new THREE.Group();
  group.name = opts.name || 'candlestick';

  // Empire-style lathe profile: [radius, y, creviceWeight]
  // Silver body runs from y = 0.000 m (floor/table contact) to y = 0.220 m (top of bobèche lip)
  const profileSpec = [
    // Underside hollow & outer foot rim (round foot, diameter ~11.2 cm)
    [0.044, 0.000, 0.65],
    [0.056, 0.000, 0.15],
    [0.0565, 0.004, 0.05],
    [0.054, 0.008, 0.55], // first stepped foot fillet (tarnished crevice)
    [0.051, 0.011, 0.10],
    [0.046, 0.016, 0.65], // deep scotia groove above foot rim
    [0.043, 0.020, 0.12],
    [0.036, 0.025, 0.50],
    [0.027, 0.031, 0.20],
    [0.019, 0.036, 0.85], // tight necking crevice between foot and lower knop
    // Lower baluster knop / torus
    [0.024, 0.041, 0.08],
    [0.025, 0.046, 0.05],
    [0.022, 0.051, 0.45],
    [0.015, 0.056, 0.88], // deep crevice above lower knop
    // Baluster stem (tapered Empire column swelling to shouldered amphora belly)
    [0.017, 0.064, 0.20],
    [0.0185, 0.082, 0.12],
    [0.0205, 0.102, 0.08],
    [0.0235, 0.122, 0.05],
    [0.0255, 0.136, 0.04], // wide Empire baluster shoulder
    [0.023, 0.144, 0.35],
    [0.0145, 0.150, 0.90], // sharp collar crevice below nozzle
    [0.019, 0.154, 0.12], // decorative collar ring
    [0.015, 0.158, 0.82], // nozzle base crevice
    // Campana candle socket / nozzle
    [0.0185, 0.168, 0.15],
    [0.0195, 0.182, 0.10],
    [0.021, 0.194, 0.55],
    // Wide concave drip pan (grease cup) at y = 0.197..0.208 m
    [0.032, 0.199, 0.25],
    [0.037, 0.204, 0.06], // outer drip pan rim
    [0.035, 0.207, 0.40],
    [0.023, 0.202, 0.85], // deep inner drip pan basin crevice
    [0.0185, 0.205, 0.70],
    // Flared removable-style bobèche above drip pan (y = 0.208..0.220 m)
    [0.020, 0.211, 0.30],
    [0.0295, 0.215, 0.08],
    [0.031, 0.218, 0.04], // bobèche outer beaded edge
    [0.028, 0.220, 0.20],
    [0.018, 0.216, 0.82], // bobèche wax well crevice
    [0.013, 0.215, 0.90], // inner candle socket throat
  ];

  const lathePoints = profileSpec.map(([r, y]) => new THREE.Vector2(r, y));
  const radialSegs = 56;
  const silverGeo = new THREE.LatheGeometry(lathePoints, radialSegs);

  // Add subtle Empire vertical fluting on the baluster stem and gadrooning on foot/bobèche,
  // plus bake crevice tarnish vertex colors.
  const posAttr = silverGeo.attributes.position;
  const vTmp = new THREE.Vector3();
  for (let i = 0; i < posAttr.count; i++) {
    vTmp.fromBufferAttribute(posAttr, i);
    const y = vTmp.y;
    const r = Math.hypot(vTmp.x, vTmp.z);
    if (r > 1e-5) {
      const angle = Math.atan2(vTmp.z, vTmp.x);
      let radialDelta = 0;
      // Subtle Empire vertical flutes on stem (y = 0.060..0.140)
      if (y > 0.058 && y < 0.142) {
        const stemMask = smoothstep(0.058, 0.07, y) * (1 - smoothstep(0.13, 0.142, y));
        radialDelta += stemMask * 0.00055 * Math.cos(angle * 20);
      }
      // Fine beaded moulding on foot step (y = 0.008..0.022) and bobèche rim (y = 0.214..0.220)
      if (y > 0.007 && y < 0.022) {
        const footMask = smoothstep(0.007, 0.011, y) * (1 - smoothstep(0.018, 0.022, y));
        radialDelta += footMask * 0.00035 * Math.cos(angle * 48);
      }
      if (y > 0.213 && y <= 0.220 && r > 0.024) {
        radialDelta += 0.0003 * Math.cos(angle * 40);
      }
      const scale = (r + radialDelta) / r;
      posAttr.setXYZ(i, vTmp.x * scale, y, vTmp.z * scale);
    }
  }
  silverGeo.computeVertexNormals();

  applyCreviceTarnishColors(silverGeo, (v) => {
    // Interpolate profile crevice weight by closest y/r sample, plus flute valleys
    let bestDist = Infinity;
    let cWeight = 0.15;
    const r = Math.hypot(v.x, v.z);
    for (let j = 0; j < profileSpec.length; j++) {
      const [pr, py, cw] = profileSpec[j];
      const d = Math.hypot(r - pr, v.y - py);
      if (d < bestDist) {
        bestDist = d;
        cWeight = cw;
      }
    }
    const angle = Math.atan2(v.z, v.x);
    if (v.y > 0.058 && v.y < 0.142) {
      const fluteValley = clamp(-Math.cos(angle * 20), 0, 1);
      cWeight = Math.max(cWeight, fluteValley * 0.52);
    }
    return cWeight;
  });

  const silverMat = getSilverMaterial(true);
  const bodyMesh = new THREE.Mesh(silverGeo, silverMat);
  bodyMesh.name = 'candlestickSilver';
  bodyMesh.castShadow = true;
  bodyMesh.receiveShadow = true;
  group.add(bodyMesh);

  // White beeswax candle sitting in socket (y = 0.212 to y = 0.292 m, diameter ~2.45 cm)
  const candlePts = [
    new THREE.Vector2(0.0124, 0.212),
    new THREE.Vector2(0.0124, 0.235),
    new THREE.Vector2(0.0121, 0.265),
    new THREE.Vector2(0.0118, 0.289),
    new THREE.Vector2(0.0112, 0.2925), // outer wax rim at top
    new THREE.Vector2(0.0085, 0.291),  // recessed melted wax pool
    new THREE.Vector2(0.0035, 0.2895),
    new THREE.Vector2(0.0, 0.2892),
  ];
  const candleGeo = new THREE.LatheGeometry(candlePts, 36);
  // Deterministic organic solidified wax drips along the upper candle shaft
  const cPos = candleGeo.attributes.position;
  for (let i = 0; i < cPos.count; i++) {
    vTmp.fromBufferAttribute(cPos, i);
    const r = Math.hypot(vTmp.x, vTmp.z);
    if (r > 0.009 && vTmp.y > 0.235) {
      const ang = Math.atan2(vTmp.z, vTmp.x);
      const drip1 = Math.exp(-Math.pow((ang - 0.7) / 0.22, 2)) * smoothstep(0.245, 0.288, vTmp.y);
      const drip2 = Math.exp(-Math.pow((ang + 1.6) / 0.18, 2)) * smoothstep(0.258, 0.290, vTmp.y);
      const rad = r + 0.0011 * drip1 + 0.0008 * drip2;
      const sc = rad / r;
      cPos.setXYZ(i, vTmp.x * sc, vTmp.y + 0.0006 * Math.sin(ang * 3 + seed), vTmp.z * sc);
    }
  }
  candleGeo.computeVertexNormals();

  const candleMesh = new THREE.Mesh(candleGeo, getBeeswaxMaterial());
  candleMesh.name = 'candle';
  candleMesh.castShadow = true;
  candleMesh.receiveShadow = true;
  group.add(candleMesh);

  // Braided charred cotton wick (y = 0.289 to y = 0.298 m)
  const wickCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(0.0, 0.289, 0.0),
    new THREE.Vector3(0.0002, 0.2935, 0.0001),
    new THREE.Vector3(0.0007, 0.2965, -0.0002),
    new THREE.Vector3(0.001, 0.2985, 0.0),
  ]);
  const wickGeo = new THREE.TubeGeometry(wickCurve, 12, 0.00095, 8, false);
  if (!CACHE.wickMat) {
    CACHE.wickMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(0x1c1714),
      roughness: 0.92,
      metalness: 0.0,
      emissive: new THREE.Color(0xff4500),
      emissiveIntensity: 0.35,
    });
  }
  const wickMesh = new THREE.Mesh(wickGeo, CACHE.wickMat);
  wickMesh.name = 'wick';
  group.add(wickMesh);

  // Flame group at top of wick (y = 0.2965 m, rising to ~0.320 m so total candlestick height is ~0.30-0.32 m)
  const flameGroup = new THREE.Group();
  flameGroup.name = 'flame';
  flameGroup.position.set(0.0008, 0.2965, 0.0);

  if (includeFlame) {
    // Outer teardrop flame envelope (height 0.024 m)
    const outerFlamePts = [
      new THREE.Vector2(0.0001, 0.0),
      new THREE.Vector2(0.0038, 0.003),
      new THREE.Vector2(0.0056, 0.0075),
      new THREE.Vector2(0.0049, 0.013),
      new THREE.Vector2(0.003, 0.0185),
      new THREE.Vector2(0.0011, 0.0225),
      new THREE.Vector2(0.0, 0.0245),
    ];
    const outerFlameGeo = new THREE.LatheGeometry(outerFlamePts, 24);
    const outerFlameMat = new THREE.MeshStandardMaterial({
      map: getFlameTexture(),
      emissive: new THREE.Color(0xffb85c),
      emissiveMap: getFlameTexture(),
      emissiveIntensity: 2.8,
      roughness: 0.2,
      metalness: 0.0,
      transparent: true,
      opacity: 0.94,
      depthWrite: false,
    });
    const outerFlame = new THREE.Mesh(outerFlameGeo, outerFlameMat);
    outerFlame.name = 'flameOuter';
    flameGroup.add(outerFlame);

    // Bright incandescent inner core (triggers subtle bloom smoothly)
    const innerFlamePts = [
      new THREE.Vector2(0.0001, 0.0015),
      new THREE.Vector2(0.0022, 0.0045),
      new THREE.Vector2(0.0031, 0.0085),
      new THREE.Vector2(0.0021, 0.0135),
      new THREE.Vector2(0.0, 0.0175),
    ];
    const innerFlameGeo = new THREE.LatheGeometry(innerFlamePts, 18);
    const innerFlameMat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(0xfff8df),
      transparent: true,
      opacity: 0.96,
    });
    const innerFlame = new THREE.Mesh(innerFlameGeo, innerFlameMat);
    innerFlame.name = 'flameInner';
    flameGroup.add(innerFlame);
  }

  flameGroup.visible = includeFlame && initiallyLit;
  group.add(flameGroup);

  // Warm PointLight child (#ffb36b per BRIEF.md)
  const light = new THREE.PointLight(
    0xffb36b,
    initiallyLit ? baseIntensity : 0,
    opts.distance ?? 6.5,
    opts.decay ?? 2.0
  );
  light.name = 'candleLight';
  light.position.set(0.0, 0.312, 0.0);
  if (opts.castShadow) {
    light.castShadow = true;
    light.shadow.mapSize.set(1024, 1024);
    light.shadow.bias = -0.0005;
  }
  group.add(light);

  let currentScale = initiallyLit ? 1 : 0;

  function setIntensity(scale = 1, t = 0) {
    currentScale = Math.max(0, Number.isFinite(scale) ? scale : 1);
    const flk = flicker(t, seed);
    light.intensity = baseIntensity * currentScale * flk;
    if (includeFlame) {
      const visible = currentScale > 0.002;
      flameGroup.visible = visible;
      if (visible) {
        const s = clamp(currentScale, 0.15, 1.6);
        const breathY = s * (0.94 + 0.09 * Math.sin(t * 13.7 + seed) + 0.04 * Math.cos(t * 23.1 + seed * 2));
        const breathXZ = Math.sqrt(s) * (0.97 + 0.04 * Math.cos(t * 11.3 + seed));
        flameGroup.scale.set(breathXZ, breathY, breathXZ);
        flameGroup.rotation.z = 0.055 * Math.sin(t * 6.3 + seed * 1.7);
        flameGroup.rotation.x = 0.035 * Math.cos(t * 5.1 + seed * 2.3);
      }
    }
  }

  // update(t, scale): scales the warm PointLight intensity and animates deterministic candle flicker
  function update(t = 0, scale = undefined) {
    let intensityScale = currentScale;
    if (typeof scale === 'number' && Number.isFinite(scale)) {
      intensityScale = Math.max(0, scale);
    } else if (scale && typeof scale === 'object') {
      if (typeof scale.intensity === 'number') intensityScale = Math.max(0, scale.intensity);
      else if (typeof scale.scale === 'number') intensityScale = Math.max(0, scale.scale);
      else if (typeof scale.lit === 'boolean') intensityScale = scale.lit ? 1 : 0;
    }
    setIntensity(intensityScale, t);
  }

  const anchors = {
    base: new THREE.Vector3(0, 0, 0),
    dripPan: new THREE.Vector3(0, 0.204, 0),
    bobeche: new THREE.Vector3(0, 0.216, 0),
    candleTop: new THREE.Vector3(0, 0.292, 0),
    wick: new THREE.Vector3(0.0008, 0.2965, 0),
    flame: new THREE.Vector3(0.0008, 0.308, 0),
    light: new THREE.Vector3(0, 0.312, 0),
  };

  group.userData = {
    light,
    flame: flameGroup,
    candle: candleMesh,
    wick: wickMesh,
    baseIntensity,
    setIntensity,
    update,
    anchors,
  };

  return {
    group,
    update,
    anchors,
    light,
    flame: flameGroup,
    candle: candleMesh,
    wick: wickMesh,
    setIntensity,
  };
}

// Helper to build a closed lofted ribbon strip with top/bottom camber and side walls
function buildLoftedStripGeometry(slices, cols = 9) {
  // Each slice: { z, halfWidth, yCenter, thickness, crossCurve, crevice }
  // crossCurve > 0 arches the center upward relative to edges; < 0 hollows the center (like a spoon/fork bowl)
  const rows = slices.length;
  const ringVerts = cols * 2; // top row (0..cols-1 left-to-right), bottom row (0..cols-1 right-to-left)
  const positions = [];
  const uvs = [];
  const crevices = [];

  for (let r = 0; r < rows; r++) {
    const s = slices[r];
    const vCoord = r / (rows - 1);
    // Top surface: left (-1) to right (+1)
    for (let c = 0; c < cols; c++) {
      const uNorm = (c / (cols - 1)) * 2 - 1; // -1..1
      const x = uNorm * s.halfWidth;
      const dish = s.crossCurve * (1 - uNorm * uNorm);
      // Subtle Empire thread ridge near perimeter
      const threadGroove = Math.exp(-Math.pow((Math.abs(uNorm) - 0.76) / 0.08, 2));
      const y = s.yCenter + s.thickness * 0.5 + dish - threadGroove * 0.00018;
      positions.push(x, y, s.z);
      uvs.push(uNorm * 0.5 + 0.5, vCoord);
      crevices.push(clamp(s.crevice + threadGroove * 0.45, 0, 1));
    }
    // Bottom surface: right (+1) to left (-1)
    for (let c = cols - 1; c >= 0; c--) {
      const uNorm = (c / (cols - 1)) * 2 - 1;
      const x = uNorm * s.halfWidth;
      const dish = s.crossCurve * (1 - uNorm * uNorm);
      const y = s.yCenter - s.thickness * 0.5 + dish;
      positions.push(x, y, s.z);
      uvs.push(uNorm * 0.5 + 0.5, vCoord);
      crevices.push(clamp(s.crevice + 0.12, 0, 1));
    }
  }

  const indices = [];
  for (let r = 0; r < rows - 1; r++) {
    const rowA = r * ringVerts;
    const rowB = (r + 1) * ringVerts;
    for (let k = 0; k < ringVerts; k++) {
      const kNext = (k + 1) % ringVerts;
      const a0 = rowA + k;
      const a1 = rowA + kNext;
      const b0 = rowB + k;
      const b1 = rowB + kNext;
      indices.push(a0, b0, a1, a1, b0, b1);
    }
  }

  // Cap start (r = 0) and end (r = rows - 1)
  const capRing = (rowOffset, flip) => {
    for (let c = 0; c < cols - 1; c++) {
      const t0 = rowOffset + c;
      const t1 = rowOffset + c + 1;
      const b0 = rowOffset + (ringVerts - 1 - c);
      const b1 = rowOffset + (ringVerts - 2 - c);
      if (flip) {
        indices.push(t0, b0, t1, t1, b0, b1);
      } else {
        indices.push(t0, t1, b0, t1, b1, b0);
      }
    }
  };
  capRing(0, false);
  capRing((rows - 1) * ringVerts, true);

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geo.setIndex(indices);
  geo.computeVertexNormals();

  const colors = new Float32Array(crevices.length * 3);
  for (let i = 0; i < crevices.length; i++) {
    const cw = crevices[i];
    colors[i * 3] = lerp(1.0, 0.36, cw);
    colors[i * 3 + 1] = lerp(0.99, 0.32, cw);
    colors[i * 3 + 2] = lerp(0.97, 0.28, cw);
  }
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  return geo;
}

function mergeGeometriesSimple(geos) {
  const positions = [];
  const normals = [];
  const uvs = [];
  const colors = [];
  const indices = [];
  let vertOffset = 0;

  for (const g of geos) {
    const pos = g.attributes.position;
    const norm = g.attributes.normal;
    const uv = g.attributes.uv;
    const col = g.attributes.color;
    const idx = g.index;

    for (let i = 0; i < pos.count; i++) {
      positions.push(pos.getX(i), pos.getY(i), pos.getZ(i));
      if (norm) normals.push(norm.getX(i), norm.getY(i), norm.getZ(i));
      if (uv) uvs.push(uv.getX(i), uv.getY(i));
      else uvs.push(0, 0);
      if (col) colors.push(col.getX(i), col.getY(i), col.getZ(i));
      else colors.push(1, 1, 1);
    }

    if (idx) {
      for (let i = 0; i < idx.count; i++) {
        indices.push(idx.getX(i) + vertOffset);
      }
    } else {
      for (let i = 0; i < pos.count; i++) {
        indices.push(i + vertOffset);
      }
    }
    vertOffset += pos.count;
  }

  const merged = new THREE.BufferGeometry();
  merged.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  if (normals.length) merged.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  merged.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  merged.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  merged.setIndex(indices);
  if (!normals.length) merged.computeVertexNormals();
  return merged;
}

// Build realistic 1815 French silver table fork geometry (~0.204 m long, 0.024 m wide head, 4 curved tines)
function getForkGeometry() {
  if (CACHE.forkGeo) return CACHE.forkGeo;

  // Handle + neck + bridge (z = +0.102 m at handle butt to z = -0.036 m at tine root)
  const handleSlices = [
    { z: 0.102, halfWidth: 0.0045, yCenter: 0.0022, thickness: 0.0024, crossCurve: 0.0006, crevice: 0.22 },
    { z: 0.097, halfWidth: 0.0086, yCenter: 0.0018, thickness: 0.0027, crossCurve: 0.0008, crevice: 0.12 },
    { z: 0.086, halfWidth: 0.0092, yCenter: 0.0016, thickness: 0.0028, crossCurve: 0.0009, crevice: 0.08 },
    { z: 0.070, halfWidth: 0.0074, yCenter: 0.0025, thickness: 0.0027, crossCurve: 0.0006, crevice: 0.10 },
    { z: 0.045, halfWidth: 0.0052, yCenter: 0.0046, thickness: 0.0029, crossCurve: 0.0004, crevice: 0.14 },
    { z: 0.020, halfWidth: 0.0038, yCenter: 0.0068, thickness: 0.0033, crossCurve: 0.0004, crevice: 0.25 },
    { z: -0.004, halfWidth: 0.0035, yCenter: 0.0072, thickness: 0.0034, crossCurve: 0.0003, crevice: 0.35 },
    { z: -0.020, halfWidth: 0.0065, yCenter: 0.0045, thickness: 0.0030, crossCurve: -0.0004, crevice: 0.55 },
    { z: -0.030, halfWidth: 0.0116, yCenter: 0.0026, thickness: 0.0027, crossCurve: -0.0010, crevice: 0.65 },
    { z: -0.037, halfWidth: 0.0120, yCenter: 0.0020, thickness: 0.0024, crossCurve: -0.0011, crevice: 0.82 },
  ];
  const parts = [buildLoftedStripGeometry(handleSlices, 9)];

  // Four tapered curved tines (z = -0.035 m to z = -0.102 m)
  const tineOffsets = [-0.0099, -0.0033, 0.0033, 0.0099];
  for (let t = 0; t < 4; t++) {
    const xBase = tineOffsets[t];
    const xTip = xBase * 0.93;
    const tineSteps = [
      { z: -0.035, w: 0.0019, y: 0.0021, th: 0.0023, cr: 0.85 },
      { z: -0.046, w: 0.0016, y: 0.0017, th: 0.0021, cr: 0.40 },
      { z: -0.064, w: 0.00135, y: 0.0020, th: 0.0018, cr: 0.14 },
      { z: -0.084, w: 0.00105, y: 0.0034, th: 0.0014, cr: 0.08 },
      { z: -0.098, w: 0.0007, y: 0.0050, th: 0.0010, cr: 0.06 },
      { z: -0.102, w: 0.00035, y: 0.0056, th: 0.0007, cr: 0.10 },
    ];
    const tineGeo = buildLoftedStripGeometry(
      tineSteps.map((s) => ({
        z: s.z,
        halfWidth: s.w,
        yCenter: s.y - 0.0011 * (1 - Math.pow(xBase / 0.012, 2)),
        thickness: s.th,
        crossCurve: 0.00018,
        crevice: s.cr,
      })),
      5
    );
    const p = tineGeo.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const zVal = p.getZ(i);
      const k = clamp((-0.035 - zVal) / 0.067, 0, 1);
      p.setX(i, p.getX(i) + lerp(xBase, xTip, k));
    }
    tineGeo.computeVertexNormals();
    parts.push(tineGeo);
  }

  const merged = mergeGeometriesSimple(parts);
  // Shift Y so the lowest point rests exactly on y = 0
  merged.computeBoundingBox();
  const minY = merged.boundingBox.min.y;
  merged.translate(0, -minY, 0);
  CACHE.forkGeo = merged;
  return CACHE.forkGeo;
}

// Build realistic 1815 French silver table spoon geometry (~0.208 m long, oval concave bowl 0.042 m wide)
function getSpoonGeometry() {
  if (CACHE.spoonGeo) return CACHE.spoonGeo;

  const slices = [
    // Fiddle-and-thread handle butt (z = +0.104 m) to arched neck (z = -0.022 m)
    { z: 0.104, halfWidth: 0.0046, yCenter: 0.0024, thickness: 0.0024, crossCurve: 0.0006, crevice: 0.22 },
    { z: 0.098, halfWidth: 0.0088, yCenter: 0.0019, thickness: 0.0027, crossCurve: 0.0008, crevice: 0.12 },
    { z: 0.086, halfWidth: 0.0094, yCenter: 0.0017, thickness: 0.0028, crossCurve: 0.0009, crevice: 0.08 },
    { z: 0.068, halfWidth: 0.0075, yCenter: 0.0028, thickness: 0.0027, crossCurve: 0.0006, crevice: 0.10 },
    { z: 0.042, halfWidth: 0.0052, yCenter: 0.0052, thickness: 0.0030, crossCurve: 0.0004, crevice: 0.15 },
    { z: 0.015, halfWidth: 0.0038, yCenter: 0.0078, thickness: 0.0033, crossCurve: 0.0003, crevice: 0.26 },
    { z: -0.012, halfWidth: 0.0036, yCenter: 0.0082, thickness: 0.0034, crossCurve: 0.0002, crevice: 0.45 },
    // Bowl drop heel & deep concave oval spoon bowl (z = -0.024 m to z = -0.104 m, max width 0.042 m)
    { z: -0.024, halfWidth: 0.0085, yCenter: 0.0068, thickness: 0.0024, crossCurve: -0.0022, crevice: 0.68 },
    { z: -0.036, halfWidth: 0.0158, yCenter: 0.0072, thickness: 0.0019, crossCurve: -0.0058, crevice: 0.35 },
    { z: -0.052, halfWidth: 0.0204, yCenter: 0.0082, thickness: 0.0017, crossCurve: -0.0084, crevice: 0.22 },
    { z: -0.068, halfWidth: 0.0210, yCenter: 0.0084, thickness: 0.0016, crossCurve: -0.0086, crevice: 0.18 },
    { z: -0.084, halfWidth: 0.0182, yCenter: 0.0078, thickness: 0.0015, crossCurve: -0.0068, crevice: 0.15 },
    { z: -0.096, halfWidth: 0.0124, yCenter: 0.0070, thickness: 0.0014, crossCurve: -0.0036, crevice: 0.14 },
    { z: -0.104, halfWidth: 0.0042, yCenter: 0.0066, thickness: 0.0013, crossCurve: -0.0008, crevice: 0.18 },
  ];

  const geo = buildLoftedStripGeometry(slices, 13);
  geo.computeBoundingBox();
  const minY = geo.boundingBox.min.y;
  geo.translate(0, -minY, 0);
  CACHE.spoonGeo = geo;
  return CACHE.spoonGeo;
}

// Build realistic French silver soup ladle (*louche*, ~0.305 m long, hemispherical bowl diameter ~0.086 m)
function buildLadleMesh() {
  const mat = getSilverMaterial(true);
  const ladleGroup = new THREE.Group();
  ladleGroup.name = 'ladle';

  // Deep hemispherical/oval silver ladle bowl (radius 0.043 m, depth 0.030 m)
  const bowlSlices = [];
  const steps = 14;
  for (let i = 0; i <= steps; i++) {
    const u = (i / steps) * 2 - 1; // -1 to +1 along Z of bowl
    const z = -0.115 + u * 0.043;
    const profile = Math.sqrt(Math.max(0.02, 1 - u * u));
    const halfWidth = 0.043 * profile;
    const depth = 0.027 * (1 - u * u);
    bowlSlices.push({
      z,
      halfWidth,
      yCenter: 0.0285,
      thickness: 0.0018,
      crossCurve: -depth,
      crevice: lerp(0.15, 0.48, 1 - Math.abs(u)),
    });
  }
  const bowlGeo = buildLoftedStripGeometry(bowlSlices, 15);

  // Long curved Empire ladle stem & fiddle handle (z = -0.074 m up to z = +0.185 m)
  const handleSlices = [
    { z: -0.074, halfWidth: 0.0065, yCenter: 0.027, thickness: 0.0032, crossCurve: -0.001, crevice: 0.78 },
    { z: -0.055, halfWidth: 0.0042, yCenter: 0.036, thickness: 0.0035, crossCurve: 0.0003, crevice: 0.45 },
    { z: -0.020, halfWidth: 0.0040, yCenter: 0.044, thickness: 0.0034, crossCurve: 0.0004, crevice: 0.20 },
    { z: 0.030, halfWidth: 0.0045, yCenter: 0.048, thickness: 0.0032, crossCurve: 0.0005, crevice: 0.14 },
    { z: 0.085, halfWidth: 0.0058, yCenter: 0.046, thickness: 0.0030, crossCurve: 0.0006, crevice: 0.12 },
    { z: 0.135, halfWidth: 0.0085, yCenter: 0.040, thickness: 0.0029, crossCurve: 0.0008, crevice: 0.10 },
    { z: 0.168, halfWidth: 0.0112, yCenter: 0.034, thickness: 0.0029, crossCurve: 0.0010, crevice: 0.08 },
    { z: 0.182, halfWidth: 0.0098, yCenter: 0.028, thickness: 0.0028, crossCurve: 0.0008, crevice: 0.18 },
    { z: 0.188, halfWidth: 0.0055, yCenter: 0.023, thickness: 0.0025, crossCurve: 0.0005, crevice: 0.28 },
  ];
  const handleGeo = buildLoftedStripGeometry(handleSlices, 9);

  const merged = mergeGeometriesSimple([bowlGeo, handleGeo]);
  merged.computeBoundingBox();
  merged.translate(0, -merged.boundingBox.min.y, 0);

  const mesh = new THREE.Mesh(merged, mat);
  mesh.name = 'ladleMesh';
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  ladleGroup.add(mesh);
  return ladleGroup;
}

/**
 * 2. makePlaceSetting(opts = {})
 * One silver fork and one silver spoon, realistic dimensions (~0.205 m long),
 * resting on y = 0, +Y up.
 */
export function makePlaceSetting(opts = {}) {
  const spacing = Number.isFinite(opts.spacing) ? opts.spacing : 0.054;
  const group = new THREE.Group();
  group.name = opts.name || 'placeSetting';

  const mat = getSilverMaterial(true);

  const fork = new THREE.Mesh(getForkGeometry(), mat);
  fork.name = 'fork';
  fork.position.set(-spacing * 0.5, 0, 0);
  fork.rotation.y = opts.forkYaw ?? 0.025;
  fork.castShadow = true;
  fork.receiveShadow = true;
  group.add(fork);

  const spoon = new THREE.Mesh(getSpoonGeometry(), mat);
  spoon.name = 'spoon';
  spoon.position.set(spacing * 0.5, 0, 0);
  spoon.rotation.y = opts.spoonYaw ?? -0.025;
  spoon.castShadow = true;
  spoon.receiveShadow = true;
  group.add(spoon);

  function update() {}

  const anchors = {
    center: new THREE.Vector3(0, 0, 0),
    fork: fork.position.clone(),
    spoon: spoon.position.clone(),
  };

  group.userData = { fork, spoon, update, anchors };
  return { group, update, anchors, fork, spoon };
}

// Procedural woven wicker textures & material for makeSilverBasket
function getWickerMaterial() {
  if (CACHE.wickerMat) return CACHE.wickerMat;
  const W = 256;
  const H = 256;
  const albedo = new Uint8Array(W * H * 4);
  const rough = new Uint8Array(W * H * 4);
  const normal = new Uint8Array(W * H * 4);
  const hField = new Float32Array(W * H);
  const noise = makeNoise2D(7741, 64);

  for (let y = 0; y < H; y++) {
    const v = y / H;
    const rowIdx = Math.floor(v * 24);
    const rowFrac = (v * 24) % 1;
    const rowRound = Math.sin(rowFrac * Math.PI);
    for (let x = 0; x < W; x++) {
      const u = x / W;
      const colShift = (rowIdx & 1) * 0.5;
      const colFrac = ((u * 12 + colShift) % 1 + 1) % 1;
      const overUnder = Math.sin(colFrac * Math.PI * 2);
      const n = noise(u, v);

      const h = clamp(0.15 + rowRound * (0.55 + 0.25 * overUnder) + (n - 0.5) * 0.12, 0, 1);
      hField[y * W + x] = h;

      // Warm golden-umber willow osier wicker tones with deep shadow in weave interstices
      const shade = clamp(0.32 + h * 0.72 + (n - 0.5) * 0.18, 0.18, 1.05);
      const r = Math.round(clamp(138 * shade, 28, 210));
      const g = Math.round(clamp(96 * shade, 20, 155));
      const b = Math.round(clamp(54 * shade, 12, 95));

      const idx = (y * W + x) * 4;
      albedo[idx] = r;
      albedo[idx + 1] = g;
      albedo[idx + 2] = b;
      albedo[idx + 3] = 255;

      const rv = Math.round(clamp(lerp(235, 165, h), 140, 250));
      rough[idx] = rv;
      rough[idx + 1] = rv;
      rough[idx + 2] = rv;
      rough[idx + 3] = 255;
    }
  }

  const strength = 4.2;
  for (let y = 0; y < H; y++) {
    const ym = (y - 1 + H) % H;
    const yp = (y + 1) % H;
    for (let x = 0; x < W; x++) {
      const xm = (x - 1 + W) % W;
      const xp = (x + 1) % W;
      const dx = (hField[y * W + xp] - hField[y * W + xm]) * strength;
      const dy = (hField[yp * W + x] - hField[ym * W + x]) * strength;
      const inv = 1 / Math.hypot(dx, dy, 1);
      const idx = (y * W + x) * 4;
      normal[idx] = Math.round((-dx * inv * 0.5 + 0.5) * 255);
      normal[idx + 1] = Math.round((-dy * inv * 0.5 + 0.5) * 255);
      normal[idx + 2] = Math.round((inv * 0.5 + 0.5) * 255);
      normal[idx + 3] = 255;
    }
  }

  CACHE.wickerMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(0xd8b482),
    map: makeTextureFromRGBA(W, H, albedo, true, 3, 2),
    roughness: 0.78,
    roughnessMap: makeTextureFromRGBA(W, H, rough, false, 3, 2),
    normalMap: makeTextureFromRGBA(W, H, normal, false, 3, 2),
    normalScale: new THREE.Vector2(0.55, 0.55),
    metalness: 0.0,
    side: THREE.DoubleSide,
  });
  return CACHE.wickerMat;
}

/**
 * 3. makeSilverBasket(opts = {})
 * Wicker basket (~0.32 m x 0.22 m, height ~0.095 m, handle to ~0.18 m)
 * holding six silver forks, six silver spoons and a silver soup ladle.
 */
export function makeSilverBasket(opts = {}) {
  const group = new THREE.Group();
  group.name = opts.name || 'silverBasket';
  const wickerMat = getWickerMaterial();

  const basketGroup = new THREE.Group();
  basketGroup.name = 'wickerBasket';

  // Oval wicker basket dimensions (half-axes aX, aZ)
  const baseAX = 0.128;
  const baseAZ = 0.086;
  const topAX = 0.160;
  const topAZ = 0.110;
  const basketH = 0.094;

  // 1. Woven basket wall shell with 3D corrugated horizontal reed courses and vertical stake ribs
  const radSegs = 64;
  const heightSegs = 20;
  const wallGeo = new THREE.CylinderGeometry(1, 1, basketH, radSegs, heightSegs, true);
  const wPos = wallGeo.attributes.position;
  for (let i = 0; i < wPos.count; i++) {
    const x0 = wPos.getX(i);
    const y0 = wPos.getY(i); // -basketH/2 .. +basketH/2
    const z0 = wPos.getZ(i);
    const v = (y0 + basketH * 0.5) / basketH; // 0 at floor, 1 at rim
    const ang = Math.atan2(z0, x0);
    const course = v * 11;
    const courseIdx = Math.floor(course);
    // Alternating over-under radial wicker weave relief
    const weave =
      0.0024 * Math.sin(ang * 24 + (courseIdx & 1) * Math.PI) * Math.sin((course % 1) * Math.PI);
    const rx = lerp(baseAX, topAX, v) + weave;
    const rz = lerp(baseAZ, topAZ, v) + weave;
    wPos.setXYZ(i, Math.cos(ang) * rx, v * basketH, Math.sin(ang) * rz);
  }
  wallGeo.computeVertexNormals();
  const wallMesh = new THREE.Mesh(wallGeo, wickerMat);
  wallMesh.castShadow = true;
  wallMesh.receiveShadow = true;
  basketGroup.add(wallMesh);

  // 2. Woven bottom base plate (resting on y = 0..0.008 m)
  const bottomGeo = new THREE.CylinderGeometry(1, 1, 0.007, 48, 1);
  const bPos = bottomGeo.attributes.position;
  for (let i = 0; i < bPos.count; i++) {
    const x0 = bPos.getX(i);
    const y0 = bPos.getY(i) + 0.0035;
    const z0 = bPos.getZ(i);
    bPos.setXYZ(i, x0 * baseAX, y0, z0 * baseAZ);
  }
  bottomGeo.computeVertexNormals();
  const bottomMesh = new THREE.Mesh(bottomGeo, wickerMat);
  bottomMesh.castShadow = true;
  bottomMesh.receiveShadow = true;
  basketGroup.add(bottomMesh);

  // 3. Braided rope-twist wicker rim collar at top (y = basketH) and foot ring (y = 0.004 m)
  const makeOvalRim = (ax, az, yHeight, tubeRadius, twistAmp) => {
    const pts = [];
    const n = 72;
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2;
      const twist = twistAmp * Math.sin(a * 28);
      pts.push(
        new THREE.Vector3(
          Math.cos(a) * (ax + twist),
          yHeight + twistAmp * 0.7 * Math.cos(a * 28),
          Math.sin(a) * (az + twist)
        )
      );
    }
    const curve = new THREE.CatmullRomCurve3(pts, true);
    const geo = new THREE.TubeGeometry(curve, 96, tubeRadius, 10, true);
    const mesh = new THREE.Mesh(geo, wickerMat);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    return mesh;
  };
  basketGroup.add(makeOvalRim(topAX, topAZ, basketH, 0.0075, 0.0014));
  basketGroup.add(makeOvalRim(baseAX + 0.002, baseAZ + 0.002, 0.0052, 0.0045, 0.0007));

  // 4. Arched braided wicker carrying handle spanning across the shorter axis (Z)
  const handlePts = [];
  for (let i = 0; i <= 24; i++) {
    const u = (i / 24) * 2 - 1; // -1..1
    const z = u * topAZ;
    const arch = (1 - u * u) * 0.088;
    const twistX = 0.0016 * Math.sin(u * Math.PI * 10);
    handlePts.push(new THREE.Vector3(twistX, basketH + arch, z));
  }
  const handleCurve = new THREE.CatmullRomCurve3(handlePts);
  const handleGeo = new THREE.TubeGeometry(handleCurve, 40, 0.0062, 10, false);
  const handleMesh = new THREE.Mesh(handleGeo, wickerMat);
  handleMesh.castShadow = true;
  handleMesh.receiveShadow = true;
  basketGroup.add(handleMesh);

  // 5. Soft padded interior baize/linen cloth liner on the basket floor (y = 0.008..0.022 m)
  if (!CACHE.linerMat) {
    CACHE.linerMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(0x3a332b),
      roughness: 0.92,
      metalness: 0.0,
    });
  }
  const linerGeo = new THREE.CylinderGeometry(1, 1, 0.012, 36, 1);
  const lPos = linerGeo.attributes.position;
  for (let i = 0; i < lPos.count; i++) {
    const x0 = lPos.getX(i);
    const y0 = lPos.getY(i) + 0.013;
    const z0 = lPos.getZ(i);
    const fold = 0.0025 * Math.sin(x0 * 9) * Math.cos(z0 * 11);
    lPos.setXYZ(i, x0 * (baseAX - 0.006), y0 + fold, z0 * (baseAZ - 0.006));
  }
  linerGeo.computeVertexNormals();
  const linerMesh = new THREE.Mesh(linerGeo, CACHE.linerMat);
  linerMesh.receiveShadow = true;
  basketGroup.add(linerMesh);

  group.add(basketGroup);

  // Silverware contents: 6 forks, 6 spoons, and 1 ladle
  const silverware = new THREE.Group();
  silverware.name = 'silverware';
  const silverMat = getSilverMaterial(true);
  const forkGeo = getForkGeometry();
  const spoonGeo = getSpoonGeometry();

  const forks = [];
  const spoons = [];

  // Arrange 6 forks fanned naturally in the left/front half of the basket, slightly tilted against the inner wall
  for (let i = 0; i < 6; i++) {
    const f = new THREE.Mesh(forkGeo, silverMat);
    f.name = `fork_${i}`;
    const k = (i - 2.5) / 2.5; // -1..1
    f.rotation.order = 'YXZ';
    // Orient roughly along X (basket length) with natural fan and stacking height
    f.rotation.y = Math.PI * 0.5 + k * 0.14 + (i % 2 === 0 ? 0.03 : -0.02);
    f.rotation.x = 0.11 + (i % 3) * 0.025;
    f.rotation.z = -0.05 + k * 0.04;
    f.position.set(
      -0.012 + (i % 2) * 0.008,
      0.019 + i * 0.0042,
      -0.030 + k * 0.028
    );
    f.castShadow = true;
    f.receiveShadow = true;
    silverware.add(f);
    forks.push(f);
  }

  // Arrange 6 spoons fanned naturally in the right/back half of the basket
  for (let i = 0; i < 6; i++) {
    const s = new THREE.Mesh(spoonGeo, silverMat);
    s.name = `spoon_${i}`;
    const k = (i - 2.5) / 2.5;
    s.rotation.order = 'YXZ';
    s.rotation.y = -Math.PI * 0.5 + k * 0.13 + (i % 2 === 0 ? -0.025 : 0.03);
    s.rotation.x = 0.12 + ((i + 1) % 3) * 0.025;
    s.rotation.z = 0.04 - k * 0.04;
    s.position.set(
      0.010 - (i % 2) * 0.007,
      0.021 + i * 0.0042,
      0.028 + k * 0.026
    );
    s.castShadow = true;
    s.receiveShadow = true;
    silverware.add(s);
    spoons.push(s);
  }

  // Add the large silver soup ladle resting diagonally across the top of the cutlery bed
  const ladle = buildLadleMesh();
  ladle.rotation.order = 'YXZ';
  ladle.rotation.y = 1.28;
  ladle.rotation.x = -0.16;
  ladle.rotation.z = 0.08;
  ladle.position.set(-0.015, 0.044, 0.002);
  silverware.add(ladle);

  if (opts.empty === true) {
    silverware.visible = false;
  }
  group.add(silverware);

  function setEmpty(isEmpty = true) {
    silverware.visible = !isEmpty;
  }

  function update(t = 0, p = undefined) {
    if (p && typeof p === 'object') {
      if (typeof p.empty === 'boolean') silverware.visible = !p.empty;
      else if (typeof p.showSilver === 'boolean') silverware.visible = p.showSilver;
    }
  }

  const anchors = {
    base: new THREE.Vector3(0, 0, 0),
    rim: new THREE.Vector3(0, basketH, 0),
    handle: new THREE.Vector3(0, basketH + 0.088, 0),
    silverware: new THREE.Vector3(0, 0.038, 0),
  };

  group.userData = {
    basket: basketGroup,
    silverware,
    forks,
    spoons,
    ladle,
    setEmpty,
    update,
    anchors,
  };

  return {
    group,
    update,
    anchors,
    basket: basketGroup,
    silverware,
    forks,
    spoons,
    ladle,
    setEmpty,
  };
}

// Generate 512x512 embossed coin maps (albedo with crevice tarnish, normal map, bump map, roughness map)
function getCoinTextures() {
  if (CACHE.coinTex) return CACHE.coinTex;

  const S = 512;
  const hField = new Float32Array(S * S);
  const wearNoise = makeNoise2D(181540, 64);

  // If 2D canvas context is available (browser), draw crisp embossed profile & serif lettering first
  let canvasHeight = null;
  if (typeof document !== 'undefined' && typeof document.createElement === 'function') {
    const c = document.createElement('canvas');
    c.width = S;
    c.height = S;
    const ctx = c.getContext('2d');
    if (ctx) {
      ctx.fillStyle = '#000';
      ctx.fillRect(0, 0, S, S);
      const cx = S * 0.5;
      const cy = S * 0.5;

      // Embossed bust silhouette (1815 French 2-Francs monarch/emperor laureate profile facing left)
      const bustGrad = ctx.createRadialGradient(cx - 8, cy - 10, 12, cx, cy, 135);
      bustGrad.addColorStop(0, 'rgba(255,255,255,0.95)');
      bustGrad.addColorStop(0.65, 'rgba(210,210,210,0.82)');
      bustGrad.addColorStop(1, 'rgba(80,80,80,0.0)');

      ctx.save();
      ctx.beginPath();
      // Forehead, nose bridge, lips, chin, jaw, neck truncation, hair & shoulder drapery
      ctx.moveTo(cx - 26, cy - 108);
      ctx.quadraticCurveTo(cx - 58, cy - 92, cx - 64, cy - 58); // brow
      ctx.lineTo(cx - 88, cy - 22); // nose tip
      ctx.lineTo(cx - 72, cy - 12); // philtrum
      ctx.quadraticCurveTo(cx - 80, cy - 2, cx - 72, cy + 8); // lips
      ctx.quadraticCurveTo(cx - 78, cy + 26, cx - 60, cy + 36); // chin
      ctx.quadraticCurveTo(cx - 36, cy + 44, cx - 34, cy + 78); // throat
      ctx.lineTo(cx - 48, cy + 104); // bust front truncation
      ctx.quadraticCurveTo(cx + 8, cy + 122, cx + 68, cy + 94); // bust base truncation
      ctx.quadraticCurveTo(cx + 62, cy + 45, cx + 52, cy + 18); // nape
      ctx.quadraticCurveTo(cx + 82, cy - 18, cx + 72, cy - 68); // back of head curls
      ctx.quadraticCurveTo(cx + 42, cy - 118, cx - 26, cy - 108); // crown
      ctx.closePath();
      ctx.fillStyle = bustGrad;
      ctx.fill();

      // Secondary relief: cheekbone, ear, hair curls, and laureate fillet band
      ctx.fillStyle = 'rgba(255,255,255,0.35)';
      ctx.beginPath();
      ctx.ellipse(cx - 22, cy - 22, 34, 46, -0.15, 0, Math.PI * 2);
      ctx.fill();

      // Laureate ribbon/wreath across hair
      ctx.strokeStyle = 'rgba(255,255,255,0.55)';
      ctx.lineWidth = 10;
      ctx.beginPath();
      ctx.moveTo(cx - 48, cy - 76);
      ctx.quadraticCurveTo(cx + 4, cy - 48, cx + 58, cy - 18);
      ctx.stroke();
      ctx.restore();

      // Perimeter embossed serif inscription: "LOUIS XVIII ROI DE FRANCE" and "2 FRANCS · 1815"
      const drawArcText = (str, radius, startAng, endAng, ccw = false) => {
        ctx.save();
        ctx.font = 'bold 28px Georgia, Garamond, serif';
        ctx.fillStyle = 'rgba(245,245,245,0.92)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        const n = str.length;
        for (let i = 0; i < n; i++) {
          const t = n > 1 ? i / (n - 1) : 0.5;
          const ang = lerp(startAng, endAng, t);
          const x = cx + Math.cos(ang) * radius;
          const y = cy + Math.sin(ang) * radius;
          ctx.save();
          ctx.translate(x, y);
          ctx.rotate(ang + (ccw ? -Math.PI * 0.5 : Math.PI * 0.5));
          ctx.fillText(str[i], 0, 0);
          ctx.restore();
        }
        ctx.restore();
      };

      drawArcText('LOUIS XVIII ROI DE FRANCE', 188, -Math.PI * 0.86, -Math.PI * 0.14, false);
      drawArcText('· 2 FRANCS · 1815 ·', 188, Math.PI * 0.80, Math.PI * 0.20, true);

      const img = ctx.getImageData(0, 0, S, S).data;
      canvasHeight = new Float32Array(S * S);
      for (let i = 0; i < S * S; i++) {
        canvasHeight[i] = img[i * 4] / 255;
      }
    }
  }

  // Analytic fallback + refinement so both browser and headless environments get full relief detail
  for (let y = 0; y < S; y++) {
    const ny = (y / (S - 1)) * 2 - 1; // -1..1
    for (let x = 0; x < S; x++) {
      const nx = (x / (S - 1)) * 2 - 1;
      const r = Math.hypot(nx, ny);
      const ang = Math.atan2(ny, nx);
      const wn = wearNoise((x / S) * 2, (y / S) * 2);

      // Raised outer rim (listel) at r = 0.86..0.98 with worn edge modulation
      const edgeWear = 0.65 + 0.35 * Math.sin(ang * 3 + 0.8) * wn;
      const rimProfile =
        smoothstep(0.84, 0.89, r) * (1 - smoothstep(0.96, 1.0, r)) * (0.78 * edgeWear);

      // 72 beaded denticles just inside the rim (r = 0.80..0.86), worn down asymmetrically
      const denticleRing =
        smoothstep(0.79, 0.815, r) *
        (1 - smoothstep(0.845, 0.87, r)) *
        Math.max(0, Math.cos(ang * 72)) *
        0.34 *
        edgeWear;

      // Relief from canvas drawing or analytic bust + lettering fallback
      let relief = 0;
      if (canvasHeight) {
        // 3x3 box blur on canvas height for smooth bevelled coining die relief
        let sum = 0;
        for (let dy = -1; dy <= 1; dy++) {
          const yy = clamp(y + dy, 0, S - 1);
          for (let dx = -1; dx <= 1; dx++) {
            const xx = clamp(x + dx, 0, S - 1);
            sum += canvasHeight[yy * S + xx];
          }
        }
        relief = (sum / 9) * 0.72;
      } else {
        // Analytic bust + lettering rings for non-DOM environments
        const head = Math.max(0, 1 - Math.hypot((nx + 0.04) / 0.34, (ny + 0.06) / 0.42));
        const nose = Math.max(0, 1 - Math.hypot((nx + 0.28) / 0.12, (ny + 0.04) / 0.10)) * 0.45;
        const neck = Math.max(0, 1 - Math.hypot((nx - 0.02) / 0.24, (ny - 0.32) / 0.24)) * 0.65;
        const letterBand =
          smoothstep(0.66, 0.70, r) *
          (1 - smoothstep(0.75, 0.79, r)) *
          Math.max(0, Math.sin(ang * 28) * Math.cos(r * 90)) *
          0.42;
        relief = Math.max(head * 0.75 + nose, neck) + letterBand;
      }

      // Fine circulation scratches & worn high points
      const scratch =
        0.04 * Math.sin((nx * 19 + ny * 37) * Math.PI) * Math.cos((nx * 41 - ny * 13) * Math.PI);
      const totalH = clamp(0.18 + rimProfile + denticleRing + relief * (0.72 + 0.28 * wn) + scratch - (1 - wn) * 0.08, 0, 1);
      hField[y * S + x] = totalH;
    }
  }

  const albedo = new Uint8Array(S * S * 4);
  const rough = new Uint8Array(S * S * 4);
  const bump = new Uint8Array(S * S * 4);
  const normal = new Uint8Array(S * S * 4);

  const normalStrength = 5.5;
  for (let y = 0; y < S; y++) {
    const ym = clamp(y - 1, 0, S - 1);
    const yp = clamp(y + 1, 0, S - 1);
    for (let x = 0; x < S; x++) {
      const xm = clamp(x - 1, 0, S - 1);
      const xp = clamp(x + 1, 0, S - 1);
      const h = hField[y * S + x];
      const dx = (hField[y * S + xp] - hField[y * S + xm]) * normalStrength;
      const dy = (hField[yp * S + x] - hField[ym * S + x]) * normalStrength;
      const gradMag = Math.hypot(dx, dy);

      // Laplacian approximates concavity: tarnish settles around the base of embossed letters, profile & rim crease
      const avgNeighbor =
        0.25 * (hField[y * S + xp] + hField[y * S + xm] + hField[yp * S + x] + hField[ym * S + x]);
      const concavity = clamp((avgNeighbor - h) * 14 + gradMag * 0.18 * (1 - h), 0, 1);
      const wn = wearNoise(x / S, y / S);
      const tarnish = clamp(concavity * 0.85 + (1 - h) * 0.28 + (1 - wn) * 0.16 - 0.12, 0, 1);

      const idx = (y * S + x) * 4;
      // Worn bright silver on raised relief vs dark sulfided tarnish in lettering/profile crevices
      albedo[idx] = Math.round(lerp(248, 72, tarnish));
      albedo[idx + 1] = Math.round(lerp(243, 65, tarnish));
      albedo[idx + 2] = Math.round(lerp(233, 58, tarnish));
      albedo[idx + 3] = 255;

      // Polished worn high points have lower roughness; tarnished crevices have higher roughness
      const rVal = Math.round(clamp(lerp(185, 255, tarnish * 0.78 + (1 - h) * 0.22), 160, 255));
      rough[idx] = rVal;
      rough[idx + 1] = rVal;
      rough[idx + 2] = rVal;
      rough[idx + 3] = 255;

      const bVal = Math.round(h * 255);
      bump[idx] = bVal;
      bump[idx + 1] = bVal;
      bump[idx + 2] = bVal;
      bump[idx + 3] = 255;

      const inv = 1 / Math.hypot(dx, dy, 1);
      normal[idx] = Math.round((-dx * inv * 0.5 + 0.5) * 255);
      normal[idx + 1] = Math.round((-dy * inv * 0.5 + 0.5) * 255);
      normal[idx + 2] = Math.round((inv * 0.5 + 0.5) * 255);
      normal[idx + 3] = 255;
    }
  }

  CACHE.coinTex = {
    map: makeTextureFromRGBA(S, S, albedo, true, 1, 1),
    roughnessMap: makeTextureFromRGBA(S, S, rough, false, 1, 1),
    bumpMap: makeTextureFromRGBA(S, S, bump, false, 1, 1),
    normalMap: makeTextureFromRGBA(S, S, normal, false, 1, 1),
  };
  return CACHE.coinTex;
}

function getCoinMaterial() {
  if (CACHE.coinMat) return CACHE.coinMat;
  const tex = getCoinTextures();
  CACHE.coinMat = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(0xf5f1e8),
    map: tex.map,
    metalness: 1.0,
    roughness: 0.18,
    roughnessMap: tex.roughnessMap,
    normalMap: tex.normalMap,
    normalScale: new THREE.Vector2(0.55, 0.55),
    bumpMap: tex.bumpMap,
    bumpScale: 0.00045,
    clearcoat: 0.1,
    clearcoatRoughness: 0.24,
    reflectivity: 1.0,
    envMapIntensity: 1.35,
    vertexColors: true,
  });
  return CACHE.coinMat;
}

/**
 * 4. makeCoin40Sous(opts = {})
 * 2-franc ("40 sous") silver coin about 27 mm (0.027 m diameter, radius 0.0135 m),
 * raised rim, embossed profile and lettering via canvas-generated normal/bump map, worn edges.
 * Origin on the floor (y = 0), +Y up.
 */
export function makeCoin40Sous(opts = {}) {
  const group = new THREE.Group();
  group.name = opts.name || 'coin40Sous';

  const radius = 0.0135; // 27 mm diameter = 0.027 m
  const thickness = 0.0023; // ~2.3 mm at raised rim
  const radialSegs = 72;
  const ringSegs = 12;

  // Build custom coin geometry with raised rim, recessed field, embossed central relief boss,
  // planar top/bottom UV mapping for the coin faces, and worn milled edge vertices.
  const positions = [];
  const uvs = [];
  const colors = [];
  const indices = [];

  const edgeRng = rng(401815);
  const edgeWear = new Float32Array(radialSegs);
  for (let s = 0; s < radialSegs; s++) {
    const a = (s / radialSegs) * Math.PI * 2;
    edgeWear[s] =
      1 -
      0.018 * Math.pow(0.5 + 0.5 * Math.sin(a * 3 + 1.1), 2) -
      0.012 * edgeRng();
  }

  // Face profile height function (rNorm in 0..1)
  const faceRelief = (rNorm) => {
    // Raised outer rim (rNorm = 0.85..0.98), recessed field (0.55..0.85), slight central portrait dome (0..0.58)
    const rim = smoothstep(0.83, 0.90, rNorm) * (1 - 0.35 * smoothstep(0.96, 1.0, rNorm)) * 0.00028;
    const boss = (1 - smoothstep(0.0, 0.62, rNorm)) * 0.00018;
    return rim + boss;
  };

  // Top face vertices (index 0 is center, followed by ringSegs concentric rings of radialSegs vertices)
  positions.push(0, thickness - 0.0001, 0);
  uvs.push(0.5, 0.5);
  colors.push(1.0, 0.99, 0.97);

  for (let rIdx = 1; rIdx <= ringSegs; rIdx++) {
    const rNorm = rIdx / ringSegs;
    const hOffset = faceRelief(rNorm);
    // Crevice tarnish just inside the raised rim (rNorm ~ 0.82)
    const rimCrevice = Math.exp(-Math.pow((rNorm - 0.82) / 0.05, 2)) * 0.48;
    for (let s = 0; s < radialSegs; s++) {
      const a = (s / radialSegs) * Math.PI * 2;
      const wear = lerp(1.0, edgeWear[s], smoothstep(0.75, 1.0, rNorm));
      const rad = radius * rNorm * wear;
      const x = Math.cos(a) * rad;
      const z = Math.sin(a) * rad;
      const y = thickness - 0.00028 + hOffset * wear;
      positions.push(x, y, z);
      uvs.push(0.5 + 0.49 * rNorm * Math.cos(a), 0.5 + 0.49 * rNorm * Math.sin(a));
      colors.push(lerp(1.0, 0.42, rimCrevice), lerp(0.99, 0.38, rimCrevice), lerp(0.97, 0.34, rimCrevice));
    }
  }

  for (let s = 0; s < radialSegs; s++) {
    const sNext = (s + 1) % radialSegs;
    indices.push(0, 1 + sNext, 1 + s);
  }
  for (let rIdx = 1; rIdx < ringSegs; rIdx++) {
    const ringA = 1 + (rIdx - 1) * radialSegs;
    const ringB = 1 + rIdx * radialSegs;
    for (let s = 0; s < radialSegs; s++) {
      const sNext = (s + 1) % radialSegs;
      indices.push(ringA + s, ringA + sNext, ringB + s, ringA + sNext, ringB + sNext, ringB + s);
    }
  }

  // Bottom face vertices (resting on y = 0 at the outer rim)
  const botCenterIdx = positions.length / 3;
  positions.push(0, 0.00018, 0);
  uvs.push(0.5, 0.5);
  colors.push(0.94, 0.92, 0.89);

  for (let rIdx = 1; rIdx <= ringSegs; rIdx++) {
    const rNorm = rIdx / ringSegs;
    const hOffset = faceRelief(rNorm);
    const rimCrevice = Math.exp(-Math.pow((rNorm - 0.82) / 0.05, 2)) * 0.5;
    for (let s = 0; s < radialSegs; s++) {
      const a = (s / radialSegs) * Math.PI * 2;
      const wear = lerp(1.0, edgeWear[s], smoothstep(0.75, 1.0, rNorm));
      const rad = radius * rNorm * wear;
      const x = Math.cos(a) * rad;
      const z = Math.sin(a) * rad;
      const y = Math.max(0, 0.00028 - hOffset * wear);
      positions.push(x, y, z);
      uvs.push(0.5 - 0.49 * rNorm * Math.cos(a), 0.5 + 0.49 * rNorm * Math.sin(a));
      colors.push(lerp(0.96, 0.40, rimCrevice), lerp(0.94, 0.36, rimCrevice), lerp(0.91, 0.32, rimCrevice));
    }
  }

  for (let s = 0; s < radialSegs; s++) {
    const sNext = (s + 1) % radialSegs;
    indices.push(botCenterIdx, botCenterIdx + 1 + s, botCenterIdx + 1 + sNext);
  }
  for (let rIdx = 1; rIdx < ringSegs; rIdx++) {
    const ringA = botCenterIdx + 1 + (rIdx - 1) * radialSegs;
    const ringB = botCenterIdx + 1 + rIdx * radialSegs;
    for (let s = 0; s < radialSegs; s++) {
      const sNext = (s + 1) % radialSegs;
      indices.push(ringA + s, ringB + s, ringA + sNext, ringA + sNext, ringB + s, ringB + sNext);
    }
  }

  // Worn milled outer edge strip connecting top rim and bottom rim with reeded notches & bevel
  const edgeBaseIdx = positions.length / 3;
  const edgeRows = 4;
  for (let er = 0; er < edgeRows; er++) {
    const v = er / (edgeRows - 1); // 0 bottom to 1 top
    const bevel = Math.sin(v * Math.PI) * 0.00018;
    for (let s = 0; s < radialSegs; s++) {
      const a = (s / radialSegs) * Math.PI * 2;
      const milling = (s & 1 ? 0.00008 : -0.00008) * Math.sin(v * Math.PI);
      const rad = radius * edgeWear[s] + bevel + milling;
      positions.push(Math.cos(a) * rad, v * thickness, Math.sin(a) * rad);
      uvs.push(s / radialSegs, 0.97);
      const grooveTarnish = s & 1 ? 0.15 : 0.52;
      colors.push(lerp(1.0, 0.38, grooveTarnish), lerp(0.98, 0.34, grooveTarnish), lerp(0.95, 0.30, grooveTarnish));
    }
  }
  for (let er = 0; er < edgeRows - 1; er++) {
    const rA = edgeBaseIdx + er * radialSegs;
    const rB = edgeBaseIdx + (er + 1) * radialSegs;
    for (let s = 0; s < radialSegs; s++) {
      const sNext = (s + 1) % radialSegs;
      indices.push(rA + s, rA + sNext, rB + s, rA + sNext, rB + sNext, rB + s);
    }
  }

  const coinGeo = new THREE.BufferGeometry();
  coinGeo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  coinGeo.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  coinGeo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  coinGeo.setIndex(indices);
  coinGeo.computeVertexNormals();
  coinGeo.computeBoundingBox();
  if (coinGeo.boundingBox.min.y !== 0) {
    coinGeo.translate(0, -coinGeo.boundingBox.min.y, 0);
  }

  const coinMesh = new THREE.Mesh(coinGeo, getCoinMaterial());
  coinMesh.name = 'coin';
  coinMesh.castShadow = true;
  coinMesh.receiveShadow = true;
  group.add(coinMesh);

  function update() {}

  const anchors = {
    base: new THREE.Vector3(0, 0, 0),
    center: new THREE.Vector3(0, thickness * 0.5, 0),
    top: new THREE.Vector3(0, thickness, 0),
  };

  group.userData = { coin: coinMesh, radius, thickness, update, anchors };
  return { group, update, anchors, coin: coinMesh };
}
