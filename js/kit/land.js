import * as THREE from 'three';
import { Sky } from 'three/addons/objects/Sky.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

// Shared deterministic construction helpers; no renderer or scene ownership.
export const clamp = p => Math.max(0, Math.min(1, Number.isFinite(p) ? p : 0));
export function seeded(seed = 1) {
  return () => { let t = seed += 0x6D2B79F5; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
const textures = new Map();
// Smooth seeded value noise: material detail remains stable at every seek.
export function noise(x,y,seed=0) {
  const hash=(a,b)=>{let n=Math.imul(a+seed,374761393)^Math.imul(b,668265263);n=Math.imul(n^(n>>>13),1274126177);return ((n^(n>>>16))>>>0)/4294967295;};
  const ix=Math.floor(x),iy=Math.floor(y),u=x-ix,v=y-iy, sx=u*u*(3-2*u),sy=v*v*(3-2*v);
  return THREE.MathUtils.lerp(THREE.MathUtils.lerp(hash(ix,iy),hash(ix+1,iy),sx),THREE.MathUtils.lerp(hash(ix,iy+1),hash(ix+1,iy+1),sx),sy);
}
export function fbm(x,y,seed=0) {let n=0,a=.5;for(let i=0;i<5;i++){n+=a*noise(x,y,seed+i*17);x*=2.03;y*=2.03;a*=.5;}return n;}
function surface(kind) {
  if(textures.has(kind))return textures.get(kind);
  const n=256, heights=new Float32Array(n*n), albedo=new Uint8Array(n*n*4),normal=new Uint8Array(n*n*4),rough=new Uint8Array(n*n*4);
  for(let y=0;y<n;y++)for(let x=0;x<n;x++){
    let h=fbm(x/28,y/28,83),v=.52+h*.45;
    if(kind==='wood'){h=.5+.2*Math.sin(x*.55+fbm(x/90,y/110)*12)+.13*Math.sin(x*2.6+Math.sin(y*.045));v=.5+h*.4;}
    if(kind==='stone'){const row=Math.floor(y/112),offset=noise(row,0,31)*130,xx=(x+offset)%144,yy=y%112;const seam=xx<5||yy<5;h=seam?.04:.35+fbm(x/17,y/17,92)*.42;v=seam?.3:.42+noise(Math.floor((x+offset)/144),row,44)*.35+h*.18;}
    if(kind==='cobble'){const row=Math.floor(y/43),xx=(x+(row%2)*31+8*Math.sin(row*8))%64,yy=y%43;h*=.4;if(xx<4||yy<4){h=.04;v=.30;}else{h+=.4;v=.56+h*.28;}}
    if(kind==='tile'){h=.4+.3*Math.sin((x%32)/32*Math.PI);if(y%48<3)h=.1;v=.5+h*.4;}
    if(kind==='cloth'){h=.45+.12*Math.sin(x*Math.PI)+.12*Math.cos(y*Math.PI);v=.8+fbm(x/10,y/10)*.15;}
    if(kind==='plaster')v-=.18*Math.pow(noise(x/42,y/60,99),3);
    if(kind==='bread'){h+=.12*Math.sin(x*3+y*4);v=.35+h*.5;}
    heights[y*n+x]=h;
    const k=(y*n+x)*4,c=Math.min(255,255*v);albedo.set([c,c*.98,c*.94,255],k);
    const r=kind==='cobble'?75+h*125:145+h*100;rough.set([r,r,r,255],k);
  }
  for(let y=0;y<n;y++)for(let x=0;x<n;x++){const dx=heights[y*n+(x+1)%n]-heights[y*n+(x+n-1)%n],dy=heights[((y+1)%n)*n+x]-heights[((y+n-1)%n)*n+x],v=new THREE.Vector3(-dx*3,-dy*3,1).normalize();normal.set([128+v.x*127,128+v.y*127,128+v.z*127,255],(y*n+x)*4);}
  const create=(data,color=false)=>{const tex=new THREE.DataTexture(data,n,n);tex.wrapS=tex.wrapT=THREE.RepeatWrapping;tex.magFilter=THREE.LinearFilter;tex.minFilter=THREE.LinearMipmapLinearFilter;tex.generateMipmaps=true;tex.colorSpace=color?THREE.SRGBColorSpace:THREE.NoColorSpace;tex.needsUpdate=true;return tex;};
  const maps={map:create(albedo,true),normalMap:create(normal),roughnessMap:create(rough)};textures.set(kind,maps);return maps;
}
export function material(color,kind='plaster',extra={}) {const mat=new THREE.MeshStandardMaterial({color,...surface(kind),normalScale:new THREE.Vector2(.55,.55),roughness:.95,...extra});mat.userData.surface=kind;return mat;}
// Geometry-scale UVs keep grain and pores from stretching across entire walls.
export function mesh(parent, geometry, mat, position = [0, 0, 0], name = '') {
  const m = new THREE.Mesh(geometry, mat); m.position.set(...position); m.castShadow = m.receiveShadow = true; m.name = name; parent.add(m); return m;
}
export const box = (g,size,m,p,name) => {const geo=new THREE.BoxGeometry(...size),uv=geo.attributes.uv;for(let i=0;i<uv.count;i++){const face=Math.floor(i/4);uv.setXY(i,uv.getX(i)*(face<2?size[2]:size[0])*2,uv.getY(i)*(face===2||face===3?size[2]:size[1])*2);}return mesh(g,geo,m,p,name);};
export function rubble(g,width,height,depth,position=[0,0,0],color=0x928b79) {
  box(g,[width,height,depth],material(0x605b50,'plaster'),position,'mortar core');const random=seeded(273+Math.round(width*100)),geo=new RoundedBoxGeometry(1,1,1,1,.075),mat=material(color,'stone');
  const placements=[];let y=0;while(y<height-.04){const h=Math.min(height-y,.38+random()*.34);let x=-width/2;while(x<width/2-.02){const w=Math.min(width/2-x,.55+random()*.85);placements.push({x:x+w/2,y:y+h/2,w:w-.025,h:h-.022});x+=w;}y+=h;}
  const stones=new THREE.InstancedMesh(geo,mat,placements.length),o=new THREE.Object3D();placements.forEach((v,i)=>{o.position.set(position[0]+v.x,position[1]-height/2+v.y,position[2]+depth*.12);o.rotation.set(0,(random()-.5)*.06,(random()-.5)*.06);o.scale.set(v.w,v.h,depth);o.updateMatrix();stones.setMatrixAt(i,o.matrix);stones.setColorAt(i,new THREE.Color().setScalar(.55+random()*.65));});stones.castShadow=stones.receiveShadow=true;g.add(stones);return stones;
}
export const sphere = (g, r, m, p, name) => mesh(g, new THREE.SphereGeometry(r, 16, 10), m, p, name);
export function cylinder(g, r1, r2, h, mat, p, name) { return mesh(g, new THREE.CylinderGeometry(r1, r2, h, 16), mat, p, name); }
export function terrainHeight(x,z){return (fbm(x*.35,z*.35,149)-.48)*.15;}
export function ground(g,size=40,color=0x63533f){const geo=new THREE.PlaneGeometry(size,size,96,96);geo.rotateX(-Math.PI/2);const p=geo.attributes.position,uv=geo.attributes.uv;for(let i=0;i<p.count;i++){p.setY(i,terrainHeight(p.getX(i),p.getZ(i))-.07);uv.setXY(i,p.getX(i)/2,p.getZ(i)/2);}geo.computeVertexNormals();return mesh(g,geo,material(color,'earth'),[0,0,0],'undulating gravel ground');}
export function lightRig(g, { night = false, sunset = false, key = 2 } = {}) {
  const sun = new THREE.DirectionalLight(night ? 0x9db4ff : sunset ? 0xff9a55 : 0xffd9a8, key);
  sun.position.set(-45, night ? 45 : sunset ? 1.3 : 25, -60); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -24, right: 24, top: 24, bottom: -24, near: .5, far: 100 }); sun.shadow.bias = -.0002; sun.shadow.normalBias = .03;
  g.add(sun, sun.target, new THREE.HemisphereLight(night ? 0x647bad : 0xa0a9ba, 0x39291c, night ? .28 : .65)); return sun;
}
export function suggestedLook(night = false) { const bg = night ? 0x111c30 : 0x66667a; return { bg, fog: { color: bg, density: night ? .018 : .009 }, exposure: night ? .95 : .78 }; }
export function makeSky(opts={}) {
  const group=new THREE.Group(),night=!!opts.night,sky=new Sky();sky.scale.setScalar(140);sky.name='Preetham atmosphere';const u=sky.material.uniforms;
  u.turbidity.value=7;u.rayleigh.value=night?.6:2.8;u.mieCoefficient.value=.006;u.mieDirectionalG.value=.82;u.sunPosition.value.set(-80,night?-35:1,-100);
  // The atmosphere supplies scattering; warm horizon grades continuously to a blue zenith.
  if(!night){sky.material.fragmentShader=sky.material.fragmentShader.replace('gl_FragColor = vec4( retColor, 1.0 );','float altitude = clamp(normalize(vWorldPosition).y, 0.0, 1.0); vec3 horizon = vec3(0.56,0.22,0.075); vec3 zenith = vec3(0.025,0.055,0.13); gl_FragColor = vec4(mix(horizon,zenith,pow(altitude,0.42)) + min(retColor,vec3(1.0))*0.045,1.0);');}
  if(night){sky.material.fragmentShader=sky.material.fragmentShader.replace('gl_FragColor = vec4( retColor, 1.0 );','gl_FragColor = vec4( retColor * vec3(0.08, 0.13, 0.26) + vec3(0.006,0.012,0.028), 1.0 );');}
  group.add(sky);
  const orb=sphere(group,night?1.4:1.8,new THREE.MeshBasicMaterial({color:night?0xd5dfed:0xffc28a}),opts.position??[-80,night?38:1,-100],night?'moon':'sun');orb.castShadow=orb.receiveShadow=false;
  const cloud=new THREE.Mesh(new THREE.SphereGeometry(130,32,16),new THREE.ShaderMaterial({side:THREE.BackSide,transparent:true,depthWrite:false,uniforms:{tint:{value:new THREE.Color(night?0x3a4963:0xc49d8c)}},vertexShader:'varying vec3 v;void main(){v=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',fragmentShader:`varying vec3 v;uniform vec3 tint;float h(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}float n(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(h(i),h(i+vec2(1,0)),f.x),mix(h(i+vec2(0,1)),h(i+vec2(1,1)),f.x),f.y);}void main(){vec3 d=normalize(v);vec2 p=d.xz/max(.13,d.y)*1.8;float f=0.;float a=.5;for(int i=0;i<5;i++){f+=n(p)*a;p*=2.1;a*=.5;}float alpha=smoothstep(.48,.78,f)*smoothstep(0.,.25,d.y)*.45;gl_FragColor=vec4(tint,alpha);}` }));cloud.castShadow=cloud.receiveShadow=false;cloud.name='soft procedural cirrus';group.add(cloud);
  return {group,anchors:{orb:orb.position.clone()},look:suggestedLook(night)};
}
export const makeMoonSky=(opts={})=>makeSky({...opts,night:true});
export const makeSunsetSky=(opts={})=>makeSky({...opts,night:false});
export function mountains(g){
  for(let layer=0;layer<3;layer++){
    const geo=new THREE.PlaneGeometry(220,48,256,80);geo.rotateX(-Math.PI/2);const p=geo.attributes.position;
    for(let i=0;i<p.count;i++){const x=p.getX(i),z=p.getZ(i),ridge=1-Math.abs(2*fbm(x*.023,z*.023,74+layer*30)-1);const envelope=Math.pow(Math.max(0,Math.sin(Math.PI*(z+24)/48)),.7);p.setY(i,-2+envelope*(7+Math.pow(ridge,2)*24+fbm(x*.17,z*.17,layer)*4));}
    geo.computeVertexNormals();const m=mesh(g,geo,material([0x535d68,0x727e8e,0x919bab][layer],'stone',{normalScale:new THREE.Vector2(.25,.25),roughness:1}),[0,0,-58-layer*25],'eroded Alpine heightfield');m.castShadow=false;
  }
}
function path(g,angle,length=38,width=2.1){
  const geo=new THREE.PlaneGeometry(width,length,24,128);geo.rotateX(-Math.PI/2);const p=geo.attributes.position,uv=geo.attributes.uv;
  for(let i=0;i<p.count;i++){const x=p.getX(i),z=p.getZ(i)+length/2,wx=x*Math.cos(angle)+z*Math.sin(angle),wz=z*Math.cos(angle)-x*Math.sin(angle);const rut=-.035*Math.exp(-Math.pow((Math.abs(x)-width*.3)/.14,2));p.setXYZ(i,wx,terrainHeight(wx,wz)-.045+rut,wz);uv.setXY(i,x,z/2);}geo.computeVertexNormals();return mesh(g,geo,material(0x92785a,'earth'),[0,0,0],'rutted dirt track');
}
function leafTexture(){if(textures.has('leaf'))return textures.get('leaf');const n=64,data=new Uint8Array(n*n*4);for(let y=0;y<n;y++)for(let x=0;x<n;x++){const u=(x-32)/32,v=y/64,w=Math.sin(v*Math.PI)*.65;data.set([135,155,105,Math.abs(u)<w?255:0],(y*n+x)*4);}const tex=new THREE.DataTexture(data,n,n);tex.needsUpdate=true;textures.set('leaf',tex);return tex;}
export function vegetation(g,count=900,extent=42,bed=false){const random=seeded(493),mat=material(bed?0x536844:0x81724b,'earth',{...(bed?{alphaMap:leafTexture(),alphaTest:.4}:{}),side:THREE.DoubleSide}),geo=new THREE.PlaneGeometry(.12,.55,1,3),p=geo.attributes.position;for(let i=0;i<p.count;i++)p.setZ(i,Math.pow((p.getY(i)+.275)/.55,2)*.13);geo.translate(0,.275,0);geo.computeVertexNormals();if(!bed){for(let i=0;i<p.count;i++){const f=(p.getY(i))/.55;p.setX(i,p.getX(i)*.24*Math.max(.015,1-f));}geo.computeVertexNormals();}
  const bladeCount=bed?count:count*8,leaves=new THREE.InstancedMesh(geo,mat,bladeCount),o=new THREE.Object3D();let cx=0,cz=0;for(let i=0;i<bladeCount;i++){if(i%8===0){cx=(random()-.5)*extent;cz=(random()-.5)*extent;}const x=bed?(random()-.5)*extent:cx+(random()-.5)*.18,z=bed?random()*1.4-.3:cz+(random()-.5)*.18;o.position.set(x,terrainHeight(x,z)-.05,z);o.rotation.set((random()-.5)*.6,random()*Math.PI*2,(random()-.5)*.5);o.scale.setScalar(.45+random()*(bed?1.5:1));if(!bed&&Math.abs(x)<.7)o.scale.setScalar(.2);o.updateMatrix();leaves.setMatrixAt(i,o.matrix);leaves.setColorAt(i,new THREE.Color().setHSL(.12+random()*.1,.18+random()*.2,.45+random()*.2));}leaves.castShadow=leaves.receiveShadow=true;g.add(leaves);
  if(!bed){const stones=new THREE.InstancedMesh(new THREE.IcosahedronGeometry(.07,1),material(0x8b8170,'stone'),180);for(let i=0;i<180;i++){const x=(random()-.5)*extent,z=(random()-.5)*extent;o.position.set(x,terrainHeight(x,z)-.035,z);o.scale.set(.3+random(),.3+random()*.5,.4+random());o.rotation.set(random(),random(),random());o.updateMatrix();stones.setMatrixAt(i,o.matrix);}stones.castShadow=stones.receiveShadow=true;g.add(stones);}
}
function brush(g,count=110){vegetation(g,count*12);const random=seeded(384),mat=material(0x756247,'wood');for(let i=0;i<count;i++){const x=(random()-.5)*42,z=(random()-.5)*42;if(Math.abs(x)<1.3)continue;for(let j=0;j<3;j++){const twig=cylinder(g,.004,.012,.25+random()*.3,mat,[x+j*.07,.13,z]);twig.rotation.z=(random()-.5)*1.9;twig.rotation.x=(random()-.5);}}}
export function makePlain(opts = {}) {
  const group = new THREE.Group(); group.name = 'sunset plain'; ground(group, 100, 0x766149); path(group, 0, 55); brush(group); mountains(group); group.add(makeSunsetSky().group); lightRig(group, { sunset: true, key: 2.8 });
  return { group, look: suggestedLook(), anchors: { coin: new THREE.Vector3(0, .04, 0), boy: new THREE.Vector3(1, 0, -14), path: new THREE.Vector3(0, 0, -8) } };
}
export function makeCrossroads(opts = {}) {
  const group = new THREE.Group(); ground(group, 100, 0x524f45); [0, 2.12, 4.2].forEach(a => path(group, a)); brush(group, 85); mountains(group); group.add(makeMoonSky().group); lightRig(group, { night: true, key: 1.6 });
  const stone = mesh(group, new THREE.IcosahedronGeometry(1, 5), material(0x878b70, 'stone'), [1.9, .46, .4], 'weeping stone'); const bp=stone.geometry.attributes.position;for(let i=0;i<bp.count;i++){const x=bp.getX(i),y=bp.getY(i),z=bp.getZ(i),f=.64+fbm(x*3+z,y*3,219)*.62+.1*Math.sin(x*9+z*5);bp.setXYZ(i,x*f,y*f,z*f);}stone.geometry.computeVertexNormals();stone.scale.set(1.15, .65, .9); stone.rotation.set(.1, .35, .1);
  return { group, look: suggestedLook(true), anchors: { stone: new THREE.Vector3(1.9, .95, .4), figure: new THREE.Vector3(1.9, 0, 1.1) } };
}
export function makeGardenWall(opts = {}) {
  const group = new THREE.Group(); ground(group, 24, 0x3b4030); const stone = material(0x8e8b7b, 'stone');
  rubble(group,12,1.65,.48,[0,.825,-1]); box(group, [12.2, .16, .65], material(0xaaa392, 'stone'), [0, 1.73, -1], 'coping');
  box(group, [7, .16, 1.8], material(0x342a21, 'earth'), [0, .035, .3], 'flower bed');
  vegetation(group,650,6.8,true);
  // Small five-petal corollas are cupped cards, never sphere-on-stick flowers.
  const petals=new THREE.InstancedMesh(new THREE.PlaneGeometry(.045,.075),material(0xb0a7b6,'cloth',{side:THREE.DoubleSide}),250),random=seeded(129),o=new THREE.Object3D();
  for(let i=0;i<50;i++){const x=(random()-.5)*6.5,z=random()*1.4-.3,h=.25+random()*.25;for(let j=0;j<5;j++){const a=j*Math.PI*2/5;o.position.set(x+Math.cos(a)*.027,h,z+Math.sin(a)*.027);o.rotation.set(-Math.PI/2+.35*Math.sin(a),0,a);o.scale.setScalar(.6+random()*.4);o.updateMatrix();petals.setMatrixAt(i*5+j,o.matrix);}}petals.castShadow=true;group.add(petals);
  group.add(makeMoonSky().group); lightRig(group, { night: true, key: 1.8 });
  return { group, look: suggestedLook(true), anchors: { wallTop: new THREE.Vector3(0, 1.81, -1), flowerBed: new THREE.Vector3(0, .2, .3), basket: new THREE.Vector3(-.7, .2, .3) } };
}
