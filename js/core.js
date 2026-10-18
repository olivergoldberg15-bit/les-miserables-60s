import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
export { THREE };
export const W=1920,H=1080,FPS=30;
export const TM=window.TIMING;
export const cl=(v,a=0,b=1)=>Math.min(b,Math.max(a,v));
export const seg=(t,a,b)=>b===a?(t>=b?1:0):cl((t-a)/(b-a));
export const lerp=(a,b,k)=>a+(b-a)*k;
export const eio=k=>{k=cl(k);return k*k*(3-2*k);};
export const eo=k=>1-(1-cl(k))**3;
export const smooth=(a,b,t)=>eio(seg(t,a,b));
export const win=(t,a,b,fade=.4)=>seg(t,a,a+fade)*(1-seg(t,b-fade,b));
export const rng=(seed=1)=>()=>{let t=seed+=0x6D2B79F5;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return ((t^t>>>14)>>>0)/4294967296;};
const line=id=>{const l=TM.lines.find(l=>l.id===id);if(!l)throw new Error(`Unknown line: ${id}`);return l;};
const norm=w=>w.toLocaleLowerCase('en').replace(/[^\p{L}\p{N}]/gu,'');
export function cue(id,word,nth=1){const found=line(id).words.filter(w=>norm(w.w)===norm(word))[nth-1];if(!found)throw new Error(`Missing cue: ${id}/${word}/${nth}`);return found.s;}
export const lineStart=id=>line(id).start;
export const lineEnd=id=>line(id).end;
export function shotRange(id){const i=TM.lines.findIndex(l=>l.id===id);if(i<0)throw new Error(`Unknown shot: ${id}`);return [i?(TM.lines[i-1].end+TM.lines[i].start)/2:0,i<TM.lines.length-1?(TM.lines[i].end+TM.lines[i+1].start)/2:TM.duration];}
export const renderer=new THREE.WebGLRenderer({canvas:document.getElementById('gl'),antialias:true});
renderer.setPixelRatio(1);renderer.setSize(W,H,false);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
export const scene=new THREE.Scene();
export const camera=new THREE.PerspectiveCamera(35,W/H,.05,300);
const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment();
scene.environment=pmrem.fromScene(room,.04).texture;room.dispose();pmrem.dispose();
export const composer=new EffectComposer(renderer);
composer.addPass(new RenderPass(scene,camera));
const bloomPass=new UnrealBloomPass(new THREE.Vector2(W,H),.16,.35,1.2);composer.addPass(bloomPass);
const grade=new ShaderPass({uniforms:{tDiffuse:{value:null},time:{value:0},grain:{value:.012},vignette:{value:.24}},vertexShader:'varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',fragmentShader:`uniform sampler2D tDiffuse;uniform float time,grain,vignette;varying vec2 vUv;
void main(){vec4 c=texture2D(tDiffuse,vUv);vec2 p=vUv*2.-1.;float falloff=smoothstep(.15,1.5,dot(p,p));float n=fract(sin(dot(floor(vUv*vec2(1920.,1080.)),vec2(12.9898,78.233))+floor(time*30.)*37.719)*43758.5453)-.5;c.rgb*=1.-vignette*falloff;c.rgb+=n*grain;gl_FragColor=vec4(max(c.rgb,vec3(0.)),c.a);}`});composer.addPass(grade);composer.addPass(new OutputPass());
// Grade time is set by the deterministic dispatcher, without expanding the public exports.
scene.userData.setGradeTime=t=>{grade.uniforms.time.value=t;};
export function setCam(pos,target,fovDeg=35){camera.position.fromArray(pos.isVector3?pos.toArray():pos);camera.fov=fovDeg;camera.updateProjectionMatrix();camera.lookAt(target.isVector3?target:new THREE.Vector3(...target));}
export function setLook({bg=0x18202b,fog={color:bg,density:.025},exposure=1,bloom=.16,grain=.012,vignette=.24}={}){scene.background=new THREE.Color(bg);scene.fog=fog===null?null:new THREE.FogExp2(fog.color??bg,fog.density??.025);renderer.toneMappingExposure=exposure;if(typeof bloom==='number')bloomPass.strength=bloom;else Object.assign(bloomPass,bloom);grade.uniforms.grain.value=grain;grade.uniforms.vignette.value=vignette;}
export const flicker=(t,seed=0)=>1+.075*Math.sin(t*8.71+seed)+.045*Math.sin(t*17.31+seed*2)+.03*Math.sin(t*31.7+seed*3);
