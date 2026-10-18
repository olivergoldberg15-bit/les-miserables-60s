import * as THREE from 'three';

// Shared deterministic construction helpers; no renderer or scene ownership.
export const clamp = p => Math.max(0, Math.min(1, Number.isFinite(p) ? p : 0));
export function seeded(seed = 1) {
  return () => { let t = seed += 0x6D2B79F5; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
const textures = new Map();
function surface(kind) {
  if (textures.has(kind)) return textures.get(kind);
  const n = 128, data = new Uint8Array(n * n * 4), random = seeded(831 + kind.length);
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    let v = 170 + random() * 55;
    if (kind === 'wood') v += 24 * Math.sin(x * .35 + Math.sin(y * .06) * 2) + 12 * Math.sin(x * 1.7);
    if (kind === 'stone') { const row = Math.floor(y / 32), xx = (x + (row % 2) * 32) % 64; if (y % 32 < 2 || xx < 2) v = 85 + random() * 25; }
    if (kind === 'tile') { if (x % 16 < 2 || y % 32 < 2) v = 95; else v += 20 * Math.sin(x * Math.PI / 8); }
    if (kind === 'cloth') v += (x % 2 ? -12 : 12) + (y % 2 ? -8 : 8);
    const i = (y * n + x) * 4; data[i] = data[i + 1] = data[i + 2] = Math.max(0, Math.min(255, v)); data[i + 3] = 255;
  }
  const tex = new THREE.DataTexture(data, n, n); tex.wrapS = tex.wrapT = THREE.RepeatWrapping; tex.magFilter = THREE.LinearFilter; tex.minFilter = THREE.LinearMipmapLinearFilter; tex.generateMipmaps = true; tex.needsUpdate = true;
  textures.set(kind, tex); return tex;
}
export function material(color, kind = 'plaster', extra = {}) {
  const map = surface(kind);
  return new THREE.MeshStandardMaterial({ color, map, bumpMap: map, bumpScale: kind === 'stone' ? .045 : .012, roughnessMap: map, roughness: .91, ...extra });
}
export function mesh(parent, geometry, mat, position = [0, 0, 0], name = '') {
  const m = new THREE.Mesh(geometry, mat); m.position.set(...position); m.castShadow = m.receiveShadow = true; m.name = name; parent.add(m); return m;
}
export const box = (g, size, m, p, name) => mesh(g, new THREE.BoxGeometry(...size), m, p, name);
export const sphere = (g, r, m, p, name) => mesh(g, new THREE.SphereGeometry(r, 16, 10), m, p, name);
export function cylinder(g, r1, r2, h, mat, p, name) { return mesh(g, new THREE.CylinderGeometry(r1, r2, h, 16), mat, p, name); }
export function ground(g, size = 40, color = 0x63533f) { return box(g, [size, .16, size], material(color, 'earth'), [0, -.08, 0], 'ground'); }
export function lightRig(g, { night = false, sunset = false, key = 2 } = {}) {
  const sun = new THREE.DirectionalLight(night ? 0x9db4ff : sunset ? 0xff9a55 : 0xffd9a8, key);
  sun.position.set(-9, night ? 12 : 5, -7); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -24, right: 24, top: 24, bottom: -24, near: .5, far: 100 }); sun.shadow.bias = -.0002; sun.shadow.normalBias = .03;
  g.add(sun, sun.target, new THREE.HemisphereLight(night ? 0x647bad : 0xa0a9ba, 0x39291c, night ? .28 : .65)); return sun;
}
export function suggestedLook(night = false) { const bg = night ? 0x111c30 : 0x66667a; return { bg, fog: { color: bg, density: night ? .018 : .009 }, exposure: night ? .95 : 1.05 }; }
export function makeSky(opts = {}) {
  const group = new THREE.Group(), night = !!opts.night;
  const sky = mesh(group, new THREE.SphereGeometry(135, 32, 16), new THREE.ShaderMaterial({ side: THREE.BackSide, depthWrite: false, uniforms: { upper: { value: new THREE.Color(night ? 0x091225 : 0x384b72) }, lower: { value: new THREE.Color(night ? 0x53617c : 0xd89a71) } }, vertexShader: 'varying vec3 vP; void main(){vP=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}', fragmentShader: 'varying vec3 vP;uniform vec3 upper,lower;void main(){float h=smoothstep(-.05,.8,normalize(vP).y);gl_FragColor=vec4(mix(lower,upper,h),1.);}' }), [0, 0, 0], 'sky'); sky.castShadow = sky.receiveShadow = false;
  const orb = sphere(group, night ? 1.4 : 2.3, new THREE.MeshBasicMaterial({ color: night ? 0xe1e6f2 : 0xffd0a0 }), opts.position ?? [-48, night ? 38 : 9, -80], night ? 'moon' : 'sun'); orb.castShadow = false;
  return { group, anchors: { orb: orb.position.clone() }, look: suggestedLook(night) };
}
export const makeMoonSky = (opts = {}) => makeSky({ ...opts, night: true });
export const makeSunsetSky = (opts = {}) => makeSky({ ...opts, night: false });
export function mountains(g) {
  const random = seeded(74), mat = material(0x465063, 'stone');
  for (let i = 0; i < 14; i++) { const h = 10 + random() * 17; const m = mesh(g, new THREE.ConeGeometry(10 + random() * 9, h, 6), mat, [-85 + i * 13, h / 2 - 3, -65 - random() * 12], 'alpine ridge'); m.rotation.y = random(); }
}
function path(g, angle, length = 38, width = 2.1) { const p = box(g, [width, .025, length], material(0x92785a, 'earth'), [Math.sin(angle) * length / 2, .015, Math.cos(angle) * length / 2], 'dirt path'); p.rotation.y = angle; return p; }
function brush(g, count = 110) {
  const random = seeded(493), mat = material(0x6e6245, 'wood');
  for (let i = 0; i < count; i++) { const x = (random() - .5) * 42, z = (random() - .5) * 42; if (Math.abs(x) < 2) continue;
    for (let j = 0; j < 3; j++) { const twig = cylinder(g, .009, .025, .3 + random() * .4, mat, [x + j * .07, .22, z]); twig.rotation.z = (random() - .5) * 1.5; twig.rotation.x = random() * .6; }
  }
}
export function makePlain(opts = {}) {
  const group = new THREE.Group(); group.name = 'sunset plain'; ground(group, 100, 0x766149); path(group, 0, 55); brush(group); mountains(group); group.add(makeSunsetSky().group); lightRig(group, { sunset: true, key: 2.8 });
  return { group, look: suggestedLook(), anchors: { coin: new THREE.Vector3(0, .04, 0), boy: new THREE.Vector3(1, 0, -14), path: new THREE.Vector3(0, 0, -8) } };
}
export function makeCrossroads(opts = {}) {
  const group = new THREE.Group(); ground(group, 100, 0x524f45); [0, 2.12, 4.2].forEach(a => path(group, a)); brush(group, 85); mountains(group); group.add(makeMoonSky().group); lightRig(group, { night: true, key: 1.6 });
  const stone = mesh(group, new THREE.IcosahedronGeometry(1, 1), material(0x777973, 'stone'), [1.9, .46, .4], 'weeping stone'); stone.scale.set(1.15, .65, .9); stone.rotation.set(.1, .35, .1);
  return { group, look: suggestedLook(true), anchors: { stone: new THREE.Vector3(1.9, .95, .4), figure: new THREE.Vector3(1.9, 0, 1.1) } };
}
export function makeGardenWall(opts = {}) {
  const group = new THREE.Group(); ground(group, 24, 0x3b4030); const stone = material(0x8e8b7b, 'stone');
  box(group, [12, 1.65, .48], stone, [0, .825, -1], 'garden wall'); box(group, [12.2, .16, .65], material(0xaaa392, 'stone'), [0, 1.73, -1], 'coping');
  box(group, [7, .16, 1.8], material(0x342a21, 'earth'), [0, .035, .3], 'flower bed');
  const random = seeded(129), leaf = material(0x394b33, 'plaster'), petal = material(0xaaa4b7, 'cloth');
  for (let i = 0; i < 70; i++) { const x = (random() - .5) * 6.8, z = random() * 1.4 - .3, y = .15 + random() * .25; const stem = cylinder(group, .007, .012, y, leaf, [x, y / 2 + .1, z]); stem.rotation.z = (random() - .5) * .5; const l = sphere(group, .07, leaf, [x, .18, z]); l.scale.set(1.5, .4, 1); if (i % 3 === 0) sphere(group, .04, petal, [x, y + .1, z]); }
  group.add(makeMoonSky().group); lightRig(group, { night: true, key: 1.8 });
  return { group, look: suggestedLook(true), anchors: { wallTop: new THREE.Vector3(0, 1.81, -1), flowerBed: new THREE.Vector3(0, .2, .3), basket: new THREE.Vector3(-.7, .2, .3) } };
}
