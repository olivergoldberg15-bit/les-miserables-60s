import * as THREE from 'three';
import { clamp, seeded, material, mesh, box, sphere, cylinder, ground, lightRig, suggestedLook, makeSky, mountains, rubble, fbm, terrainHeight } from './land.js';

export function ironChain(parent, position = [0, 2, 0], length = 1.4) {
  const group = new THREE.Group(); group.position.set(...position); parent.add(group); const iron = material(0x292b2b, 'metal', { metalness: .85, roughness: .66 });
  const count = Math.ceil(length / .075);
  for (let i = 0; i < count; i++) { const link = mesh(group, new THREE.TorusGeometry(.036, .009, 5, 10), iron, [.015 * Math.sin(i * .5), -i * .075, 0], 'chain link'); link.scale.y = 1.45; link.rotation.y = i % 2 * Math.PI / 2; }
  return group;
}
function roof(g, w, d, y, mat, gableMat = material(0xa69d85)) {
  const rise = w * .27, slope = Math.hypot(w / 2 + .15, rise);
  const outline = new THREE.Shape(); outline.moveTo(-w/2,0); outline.lineTo(w/2,0); outline.lineTo(0,rise); outline.closePath(); const gable = new THREE.ExtrudeGeometry(outline,{depth:d,bevelEnabled:false}); mesh(g,gable,gableMat,[0,y,-d/2],'gable');
  for (const sign of [-1, 1]) { const r = box(g, [slope, .12, d + .35], mat, [sign * (w / 4 + .075), y + rise / 2, 0], 'terracotta roof'); r.rotation.z = -sign * Math.atan2(rise, w / 2 + .15);
    // Half-cylinder barrel tiles follow each roof slope, with overlapping courses.
    if(mat.userData.surface==='tile'){const rows=Math.ceil(slope/.32),cols=Math.ceil((d+.35)/.21),tiles=new THREE.InstancedMesh(new THREE.CylinderGeometry(.105,.105,.35,6,1,true,0,Math.PI),mat,rows*cols),o=new THREE.Object3D();let k=0;for(let row=0;row<rows;row++)for(let col=0;col<cols;col++){const u=(row+.5)*slope/rows;o.position.set(-slope/2+u,.07,-(d+.35)/2+(col+.5)*(d+.35)/cols);o.rotation.set(0,Math.PI/2,Math.PI/2);o.updateMatrix();tiles.setMatrixAt(k++,o.matrix);}r.add(tiles);tiles.castShadow=tiles.receiveShadow=true;}
 }
}
function shutterWindow(g, x, y, z, scale = 1) {
  const dark = material(0x151c20), wood = material(0x394b45, 'wood');
  box(g, [.65 * scale, .95 * scale, .06], dark, [x,y,z], 'window recess');
  for(const side of [-1,1])box(g,[.07*scale,1.03*scale,.16],material(0xa89b83,'stone'),[x+side*.36*scale,y,z+.055],'recess reveal');

  for (const s of [-1, 1]) { box(g, [.27 * scale, 1.03 * scale, .065], wood, [x + s * .46 * scale, y, z + .02], 'shutter'); for (let j = 0; j < 7; j++) box(g, [.25 * scale, .025 * scale, .04], wood, [x + s * .46 * scale, y + (j - 3) * .12 * scale, z + .065]); }
  box(g, [.85 * scale, .08, .2], material(0xb2a88e, 'stone'), [x, y - .52 * scale, z], 'sill');
}
function house(g, x, y, z, w, h, d, ochre = false) {
  const b = new THREE.Group(); b.position.set(x, y, z); g.add(b);
  box(b, [w, h, d], material(ochre ? 0xb29970 : 0xbcb49e), [0, h / 2, 0], 'limestone house'); roof(b, w, d, h, material(0x92523b, 'tile'));
  for (let floor = 0; floor < Math.floor(h / 2.2); floor++) for (const s of [-1, 1]) shutterWindow(b, s * w * .25, 1.5 + floor * 2, d / 2 + .04, .8);
  for(const side of [-1,1])for(let course=0;course<Math.floor(h/.38);course++){box(b,[course%2?.32:.48,.34,.17],material(0xb7ad96,'stone'),[side*(w/2-.15),.2+course*.38,d/2+.035],'limestone quoin');}
  box(b,[.4,.95,.42],material(0x897a65,'stone'),[w*.28,h+.48,-d*.22],'chimney');
  box(b, [.8, 1.85, .1], material(0x47382b, 'wood'), [0, .925, d / 2 + .06], 'door'); return b;
}
export function makeTownDusk(opts = {}) {
  const group = new THREE.Group(); group.name = 'Digne at dusk'; ground(group, 120, 0x766b51); const random = seeded(1815);
  const elevation = (x,z) => Math.max(0, -6 + 8.55 * Math.sqrt(Math.max(0, 1 - (x / 24.7) ** 2 - ((z + 16) / 19) ** 2)));
  const hillGeo=new THREE.PlaneGeometry(57,48,96,80);hillGeo.rotateX(-Math.PI/2);hillGeo.translate(0,0,-16);const hp=hillGeo.attributes.position;for(let i=0;i<hp.count;i++){const x=hp.getX(i),z=hp.getZ(i);hp.setY(i,elevation(x,z)+.08*fbm(x,z));}hillGeo.computeVertexNormals();mesh(group,hillGeo,material(0x827a5d,'earth'),[0,0,0],'weathered town hillside');
  // Attached terraces step around a narrow winding street.
  for(let row=0;row<4;row++)for(const side of [-1,1])for(let col=0;col<3;col++){
    const z=-6-row*5.7,x=side*(4.25+col*4.15)+Math.sin(z*.17)*1.1;
    house(group,x,elevation(x,z)+.05,z,4.2,4.4+Math.floor(random()*3)*1.95,5.6,random()>.45);
  }
  const cathedral = new THREE.Group(); cathedral.position.set(5.5, 1.4, -24); group.add(cathedral);
  const limestone = material(0xb0aa94, 'stone'); box(cathedral, [6, 6, 10], limestone, [0, 3, 0], 'cathedral nave'); roof(cathedral, 6, 10, 6, material(0x8e5842, 'tile'));
  box(cathedral, [2.8, 10, 2.8], limestone, [-2, 5, 3], 'cathedral bell tower');
  for (const x of [-2.7, -1.3]) box(cathedral, [.5, 1.3, .08], material(0x1d2529), [x, 8.6, 4.44], 'belfry opening');
  const towerRoof=new THREE.Group();towerRoof.position.set(-2,0,3);cathedral.add(towerRoof);roof(towerRoof,3.2,3.2,10,material(0x84503c,'tile')); box(cathedral, [.09, .8, .09], material(0x3f3c32, 'metal'), [-2, 11.25, 3]); box(cathedral, [.5, .08, .08], material(0x3f3c32, 'metal'), [-2, 11.4, 3]);
  const roadGeo = new THREE.PlaneGeometry(3.2, 53, 2, 64); roadGeo.rotateX(-Math.PI / 2); roadGeo.translate(0, 0, 7); const rp = roadGeo.attributes.position; for (let i=0;i<rp.count;i++) {const z=rp.getZ(i);rp.setX(i,rp.getX(i)+Math.sin(z*.17)*1.1);rp.setY(i,elevation(rp.getX(i),z)+.08)}; roadGeo.computeVertexNormals(); mesh(group, roadGeo, material(0x8c8170,'cobble'), [0,0,0], 'road entering town');
  for (const side of [-1, 1]) box(group, [.35, .23, 20], limestone, [side * 2, .115, 20], 'road wall');
  mountains(group); group.add(makeSky().group); lightRig(group, { sunset: true, key: 3 });
  return { group, look: suggestedLook(), anchors: { roadStart: new THREE.Vector3(0, 0, 22), roadEnd: new THREE.Vector3(0, 0, -5), town: new THREE.Vector3(0, 4, -18) } };
}
function facade(group, width = 6, height = 3.4, opening = 1.15, doorHeight = 2.12) {
  const stone = material(0xa29b87, 'stone');
  for (const sign of [-1, 1]) rubble(group,(width-opening)/2,height,.48,[sign*(width+opening)/4,height/2,-.22]);
  rubble(group,opening,height-doorHeight,.48,[0,(height+doorHeight)/2,-.22]);
  for (const sign of [-1, 1]) box(group, [.16, doorHeight + .1, .58], material(0xb4ac96, 'stone'), [sign * (opening / 2 + .08), doorHeight / 2, -.19], 'door jamb');
  box(group, [opening + .4, .16, .64], stone, [0, doorHeight + .08, -.16], 'lintel'); box(group, [opening + .25, .1, .65], stone, [0, .05, .06], 'threshold');
}
function doorSet(kind) {
  const group = new THREE.Group(); group.name = kind; ground(group,12,0x4a4a44);cobbles(group,8,8); facade(group); const hinge = new THREE.Group(); hinge.position.set(-.565, .1, .035); group.add(hinge);
  const door = box(hinge, [1.12, 2.02, .085], material(kind === 'bishop' ? 0x67503b : 0x45382a, 'wood'), [.56, 1.01, 0], 'door leaf');
  const iron = material(0x353532, 'metal', { metalness: .8, roughness: .58 });
  for (const y of [.35, 1.6]) box(hinge, [.9, .055, .025], iron, [.51, y, .06], 'strap hinge');
  sphere(hinge, .035, iron, [.96, 1, .085], 'door handle');
  const interior = new THREE.Group(); group.add(interior); box(interior, [1.15, 2.04, .02], material(0x9f7341, 'plaster', { emissive: 0xb86c25, emissiveIntensity: .55 }), [0, 1.12, -.65], 'warm interior');
  box(interior, [2.8, .03, 3], material(0x8b6542, 'wood'), [0, .04, -1.4], 'interior floor');
  const lamp = new THREE.PointLight(0xffb36b, 30, 8, 2); lamp.position.set(.2, 1.65, -.35); group.add(lamp); lightRig(group, { night: true, key: .7 });
  const update = (t = 0, p = 0) => { const open = kind === 'inn' ? 1 - clamp(p) : clamp(p); hinge.rotation.y = -open * Math.PI * .48; lamp.intensity = 30 * open * (1 + .035 * Math.sin(t * 9.7)); interior.visible = open > .001; };
  update(0, 0);
  return { group, update, look: suggestedLook(true), anchors: { door: new THREE.Vector3(0, 1, .12), threshold: new THREE.Vector3(0, .1, .4), figure: new THREE.Vector3(0, 0, 1.25), handle: new THREE.Vector3(.395, 1.1, .12) }, parts: { hinge, door, lamp, interior } };
}
export function makeInnDoor(opts = {}) { return doorSet('inn'); }
export function makeBishopDoor(opts = {}) { return doorSet('bishop'); }
export function makePrisonDoor(opts = {}) {
  const group = new THREE.Group(); ground(group,12,0x414443);cobbles(group,8,8); facade(group); const wood = material(0x40382e, 'wood'), iron = material(0x2c3030, 'metal', { metalness: .85, roughness: .65 });
  // Split leaf leaves a real aperture behind the sliding wicket.
  box(group, [1.12, 1.22, .13], wood, [0, .71, .02], 'lower door'); box(group, [1.12, .33, .13], wood, [0, 1.955, .02]);
  for (const s of [-1, 1]) box(group, [.34, .45, .13], wood, [s * .39, 1.555, .02]);
  const darkness = box(group, [.45, .4, .025], material(0x10151b), [0, 1.55, -.3]);
  for (const y of [.3, .95, 1.86]) { box(group, [1.12, .095, .04], iron, [0, y, .11], 'iron binding'); for (const x of [-.45, -.2, .2, .45]) sphere(group, .018, iron, [x, y, .14]); }
  for (let i = 0; i < 4; i++) cylinder(group, .012, .012, .4, iron, [-.16 + i * .105, 1.55, .07], 'wicket bar');
  const wicket = box(group, [.46, .44, .045], iron, [0, 1.55, .15], 'sliding wicket');
  const bell = mesh(group, new THREE.LatheGeometry([new THREE.Vector2(.12, 0), new THREE.Vector2(.105, .04), new THREE.Vector2(.065, .14), new THREE.Vector2(.025, .18)], 20), material(0x7c6744, 'metal', { metalness: .8 }), [1.13, 2.1, .32], 'bell');
  box(group, [.12, .16, .65], iron, [1.13, 2.36, .05], 'bell bracket'); ironChain(group, [1.13, 2.1, .34], 1.25); lightRig(group, { night: true, key: 1.5 });
  const update = (t = 0, p = 0) => { wicket.position.x = -.53 * (1 - clamp(p)); };
  update(); return { group, update, look: suggestedLook(true), anchors: { wicket: new THREE.Vector3(0, 1.55, .2), chain: new THREE.Vector3(1.13, 1, .34), figure: new THREE.Vector3(0, 0, 1.3) }, parts: { wicket, bell, darkness } };
}
export function makeKennel(opts = {}) {
  const group = new THREE.Group(); ground(group, 12, 0x4c493b); const wood = material(0x6b5439, 'wood');
  box(group, [.12, .8, 1.2], wood, [-.54, .4, 0]); box(group, [.12, .8, 1.2], wood, [.54, .4, 0]); box(group, [1.2, .8, .1], wood, [0, .4, -.56]); box(group, [1.2, .08, 1.2], wood, [0, .04, 0]);
  for (const s of [-1, 1]) box(group, [.29, .8, .1], wood, [s * .455, .4, .56]); box(group, [.62, .14, .1], wood, [0, .73, .56]); roof(group, 1.25, 1.3, .8, wood, wood);
  for (const s of [-1, 1]) sphere(group, .018, material(0xc1a568, 'metal', { emissive: 0xad8e4f, emissiveIntensity: .8, roughness: .2 }), [s * .11, .37, .12], 'eye glint');
  lightRig(group, { night: true, key: 1.1 }); return { group, look: suggestedLook(true), anchors: { entrance: new THREE.Vector3(0, .3, .65), figure: new THREE.Vector3(0, 0, 1.8) } };
}
function cobbles(g,width,length){const geo=new THREE.PlaneGeometry(width,length,32,96);geo.rotateX(-Math.PI/2);const p=geo.attributes.position,uv=geo.attributes.uv;for(let i=0;i<p.count;i++){const x=p.getX(i),z=p.getZ(i);p.setY(i,.015+terrainHeight(x,z)*.3);uv.setXY(i,x*1.8,z*1.8);}geo.computeVertexNormals();return mesh(g,geo,material(0x77766d,'cobble',{roughness:.64,normalScale:new THREE.Vector2(1.2,1.2)}),[0,0,0],'damp cobbled street');}
function lantern(g,x,y,z){const iron=material(0x242c2c,'metal',{metalness:.8}),flame=new THREE.MeshStandardMaterial({color:0xffd39a,emissive:0xffab55,emissiveIntensity:3,roughness:.4});box(g,[.09,.12,.6],iron,[x,y+.22,z-.2],'lantern bracket');box(g,[.24,.33,.22],flame,[x,y,z],'warm lantern glazing');for(const side of [-1,1])for(const depth of [-1,1])box(g,[.018,.38,.018],iron,[x+side*.12,y,z+depth*.11],'lantern iron frame');for(const dy of [-.19,.19])box(g,[.3,.045,.28],iron,[x,y+dy,z]);const light=new THREE.PointLight(0xffb36b,22,7,2);light.position.set(x,y-.12,z+.15);g.add(light);}
export function makeNightStreet(opts = {}) {
  const group = new THREE.Group(); ground(group, 35, 0x55554e); cobbles(group,4,30);
  for (const s of [-1, 1]) for (let i = 0; i < 4; i++) { const h = house(group, s * 5, 0, -i * 6, 5.7, 6.8, 5, i % 2 === 0); h.rotation.y = -s * Math.PI / 2; }
  for(const side of [-1,1])lantern(group,side*2.05,2.6,-3-side*2);group.add(makeSky({ night: true }).group); lightRig(group, { night: true, key: 1.2 });
  return { group, look: suggestedLook(true), anchors: { street: new THREE.Vector3(0, 0, -7) } };
}
export function makeBakeryWindow(opts = {}) {
  const group = new THREE.Group(); ground(group, 12, 0x4e4a42); const wood = material(0x50402e, 'wood'), stone = material(0x9f937c, 'stone');
  box(group, [6, .85, .45], stone, [0, .425, -.2]); box(group, [6, 1, .45], stone, [0, 2.85, -.2]); for (const s of [-1, 1]) box(group, [1.95, 1.5, .45], stone, [s * 2.025, 1.6, -.2]);
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x8daba9, metalness: 0, roughness: .19, transparent: true, opacity: .24, side: THREE.DoubleSide });
  const panes = []; let broken;
  for (let x = 0; x < 4; x++) for (let y = 0; y < 3; y++) { const pane = box(group, [.47, .43, .012], glass, [-.75 + x * .5, 1.1 + y * .46, .045], 'window pane'); panes.push(pane); if (x === 2 && y === 0) broken = pane; }
  for (let i = 0; i <= 4; i++) box(group, [.035, 1.5, .09], wood, [-1 + i * .5, 1.55, .09], 'mullion'); for (let i = 0; i <= 3; i++) box(group, [2.05, .035, .09], wood, [0, .87 + i * .46, .09], 'transom');
  box(group, [2.3, .12, .65], wood, [0, .85, -.1], 'bread shelf'); box(group, [2.1, 1.5, .025], material(0x66503b), [0, 1.6, -.8], 'shop interior');
  const loaf = sphere(group, .26, material(0x9c642d, 'bread'), [.25, 1.04, -.26], 'loaf'); loaf.scale.set(1.45, .64, .78);
  for (let i = 0; i < 4; i++) { const slash = box(loaf, [.045, .018, .65], material(0xd0a267, 'bread'), [-.55 + i * .35, .89, 0]); slash.rotation.y = -.25; slash.scale.multiplyScalar(.26); }
  const shardGroup = new THREE.Group(); group.add(shardGroup); const random = seeded(1796), shards = [];
  // Triangle fan fills the selected pane at p=0; seeded velocities reconstruct at every seek.
  const corners = [[-.235,-.215],[.235,-.215],[.235,.215],[-.235,.215]], center = [.02,-.025];
  for (let i = 0; i < 4; i++) { const a = corners[i], b = corners[(i+1)%4]; for (let j = 0; j < 3; j++) {
    const u = j/3, v = (j+1)/3, vertices = [center[0],center[1],0,a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u,0,a[0]+(b[0]-a[0])*v,a[1]+(b[1]-a[1])*v,0];
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(vertices,3)); geo.computeVertexNormals(); const s = mesh(shardGroup, geo, glass.clone(), broken.position.toArray(), 'glass shard');
    shards.push({ mesh:s, velocity:new THREE.Vector3((random()-.5)*1.8,random()*.65,.3+random()), spin:new THREE.Vector3(random()*5,random()*6,random()*4) });
  } }
  const lamp = new THREE.PointLight(0xffb36b, 20, 6, 2); lamp.position.set(-.6, 2.15, -.5); group.add(lamp); lightRig(group, { night:true, key:.8 });
  const update = (t=0,p=0) => { p=clamp(p); broken.visible=p===0; shardGroup.visible=p>0; for (const s of shards) { s.mesh.position.copy(broken.position).addScaledVector(s.velocity,p); s.mesh.position.y-=2.7*p*p; s.mesh.rotation.set(s.spin.x*p,s.spin.y*p,s.spin.z*p); s.mesh.material.opacity=.24*(1-p*.7); } loaf.position.set(.25+ .4*p,1.04+.08*Math.sin(p*Math.PI),-.26+1.1*p); };
  update(); return { group,update,look:suggestedLook(true), anchors:{pane:broken.position.clone(),loaf:new THREE.Vector3(.25,1.04,-.26)},parts:{loaf,brokenPane:broken,shards:shardGroup,lamp} };
}
