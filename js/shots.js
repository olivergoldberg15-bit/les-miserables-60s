import { THREE, scene, setCam, setLook, cue, lerp, eio } from './core.js';
// Temporary, deliberately simple lit staging. The shots step replaces this module.
const placeholder=new THREE.Group();placeholder.name='placeholder';
const floor=new THREE.Mesh(new THREE.PlaneGeometry(30,30),new THREE.MeshStandardMaterial({color:0x50473d,roughness:.95}));floor.rotation.x=-Math.PI/2;floor.receiveShadow=true;placeholder.add(floor);
const stone=new THREE.Mesh(new THREE.BoxGeometry(.8,1.4,.7),new THREE.MeshStandardMaterial({color:0x928775,roughness:.75}));stone.position.y=.7;stone.castShadow=true;placeholder.add(stone);
const key=new THREE.DirectionalLight(0xffb36b,3);key.position.set(-3,5,2);key.castShadow=true;key.shadow.mapSize.set(2048,2048);placeholder.add(key,new THREE.HemisphereLight(0x9db4ff,0x4c3020,1));scene.add(placeholder);
const item=(id,word,text,italic=false)=>({at:cue(id,word),text,italic});
const spec={
open:['VOL. I · BOOK 2 · CH. I',[item('open','October','Digne · October 1815')]],
bread:['CH. VI · 1796',[item('bread','Jean','1796'),item('bread','seven','7 children')]],
years:['CH. VI',[item('years','Five','5 years'),...['+3','+5','+3','+3'].map((text,i)=>({at:lerp(cue('years','Four'),cue('years','nineteen'),i/4),text})),item('years','nineteen','= 19 years')]],
passport:['CH. III · IX',[item('passport','convict','109 francs 15 sous for 19 years of work')]],
rejected:['CH. I',['Inns','prison','kennel'].map((word,i,words)=>({...item('rejected',word,`Turned away: ${i+1}`),until:i<2?cue('rejected',words[i+1]):Infinity}))],
door:['CH. III',[]],dinner:['CH. III',[item('dinner','sir','Monsieur')]],steal:['CH. XI',[]],caught:['CH. XII',[]],gift:['CH. XII',[item('gift','candlesticks','≈ 200 francs')]],
soul:['CH. XII',[item('soul','You','You no longer belong to evil, but to good.',true)]],coin:['CH. XIII',[item('coin','coin','40 sous = 2 francs')]],weep:['CH. XIII',[item('weep','nineteen','First tears in 19 years')]],end:['VOL. I · BOOK 2',[]]
};
export const SHOTS=Object.fromEntries(Object.entries(spec).map(([id,[tag,callouts]],i)=>[id,{sets:['placeholder'],tag,callouts,render(t,k){placeholder.visible=true;stone.rotation.set(0,i*.13,0);setCam([lerp(3,2.8,eio(k)),2,lerp(6,5.5,eio(k))],[0,.7,0],35);setLook({bg:i===13?0x10141b:0x25303d,exposure:.95});}}]));
// A registry bridge keeps main.js compatible with the eventual real shot module.
export function setRegistry(registry){registry.placeholder={group:placeholder};}
