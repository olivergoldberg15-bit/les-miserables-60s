import * as THREE from 'three';
import { clamp, seeded, material, mesh, box, sphere, cylinder, ground, lightRig, suggestedLook } from './land.js';
import { ironChain } from './town.js';

function table(g, width = 2.5, depth = 1.05, height = .77) {
  const wood = material(0x705036, 'wood'); const top = box(g, [width, .075, depth], wood, [0, height - .0375, 0], 'tabletop');
  for (const x of [-1, 1]) for (const z of [-1, 1]) { box(g, [.085, height - .075, .085], wood, [x * (width / 2 - .14), (height - .075) / 2, z * (depth / 2 - .12)], 'table leg'); }
  box(g, [width - .2, .14, .055], wood, [0, height - .18, -depth / 2 + .08], 'table apron'); box(g, [width - .2, .14, .055], wood, [0, height - .18, depth / 2 - .08]); return top;
}
function windowWall(g, { width = 7, height = 3.3, z = -3, barred = false } = {}) {
  const wall = material(barred ? 0x767970 : 0xb6ab92, barred ? 'stone' : 'plaster'), x = 1.8, bottom = 1.35, top = 2.75, w = 1;
  box(g, [width, bottom, .32], wall, [0, bottom / 2, z]); box(g, [width, height - top, .32], wall, [0, (height + top) / 2, z]);
  box(g, [width / 2 + x - w / 2, top - bottom, .32], wall, [(-width / 2 + x - w / 2) / 2, (top + bottom) / 2, z]);
  box(g, [width / 2 - x - w / 2, top - bottom, .32], wall, [(width / 2 + x + w / 2) / 2, (top + bottom) / 2, z]);
  const frame = material(0x554534, 'wood'); for (const s of [-1, 1]) box(g, [.085, top - bottom + .15, .4], frame, [x + s * w / 2, (top + bottom) / 2, z]);
  for (const y of [bottom, top]) box(g, [w + .15, .08, .45], frame, [x, y, z]);
  const glass = box(g, [w - .06, top - bottom - .06, .02], new THREE.MeshPhysicalMaterial({ color:0x567b98, transparent:true, opacity:.35, roughness:.3 }), [x, (top + bottom) / 2, z + .02], 'window glass');
  if (barred) { const iron = material(0x252b2c, 'metal', {metalness:.8}); for (let i = 0; i < 5; i++) cylinder(g,.018,.018,top-bottom,iron,[x-.4+i*.2,(top+bottom)/2,z+.07],'window bar'); box(g,[w,.025,.035],iron,[x,2.05,z+.08]); }
  else { box(g,[.035,top-bottom,.06],frame,[x,(top+bottom)/2,z+.06]); box(g,[w,.035,.06],frame,[x,2.05,z+.06]); }
  return { position:new THREE.Vector3(x,2.05,z),glass };
}
function bread(g, position) {
  const loaf = sphere(g,.2,material(0x75502c,'bread'),position,'rye loaf'); loaf.scale.set(1.5,.72,.85);
  const crust=material(0xb18a52,'bread'); for(let i=0;i<4;i++){ const slash=box(g,[.025,.014,.19],crust,[position[0]-.16+i*.105,position[1]+.13,position[2]],'scored crust'); slash.rotation.y=-.35; } return loaf;
}
function bowl(g, position) {
  const ceramic = material(0xb5a688,'plaster',{roughness:.58});
  const profile = [[.035,0],[.06,.006],[.09,.025],[.12,.07],[.13,.09],[.12,.095],[.108,.07],[.08,.035],[.03,.018]].map(([r,y])=>new THREE.Vector2(r,y));
  const b=mesh(g,new THREE.LatheGeometry(profile,24),ceramic,position,'soup bowl'); cylinder(g,.106,.106,.004,material(0x76542a,'soup',{roughness:.32}),[position[0],position[1]+.064,position[2]],'soup'); return b;
}
function wineGlass(g, position) {
  const glass=new THREE.MeshPhysicalMaterial({color:0xc7bda7,roughness:.14,transparent:true,opacity:.3,metalness:0});
  cylinder(g,.035,.038,.006,glass,position,'glass foot'); cylinder(g,.006,.006,.07,glass,[position[0],position[1]+.04,position[2]],'glass stem');
  const pts=[[.007,0],[.025,.015],[.037,.04],[.034,.08],[.031,.08],[.033,.04],[.021,.017],[.007,.005]].map(([r,y])=>new THREE.Vector2(r,y)); mesh(g,new THREE.LatheGeometry(pts,20),glass,[position[0],position[1]+.075,position[2]],'wine glass'); cylinder(g,.029,.02,.025,material(0x3d1115,'wine',{roughness:.2}),[position[0],position[1]+.103,position[2]],'wine');
}
function chair(g,x,z,angle=0){const c=new THREE.Group();g.add(c);c.position.set(x,0,z);c.rotation.y=angle;const wood=material(0x5c432d,'wood');box(c,[.42,.055,.42],wood,[0,.45,0],'chair seat');for(const a of [-1,1])for(const b of [-1,1])box(c,[.04,b<0?.92:.43,.04],wood,[a*.18,b<0?.46:.215,b*.18]);for(const y of [.65,.82])box(c,[.38,.055,.04],wood,[0,y,-.18]);}
export function makeDiningRoom(opts={}) {
  const group=new THREE.Group(); group.name='bishop dining room'; ground(group,8,0x756a55); const plaster=material(0xb3a58c),wood=material(0x503b2b,'wood'),stone=material(0x968871,'stone');
  const win=windowWall(group); box(group,[.3,3.3,6.5],plaster,[-3.65,1.65,-.15],'side wall'); box(group,[.3,3.3,6.5],plaster,[3.65,1.65,-.15]);
  box(group,[7.5,.12,6.5],plaster,[0,3.35,-.15],'plaster ceiling'); for(let i=0;i<6;i++) box(group,[7.3,.2,.17],wood,[0,3.18,-2.6+i*1.05],'ceiling beam');
  // Hearth is an actual dark recess framed by jambs and a chimney breast.
  const hearthX=-1.65; box(group,[1.85,.09,.8],stone,[hearthX,.045,-2.65],'hearth stone'); box(group,[1.5,1.15,.06],material(0x26241f),[hearthX,.65,-2.8],'fireplace recess');
  for(const s of [-1,1])box(group,[.22,1.15,.45],stone,[hearthX+s*.72,.6,-2.65],'fireplace jamb');box(group,[1.85,.16,.65],stone,[hearthX,1.23,-2.62],'chimney-piece mantel');box(group,[1.7,1.9,.36],plaster,[hearthX,2.29,-2.83],'chimney breast');
  for(let i=0;i<3;i++){const log=cylinder(group,.055,.065,.63,wood,[hearthX+(i-1)*.12,.14,-2.58]);log.rotation.z=Math.PI/2;log.rotation.y=(i-1)*.4;}
  const emberMat=material(0x9b3917,'earth',{emissive:0xc24712,emissiveIntensity:1.3}); for(let i=0;i<5;i++)sphere(group,.035,emberMat,[hearthX-.24+i*.12,.13,-2.5],'embers');
  const hearthLight=new THREE.PointLight(0xff9845,9,5,2);hearthLight.position.set(hearthX,.35,-2.35);group.add(hearthLight);
  table(group,2.65,1.12,.78); const cloth=material(0xd4c7a9,'cloth');box(group,[2.35,.014,1.2],cloth,[0,.792,0],'linen cloth');for(const s of [-1,1])box(group,[2.35,.3,.015],cloth,[0,.65,s*.59],'hanging cloth');
  const settings=[]; for(const z of [-.4,.4]) for(const x of [-.85,0,.85]) {settings.push(new THREE.Vector3(x,.804,z)); bowl(group,[x,.806,z]);wineGlass(group,[x+.18,.806,z*.6]);chair(group,x,Math.sign(z)*.94,z>0?0:Math.PI);}
  bread(group,[-.54,.95,.04]);const cheese=cylinder(group,.13,.14,.09,material(0xd3b36d,'cheese'),[.58,.851,.03],'cheese');
  const bottleMat=material(0x263526,'glass',{metalness:.1,roughness:.25});cylinder(group,.055,.06,.22,bottleMat,[.91,.92,-.05],'wine bottle');cylinder(group,.022,.026,.13,bottleMat,[.91,1.09,-.05]);cylinder(group,.023,.023,.025,material(0x806042,'wood'),[.91,1.165,-.05],'cork');
  // Cupboard doors remain separately addressable for the theft shot.
  const cupboard=new THREE.Group();cupboard.position.set(2.7,0,-2.48);group.add(cupboard);box(cupboard,[1.25,1.9,.48],wood,[0,.95,0],'cupboard carcass');box(cupboard,[1.1,1.65,.03],material(0x211d18),[0,.94,.26],'cupboard dark recess');box(cupboard,[1.1,.035,.5],wood,[0,1.02,.05],'silver shelf');
  const cupboardDoors=[];for(const s of [-1,1]){const pivot=new THREE.Group();pivot.position.set(s*.59,0,.29);cupboard.add(pivot);box(pivot,[.56,1.75,.055],material(0x665039,'wood'),[-s*.28,.95,0],'cupboard door');sphere(pivot,.022,material(0x59482e,'metal',{metalness:.8}),[-s*.51,.95,.06]);cupboardDoors.push(pivot);}
  const moon=new THREE.SpotLight(0x9db4ff,45,12,.55,.5,2);moon.position.set(1.8,2.4,-3.65);moon.target.position.set(-.5,.6,.5);group.add(moon,moon.target);moon.castShadow=true;moon.shadow.mapSize.set(2048,2048);
  const fill=new THREE.HemisphereLight(0x9badd1,0x3c2b1c,.3);group.add(fill);
  // Motivated by the dining candles; the separately supplied silver kit owns the visible flames.
  const candleLight=new THREE.PointLight(0xffb36b,18,6,2);candleLight.position.set(0,1.14,0);candleLight.castShadow=true;candleLight.shadow.mapSize.set(2048,2048);group.add(candleLight);
  const update=(t=0,p=0)=>{const moonlit=opts.moonlit===true;candleLight.intensity=moonlit?0:18*(1+.045*Math.sin(t*8.71)+.025*Math.sin(t*17.31));hearthLight.intensity=(moonlit?1:9)*(1+.06*Math.sin(t*11.3));moon.intensity=moonlit?60:5;};update();
  return {group,update,look:{...suggestedLook(true),bg:0x17140f,fog:{color:0x28231b,density:.014},exposure:1.1},anchors:{candlestick1:new THREE.Vector3(-.28,.805,0),candlestick2:new THREE.Vector3(.28,.805,0),candlesticks:[new THREE.Vector3(-.28,.805,0),new THREE.Vector3(.28,.805,0)],placeSettings:settings,...Object.fromEntries(settings.map((v,i)=>[`placeSetting${i+1}`,v])),mantel:new THREE.Vector3(hearthX,1.31,-2.6),mantelLeft:new THREE.Vector3(hearthX-.4,1.31,-2.6),mantelRight:new THREE.Vector3(hearthX+.4,1.31,-2.6),cupboard:new THREE.Vector3(2.7,1.04,-2.25),basket:new THREE.Vector3(2.7,1.04,-2.25),window:win.position,table:new THREE.Vector3(0,.805,0)},parts:{cupboard,cupboardDoors,candleLight,moon,hearthLight,cheese}};
}
export function makeCellWall(opts={}) {
  const group=new THREE.Group();ground(group,8,0x494c48);windowWall(group,{barred:true,z:-.4});
  const iron=material(0x303638,'metal',{metalness:.85});const ring=mesh(group,new THREE.TorusGeometry(.09,.018,8,20),iron,[-1.5,1.8,-.16],'chain wall ring');ironChain(group,[-1.5,1.75,-.08],1.5);
  const marks=[];const scratch=material(0xc6c3ad,'stone',{bumpScale:.002});
  // 19 groups of five marks. Each stroke grows from zero as progress advances.
  for(let year=0;year<19;year++)for(let j=0;j<5;j++){const x=-1.15+(year%7)*.36+j*.052,y=1.72-Math.floor(year/7)*.33;const m=box(group,[j===4?.27:.009,.006,j===4?.008:.008],scratch,[x,y,-.228],'tally scratch');m.geometry.dispose();m.geometry=new THREE.BoxGeometry(j===4?.27:.009,j===4?.008:.18,.006);m.position.z=-.228;m.rotation.z=j===4?-.3:((year+j)%3-1)*.025;marks.push({mesh:m,x,y,diagonal:j===4});}
  const key=new THREE.SpotLight(0x9db4ff,100,14,.43,.3,2);key.position.set(1.8,2.6,-1.3);key.target.position.set(-.8,.2,2.8);key.castShadow=true;key.shadow.mapSize.set(2048,2048);group.add(key,key.target,new THREE.HemisphereLight(0x8190a9,0x242521,.28));
  const update=(t=0,p=0)=>{const count=clamp(p)*marks.length;marks.forEach(({mesh:m,y,diagonal},i)=>{const s=clamp(count-i);m.visible=s>0;m.scale.set(diagonal?s:1,diagonal?1:s,1);m.position.y=diagonal?y:y+.09*(1-s);});};update();
  return {group,update,look:suggestedLook(true),anchors:{tallies:new THREE.Vector3(0,1.3,-.22),window:new THREE.Vector3(1.8,2.05,-.4),chain:new THREE.Vector3(-1.5,1,-.08)},parts:{marks:marks.map(m=>m.mesh),ring}};
}
let passportMap;
function passportTexture(){
  if(passportMap)return passportMap;
  const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=768;const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Passport texture requires a canvas 2D context');
  ctx.fillStyle='#c5aa54';ctx.fillRect(0,0,1024,768);const random=seeded(1815);
  for(let i=0;i<16000;i++){ctx.fillStyle=`rgba(${random()>.5?'62,39,13':'255,231,154'},${.025+random()*.07})`;ctx.fillRect(random()*1024,random()*768,1+random()*4,1+random()*3);}
  ctx.strokeStyle='#766332';ctx.lineWidth=3;ctx.strokeRect(33,35,958,696);ctx.fillStyle='#4b3a1c';ctx.textAlign='center';ctx.font='32px Georgia, serif';ctx.fillText('ROYAUME DE FRANCE',512,100);ctx.font='bold 44px Georgia, serif';ctx.fillText('PASSEPORT',512,163);
  ctx.textAlign='left';ctx.font='italic 54px cursive';ctx.fillText('Jean Valjean',110,300);ctx.font='italic 43px cursive';ctx.fillText('forçat libéré',110,390);ctx.fillText('19 ans au bagne',110,480);ctx.font='italic 25px cursive';ctx.fillText('Délivré à Toulon, octobre 1815',110,565);
  ctx.save();ctx.translate(795,570);ctx.rotate(-.16);ctx.strokeStyle='rgba(136,31,24,.8)';ctx.fillStyle='rgba(136,31,24,.8)';ctx.lineWidth=7;ctx.beginPath();ctx.arc(0,0,95,0,Math.PI*2);ctx.stroke();ctx.lineWidth=2;ctx.beginPath();ctx.arc(0,0,79,0,Math.PI*2);ctx.stroke();ctx.textAlign='center';ctx.font='bold 23px Georgia';ctx.fillText('BAGNE',0,-13);ctx.fillText('TOULON',0,24);ctx.restore();
  passportMap=new THREE.CanvasTexture(canvas);passportMap.colorSpace=THREE.SRGBColorSpace;return passportMap;
}
export function makePassportTable(opts={}) {
  const group=new THREE.Group();ground(group,6,0x3f352a);table(group,1.6,1.05,.76);
  const geometry=new THREE.PlaneGeometry(.43,.32,32,24),positions=geometry.attributes.position;
  for(let i=0;i<positions.count;i++){const x=positions.getX(i),y=positions.getY(i);positions.setZ(i,.004*Math.sin(x*24+y*9)+.013*Math.pow(Math.abs(x)/.215,6));}geometry.computeVertexNormals();
  const paperMat=new THREE.MeshStandardMaterial({map:passportTexture(),roughness:.95,bumpMap:passportMap,bumpScale:.0007,side:THREE.DoubleSide});const paper=mesh(group,geometry,paperMat,[0,.772,.05],'yellow passport');paper.rotation.x=-Math.PI/2;paper.rotation.z=-.08;
  const brass=material(0x8b6d3e,'metal',{metalness:.8,roughness:.4});cylinder(group,.09,.12,.025,brass,[-.5,.78,-.22],'lamp base');cylinder(group,.065,.07,.09,brass,[-.5,.837,-.22],'oil reservoir');cylinder(group,.015,.02,.035,brass,[-.5,.9,-.22],'wick collar');
  const chimney=mesh(group,new THREE.LatheGeometry([[.035,0],[.045,.04],[.035,.12],[.03,.22]].map(([r,y])=>new THREE.Vector2(r,y)),24),new THREE.MeshPhysicalMaterial({color:0xe4d6bb,transparent:true,opacity:.2,roughness:.15,side:THREE.DoubleSide}),[-.5,.91,-.22],'lamp chimney');
  const flame=sphere(group,.015,new THREE.MeshBasicMaterial({color:0xffd48d}),[-.5,.95,-.22],'oil flame');flame.scale.set(.65,2.6,.65);const lamp=new THREE.PointLight(0xffb36b,13,5,2);lamp.position.set(-.5,1.02,-.22);lamp.castShadow=true;lamp.shadow.mapSize.set(2048,2048);group.add(lamp,new THREE.HemisphereLight(0x667385,0x322216,.2));
  const coinMat=material(0x93846a,'metal',{metalness:.9,roughness:.42});for(let i=0;i<5;i++){const coin=cylinder(group,.0135,.0135,.002,coinMat,[.34+(i%3)*.036,.764+Math.floor(i/3)*.002,-.1+(i%2)*.026],'coin');const rim=mesh(group,new THREE.TorusGeometry(.012,.0008,5,20),coinMat,coin.position.toArray());rim.rotation.x=Math.PI/2;rim.position.y+=.0015;}
  const update=(t=0,p=0)=>{lamp.intensity=13*(1+.055*Math.sin(t*8.71)+.025*Math.sin(t*17.31));flame.scale.y=2.6*(1+.05*Math.sin(t*11.1));};update();
  return {group,update,look:{bg:0x211a12,fog:{color:0x211a12,density:.035},exposure:1.12},anchors:{passport:new THREE.Vector3(0,.78,.05),lamp:lamp.position.clone(),table:new THREE.Vector3(0,.76,0)},parts:{paper,lamp,flame,chimney}};
}
