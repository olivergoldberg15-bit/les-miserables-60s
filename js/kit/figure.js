import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as SkeletonUtils from 'three/addons/utils/SkeletonUtils.js';

let figuresPromise;
const clamp = p => Math.max(0, Math.min(1, Number.isFinite(p) ? p : 0));
const ease = p => { p = clamp(p); return p * p * (3 - 2 * p); };

// One asset request, including concurrent callers. Load failures remain explicit.
export async function loadFigures() {
  figuresPromise ??= new GLTFLoader().loadAsync(new URL('../../vendor/Xbot.glb', import.meta.url).href)
    .then(gltf => {
      const walk = gltf.animations.find(clip => /^walk$/i.test(clip.name));
      if (!walk) throw new Error('Xbot.glb: required walk clip is missing');
      return {
        makeValjean: () => makeFigure(gltf.scene, walk, 'valjean'),
        makeBoy: () => makeFigure(gltf.scene, walk, 'boy'),
        makeGendarme: () => makeFigure(gltf.scene, walk, 'gendarme')
      };
    });
  return figuresPromise;
}

function makeFigure(source, walkClip, kind) {
  const group = new THREE.Group();
  group.name = kind;
  const motion = new THREE.Group();
  const model = SkeletonUtils.clone(source);
  group.add(motion); motion.add(model);
  model.updateMatrixWorld(true);
  const bounds = new THREE.Box3().setFromObject(model);
  const scale = 1.82 / (bounds.max.y - bounds.min.y);
  model.scale.multiplyScalar(scale);
  model.position.y -= bounds.min.y * scale;
  model.updateMatrixWorld(true);
  if (kind === 'boy') group.scale.setScalar(0.55);

  const bones = {};
  model.traverse(o => {
    if (o.isBone) bones[o.name.replace(/^mixamorig:?/, '')] = o;
  });
  for (const name of ['Hips', 'Spine', 'Spine2', 'Head', 'RightArm', 'LeftArm',
    'RightForeArm', 'LeftForeArm', 'RightHand', 'LeftHand', 'RightUpLeg',
    'LeftUpLeg', 'RightLeg', 'LeftLeg', 'RightFoot', 'LeftFoot']) {
    if (!bones[name]) throw new Error(`Xbot.glb: required bone ${name} is missing`);
  }

  // Linear data texture: fine woven relief, never a color image or mannequin map.
  const pixels = new Uint8Array(32 * 32 * 4);
  for (let y = 0; y < 32; y++) for (let x = 0; x < 32; x++) {
    const i = (y * 32 + x) * 4;
    const v = 218 + ((x * 17 + y * 31 + x * y * 7) % 17);
    pixels.set([v, v, v, 255], i);
  }
  const weave = new THREE.DataTexture(pixels, 32, 32);
  weave.wrapS = weave.wrapT = THREE.RepeatWrapping;
  weave.colorSpace = THREE.NoColorSpace;
  weave.repeat.set(28, 28); weave.needsUpdate = true;
  const cloth = new THREE.MeshStandardMaterial({ color: kind === 'gendarme' ? 0x121923 : 0x201d1a,
    roughness: 0.98, metalness: 0, bumpMap: weave, bumpScale: 0.00035, side: THREE.DoubleSide });
  const leather = new THREE.MeshStandardMaterial({ color: 0x17120e, roughness: 0.88, bumpMap: weave, bumpScale: 0.001 });
  const wood = new THREE.MeshStandardMaterial({ color: 0x3b2819, roughness: 0.92, bumpMap: weave, bumpScale: 0.002 });
  const iron = new THREE.MeshStandardMaterial({ color: 0x33373a, metalness: 0.65, roughness: 0.65 });
  model.traverse(o => {
    if (!o.isMesh) return;
    o.material = cloth; o.castShadow = o.receiveShadow = true;
    if (/joint/i.test(o.name)) o.visible = false;
  });
  const rest = new Map(Object.values(bones).map(b => [b, {
    position: b.position.clone(), quaternion: b.quaternion.clone(), scale: b.scale.clone()
  }]));
  const point = name => bones[name].getWorldPosition(new THREE.Vector3());
  const ownedGeometry = new Set();
  // Build in meter-space, then preserve the bind transform while parenting to a bone.
  function piece(name, bone, geometry, material, position, rotation = [0, 0, 0]) {
    ownedGeometry.add(geometry);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = name; mesh.position.copy(position); mesh.rotation.set(...rotation);
    mesh.castShadow = mesh.receiveShadow = true;
    motion.add(mesh); motion.updateMatrixWorld(true); bones[bone].attach(mesh);
    return mesh;
  }
  const head = point('Head'), chest = point('Spine2'), hips = point('Hips');
  const cylinder = (rt, rb, h, n = 12) => new THREE.CylinderGeometry(rt, rb, h, n);
  piece('coat torso', 'Spine2', cylinder(0.22, 0.25, 0.49), cloth, chest.clone().add(new THREE.Vector3(0, -0.15, 0)));
  // Open-front cloth shells: +Z is the face, the gap separates the two tails.
  function foldedShell(top, bottom, height, gap = 0.32) {
    const g = new THREE.CylinderGeometry(top, bottom, height, 64, 12, true,
      gap / 2, Math.PI * 2 - gap);
    const v = g.attributes.position;
    for (let i = 0; i < v.count; i++) {
      const x = v.getX(i), z = v.getZ(i), y = v.getY(i);
      const angle = Math.atan2(x, z), down = (height / 2 - y) / height;
      const ripple = 1 + (0.018 + 0.025 * down) * Math.cos(angle * 18);
      v.setXYZ(i, x * ripple, y + 0.008 * down * Math.cos(angle * 9), z * ripple * 0.78);
    }
    g.computeVertexNormals();
    return g;
  }
  const skirt = piece('open folded coat tails', 'Hips',
    foldedShell(0.26, kind === 'boy' ? 0.30 : 0.44, kind === 'boy' ? 0.30 : 0.70, 0.70), cloth,
    hips.clone().add(new THREE.Vector3(0, kind === 'boy' ? -0.13 : -0.32, -0.025)));
  const skirtRest = skirt.quaternion.clone();
  for (const side of ['Left', 'Right']) {
    for (const [a, b, radius] of [['Arm', 'ForeArm', 0.079], ['ForeArm', 'Hand', 0.065], ['UpLeg', 'Leg', 0.10], ['Leg', 'Foot', 0.082]]) {
      const start = point(side + a), end = point(side + b), direction = end.clone().sub(start);
      const sleeve = piece(`${side} ${a} cloth`, side + a, cylinder(radius, radius * 0.92, direction.length() + 0.035),
        a === 'Leg' ? leather : cloth, start.clone().add(end).multiplyScalar(0.5));
      // Convert desired world orientation into bone-local orientation.
      const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
      sleeve.quaternion.copy(bones[side + a].getWorldQuaternion(new THREE.Quaternion()).invert().multiply(q));
    }
    const foot = point(side + 'Foot');
    const toeBone = bones[side + 'ToeBase'];
    const forward = toeBone ? point(side + 'ToeBase').sub(foot) : new THREE.Vector3(0, 0, 1);
    forward.y = 0; forward.normalize();
    const yaw = Math.atan2(forward.x, forward.z);
    const toe = piece(`${side} rounded boot toe`, side + 'Foot', new THREE.SphereGeometry(1, 16, 10), leather,
      foot.clone().addScaledVector(forward, 0.075).add(new THREE.Vector3(0, -0.018, 0)), [0, yaw, 0]);
    toe.scale.multiply(new THREE.Vector3(0.079, 0.075, 0.16));
    const sole = piece(`${side} boot sole`, side + 'Foot', new THREE.CapsuleGeometry(0.073, 0.15, 4, 12), leather,
      foot.clone().addScaledVector(forward, 0.065).add(new THREE.Vector3(0, -0.072, 0)), [Math.PI / 2, 0, -yaw]);
    sole.scale.z *= 0.24;
  }
  // Opaque featureless covering encloses the original robot head, including its face.
  const hood = piece('featureless head covering', 'Head', new THREE.SphereGeometry(1, 16, 12), cloth,
    head.clone().add(new THREE.Vector3(0, 0.10, 0)));
  hood.scale.multiply(new THREE.Vector3(0.117, 0.15, 0.12));
  const collar = piece('turned up wool collar', 'Spine2', cylinder(0.15, 0.19, 0.16, 24), cloth,
    head.clone().add(new THREE.Vector3(0, -0.065, -0.015)));
  const beard = piece('dark hair and beard mass', 'Head', new THREE.SphereGeometry(1, 16, 12), cloth,
    head.clone().add(new THREE.Vector3(0, 0.015, 0.02)));
  beard.scale.multiply(new THREE.Vector3(0.12, 0.115, 0.125));
  if (kind === 'gendarme') {
    const shape = new THREE.Shape();
    shape.moveTo(-0.34, 0); shape.quadraticCurveTo(-0.22, 0.03, -0.12, 0.20);
    shape.quadraticCurveTo(0, 0.28, 0.12, 0.20); shape.quadraticCurveTo(0.22, 0.03, 0.34, 0);
    shape.lineTo(-0.34, 0);
    piece('bicorne', 'Head', new THREE.ExtrudeGeometry(shape, { depth: 0.16, bevelEnabled: true,
      bevelSegments: 2, steps: 1, bevelSize: 0.025, bevelThickness: 0.025 }), cloth,
    head.clone().add(new THREE.Vector3(0, 0.17, -0.08)));
    piece('crossbelt', 'Spine2', new THREE.BoxGeometry(0.055, 0.57, 0.025), leather,
      chest.clone().add(new THREE.Vector3(0, -0.15, 0.225)), [0, 0, -0.55]);
    piece('sabre grip', 'Hips', cylinder(0.021, 0.021, 0.14), leather,
      hips.clone().add(new THREE.Vector3(0.24, 0.13, -0.05)), [0, 0, -0.17]);
    piece('sabre scabbard', 'Hips', cylinder(0.018, 0.012, 0.76), leather,
      hips.clone().add(new THREE.Vector3(0.29, -0.32, -0.05)), [0, 0, -0.17]);
    piece('sabre guard', 'Hips', new THREE.TorusGeometry(0.06, 0.009, 6, 16), iron,
      hips.clone().add(new THREE.Vector3(0.24, 0.08, -0.05)), [0, Math.PI / 2, 0]);
  } else {
    const brim = piece(kind === 'boy' ? 'cap brim' : 'wide hat brim', 'Head', cylinder(kind === 'boy' ? 0.16 : 0.32,
      kind === 'boy' ? 0.16 : 0.32, 0.025, 32), cloth, head.clone().add(new THREE.Vector3(0, 0.20, 0.025)));
    const brimVertices = brim.geometry.attributes.position;
    for (let i = 0; i < brimVertices.count; i++) {
      const x = brimVertices.getX(i), z = brimVertices.getZ(i);
      brimVertices.setY(i, brimVertices.getY(i) + 0.028 * (x * x - z * z) / 0.1024);
    }
    brim.geometry.computeVertexNormals();
    const crown = piece('hat crown', 'Head', cylinder(0.12, 0.145, kind === 'boy' ? 0.08 : 0.15, 20), cloth,
      head.clone().add(new THREE.Vector3(0, kind === 'boy' ? 0.24 : 0.28, 0)));
  }
  let staff, cape;
  let capeRest;

  if (kind === 'valjean') {
    cape = piece('folded carrick shoulder cape', 'Spine2', foldedShell(0.22, 0.42, 0.38, 0.50), cloth,
      chest.clone().add(new THREE.Vector3(0, -0.06, -0.045)));
    capeRest = cape.quaternion.clone();
    piece('knapsack', 'Spine2', new THREE.BoxGeometry(0.36, 0.40, 0.19), leather,
      chest.clone().add(new THREE.Vector3(0, -0.15, -0.30)));
    staff = piece('wooden staff', 'RightHand', cylinder(0.018, 0.023, 1.52), wood,
      point('RightHand').add(new THREE.Vector3(0, -0.38, 0.035)), [0.05, 0, 0.07]);
  }

  const staffRest = staff && { position: staff.position.clone(), quaternion: staff.quaternion.clone() };
  const mixer = new THREE.AnimationMixer(model);
  // Keep locomotion in place; shots own travel. Retain vertical gait motion.
  const clip = walkClip.clone();
  for (const track of clip.tracks) if (/Hips\.position$/.test(track.name)) {
    for (let i = 0; i < track.values.length; i += 3) {
      track.values[i] = bones.Hips.position.x; track.values[i + 2] = bones.Hips.position.z;
    }
  }
  const walk = mixer.clipAction(clip); walk.setLoop(THREE.LoopRepeat, Infinity);
  let current = 'stand';
  const rotation = new THREE.Quaternion();
  function turn(name, x = 0, y = 0, z = 0) {
    const b = bones[name];
    rotation.setFromEuler(new THREE.Euler(x, y, z));
    b.quaternion.copy(rest.get(b).quaternion).multiply(rotation);
  }
  /** phase is normalized for gestures; walk accepts unbounded cycle phase. */
  function pose(name = 'stand', phase = 0) {
    if (!['stand', 'walk', 'knock', 'vault', 'kneel_collapse', 'held'].includes(name)) throw new Error(`Unknown figure pose: ${name}`);
    current = name;
    walk.stop(); mixer.setTime(0);
    for (const [b, r] of rest) { b.position.copy(r.position); b.quaternion.copy(r.quaternion); b.scale.copy(r.scale); }
    skirt.quaternion.copy(skirtRest);
    if (cape) cape.quaternion.copy(capeRest);
    motion.position.set(0, 0, 0); motion.rotation.set(0, 0, 0);
    if (staff) {
      staff.position.copy(staffRest.position); staff.quaternion.copy(staffRest.quaternion);
      staff.visible = name === 'walk' || name === 'stand';
    }
    const p = clamp(phase), k = ease(p);
    if (name === 'walk') {
      walk.reset().play();
      const cycle = Number.isFinite(phase) ? ((phase % 1) + 1) % 1 : 0;
      mixer.setTime(cycle * clip.duration);
      rotation.setFromEuler(new THREE.Euler(0.025 * Math.sin(cycle * Math.PI * 4), 0, 0.025 * Math.sin(cycle * Math.PI * 2)));
      skirt.quaternion.multiply(rotation);
      if (cape) cape.quaternion.multiply(rotation);

    } else {
      turn('LeftArm', 0, 0, -1.40); turn('RightArm', 0, 0, 1.40);
      turn('LeftForeArm', 0, -0.12); turn('RightForeArm', 0, 0.16);
      if (name === 'knock') {
        const lift = ease(p / 0.3);
        const tap = Math.sin(clamp((p - 0.3) / 0.7) * Math.PI * 6);
        turn('RightArm', 0, 0.5 * lift, 1.40 - 0.30 * lift);
        turn('RightForeArm', 0, (1.28 + 0.12 * tap) * lift);
      } else if (name === 'vault') {
        const arc = Math.sin(Math.PI * p);
        motion.position.set(0, 1.18 * arc, 1.6 * k);
        turn('Spine', 0.55 * arc); turn('LeftUpLeg', -1.25 * arc);
        turn('RightUpLeg', -0.85 * arc); turn('LeftLeg', 1.5 * arc); turn('RightLeg', 1.2 * arc);
        turn('LeftArm', 0, -0.8 * arc, -1.40 + 0.65 * arc);
        turn('RightArm', 0, 0.8 * arc, 1.40 - 0.65 * arc);
      } else if (name === 'kneel_collapse') {
        // Seated on a roughly 0.48 m stone; place that stone in the set.
        motion.position.set(0, -0.48 * k, -0.12 * k);
        turn('LeftUpLeg', -1.35 * k); turn('RightUpLeg', -1.35 * k);
        turn('LeftLeg', 1.48 * k); turn('RightLeg', 1.48 * k);
        turn('Spine', 0.48 * k); turn('Head', 0.55 * k);
        turn('LeftArm', 0, -0.65 * k, -1.40 + 0.35 * k);
        turn('RightArm', 0, 0.65 * k, 1.40 - 0.35 * k);
        turn('LeftForeArm', 0, -2.05 * k); turn('RightForeArm', 0, 2.05 * k);
      } else if (name === 'held') {
        turn('LeftArm', 0, -0.22, -1.12); turn('RightArm', 0, 0.22, 1.12);
        turn('LeftForeArm', 0, 0.45); turn('RightForeArm', 0, -0.45);
        turn('Head', 0.22); turn('Spine', 0.10);
      }
    }
    group.updateMatrixWorld(true);
    if (staff?.visible) {
      // Grip follows the hand; counter-rotate the shaft so a lowered bind-pose
      // arm cannot turn the walking stick sideways. Direction follows staging.
      const upright = motion.getWorldQuaternion(new THREE.Quaternion())
        .multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(0.05, 0, 0.07)));
      staff.quaternion.copy(staff.parent.getWorldQuaternion(new THREE.Quaternion()).invert().multiply(upright));
      const grip = staff.parent.getWorldPosition(new THREE.Vector3());
      const outward = new THREE.Vector3(-0.035, 0, 0.035).applyQuaternion(motion.getWorldQuaternion(new THREE.Quaternion()));
      const center = grip.add(outward).add(new THREE.Vector3(0, -0.38 * group.scale.y, 0));
      staff.position.copy(staff.parent.worldToLocal(center));
      group.updateMatrixWorld(true);
    }
  }
  // Absolute film time deliberately ignored; caller supplies pose progress.
  function update(_t, p = 0) { pose(current, p); }
  function dispose() {
    mixer.stopAllAction(); mixer.uncacheRoot(model);
    ownedGeometry.forEach(g => g.dispose());
    [cloth, leather, wood, iron].forEach(m => m.dispose()); weave.dispose();
    model.traverse(o => { if (o.isSkinnedMesh) o.skeleton.dispose(); });
    // Source GLB geometry is shared across clones and belongs to the asset cache.
    group.removeFromParent();
  }
  pose('stand', 0);
  return { group, update, pose, dispose };
}
