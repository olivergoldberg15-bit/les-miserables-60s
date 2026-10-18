import { THREE, TM, scene, composer, cl, seg, shotRange } from './core.js';
import { SHOTS, setRegistry } from './shots.js';
import { updateOverlay } from './overlay.js';
const registry={};
const empty=()=>({group:new THREE.Group()});
async function loadKit(path,names){let mod;try{mod=await import(path);}catch(error){console.warn(`Kit unavailable: ${path}`,error);}
for(const [key,name] of Object.entries(names)){try{registry[key]=mod?.[name]?await mod[name]():empty();if(!registry[key]?.group)throw new Error(`${name} returned no group`);}catch(error){console.warn(`Kit builder unavailable: ${path}/${name}`,error);registry[key]=empty();}scene.add(registry[key].group);}}
async function build(){await Promise.all([
loadKit('./kit/silver.js',{candlestick:'makeCandlestick',placeSetting:'makePlaceSetting',silverBasket:'makeSilverBasket',coin40Sous:'makeCoin40Sous'}),
loadKit('./kit/town.js',{townDusk:'makeTownDusk',nightStreet:'makeNightStreet',innDoor:'makeInnDoor',prisonDoor:'makePrisonDoor',kennel:'makeKennel',bishopDoor:'makeBishopDoor',bakeryWindow:'makeBakeryWindow'}),
loadKit('./kit/interior.js',{diningRoom:'makeDiningRoom',cellWall:'makeCellWall',passportTable:'makePassportTable'}),
loadKit('./kit/land.js',{gardenWall:'makeGardenWall',plain:'makePlain',crossroads:'makeCrossroads'})]);
try{const mod=await import('./kit/figure.js');const makers=await mod.loadFigures();for(const [key,name] of Object.entries({figure:'makeValjean',boy:'makeValjean',gendarme:'makeGendarme',guard2:'makeGendarme',guard3:'makeGendarme'})){try{registry[key]=makers[name]();scene.add(registry[key].group);}catch(error){console.warn(`Figure builder unavailable: ${name}`,error);registry[key]=empty();scene.add(registry[key].group);}}}catch(error){console.warn('Figure kit unavailable',error);for(const key of ['figure','boy','gendarme','guard2','guard3']){registry[key]=empty();scene.add(registry[key].group);}}
registry.boy.group.scale.setScalar(.55);registry.boy.group.traverse(o=>{if(/hat|brim/.test(o.name))o.visible=false;});
setRegistry(registry);
function renderAt(value){const t=cl(Number.isFinite(Number(value))?Number(value):0,0,TM.duration);const id=TM.lines.find(l=>{const [a,b]=shotRange(l.id);return t>=a&&t<b;})?.id??TM.lines.at(-1).id;const shot=SHOTS[id];const [a,b]=shotRange(id);const k=seg(t,a,b);for(const asset of Object.values(registry))asset.group.visible=false;for(const key of shot.sets){const asset=registry[key];if(asset){asset.group.visible=true;asset.update?.(t,k);}}shot.render(t,k);updateOverlay(t,id,shot);scene.userData.setGradeTime(t);composer.render(0);}
window.__lmRender=renderAt;window.addEventListener('hf-seek',e=>renderAt(e.detail.time));
await document.fonts.ready;
const params=new URLSearchParams(location.search);let t=Number(window.__hfThreeTime)||0;
if(params.has('shot')){const id=params.get('shot');if(SHOTS[id]){const [a,b]=shotRange(id);t=a+(b-a)*cl(Number(params.get('k')??.5));}else console.warn(`Unknown preview shot: ${id}`);}else if(params.has('t'))t=Number(params.get('t'));
renderAt(t);window.__lmReady?.();if(params.has('t')||params.has('shot'))document.title='ready';
}
build().catch(error=>{console.error('Les Misérables build failed',error);});
