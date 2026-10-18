import { scene, setCam, setLook, cue, shotRange, lineEnd, seg, lerp, eio } from './core.js';
import { makeCandlestick, makePlaceSetting } from './kit/silver.js';
let R;
const item=(id,word,text,italic=false)=>({at:cue(id,word),text,italic});
const escapes=Array.from({length:4},(_,i)=>lerp(cue('years','Four'),cue('years','nineteen'),i/4));
const spec={
open:['VOL. I · BOOK 2 · CH. I',[item('open','October','Digne · October 1815')]],
bread:['CH. VI · 1796',[item('bread','Jean','1796'),item('bread','seven','7 children')]],
years:['CH. VI',[{...item('years','Five','5 years'),until:escapes[0]},...['+3','+3 +5','+3 +5 +3','+3 +5 +3 +3'].map((text,i)=>({at:escapes[i],until:escapes[i+1]??cue('years','nineteen'),text})),item('years','nineteen','= 19 years')]],
passport:['CH. III · IX',[item('passport','convict','109 francs 15 sous for 19 years of work')]],
rejected:['CH. I',['Inns','prison','kennel'].map((w,i,ws)=>({...item('rejected',w,`Turned away: ${i+1}`),until:i<2?cue('rejected',ws[i+1]):Infinity}))],
door:['CH. III',[]],dinner:['CH. III',[item('dinner','sir','Monsieur')]],steal:['CH. XI',[]],caught:['CH. XII',[]],gift:['CH. XII',[item('gift','candlesticks','≈ 200 francs')]],
soul:['CH. XII',[item('soul','You','You no longer belong to evil, but to good.',true)]],coin:['CH. XIII',[item('coin','coin','40 sous = 2 francs')]],weep:['CH. XIII',[item('weep','nineteen','First tears in 19 years')]],end:['VOL. I · BOOK 2',[]]
};
const group=key=>R[key].group;
const progress=(t,id,word,end=lineEnd(id))=>eio(seg(t,cue(id,word),end));
function look(key,extra={}){if(key==='diningRoom'){R.diningRoom.parts.cupboardDoors.forEach(d=>d.rotation.y=0);}setLook({...R[key].look,grain:.009,vignette:.22,bloom:.11,...extra});}
function cam(a,b,target,k,fov=35){setCam(a.map((v,i)=>lerp(v,b[i],eio(k))),target,fov);}
function actor(key,pos,pose='stand',phase=0,rotation=Math.PI){const a=R[key];a.group.traverse(o=>{if(o.name==='knapsack')o.scale.setScalar(.6);});a.group.position.set(...pos);a.group.rotation.set(0,rotation,0);a.pose(pose,phase);}
function candles(t,positions,lit=1){['candlestick','candle2'].forEach((key,i)=>{group(key).position.copy(positions[i]);group(key).rotation.set(0,0,0);R[key].update(t,lit);});}
function tableCandles(t,lit=1,lift=0){const ps=R.diningRoom.anchors.candlesticks.map(p=>p.clone());ps.forEach(p=>p.y+=lift);candles(t,ps,lit);}
const renderers={
open(t,k){look('townDusk',{exposure:.78});actor('figure',[0,0,lerp(20,8,eio(k))],'walk',k*4);cam([0,14,34],[0,2.8,30],[0,4,-16],k,38);},
bread(t,k){look('bakeryWindow');R.bakeryWindow.update(t,progress(t,'bread','stole',cue('bread','bread')));R.bakeryWindow.parts.loaf.scale.set(.58,.36,.42);cam([.65,1.45,3.2],[.45,1.25,1.9],[.25,1.25,0],k,32);},
years(t,k){
  look('cellWall');
  const stages=[{at:cue('years','Five'),count:5},{at:escapes[0],count:8},{at:escapes[1],count:13},{at:escapes[2],count:16},{at:cue('years','nineteen'),count:19}];
  const i=stages.findLastIndex(s=>t>=s.at),stage=stages[i];
  const count=stage?lerp(stages[i-1]?.count??0,stage.count,seg(t,stage.at,lerp(stage.at,stages[i+1]?.at??lineEnd('years'),.2))):0;
  R.cellWall.update(t,count/19);
  cam([-1.4,1.35,3.8],[.6,1.35,3.8],[0,1.35,-.2],k,38);
},
passport(t,k){look('passportTable');const a=lerp(-.16,.1,eio(k)),r=lerp(.14,.09,eio(k));setCam([Math.sin(a)*r,lerp(1.8,1.57,eio(k)),.05+Math.cos(a)*r],[0,.772,.05],36);},
rejected(t,k){const n=t<cue('rejected','prison')?0:t<cue('rejected','kennel')?1:2;const keys=['innDoor','prisonDoor','kennel'];keys.forEach((key,i)=>group(key).visible=i===n);const key=keys[n],word=['Inns','prison','kennel'][n],end=n<2?cue('rejected',['prison','kennel'][n]):lineEnd('rejected');look('nightStreet');const p=progress(t,'rejected',word,lerp(cue('rejected',word),end,.35));R[key].update?.(t,p);actor('figure',[1.05,0,n===2?lerp(1.4,2.3,p):1.4],'stand',0,-Math.PI*.65);setCam(n===2?[2.9,1.05,4.2]:[2.6,1.7,4.8],n===2?[0,.45,.3]:[0,1.15,0],38);},
door(t,k){look('bishopDoor');const knock=progress(t,'door','knocks',cue('door','door'));R.bishopDoor.update(t,progress(t,'door','door',shotRange('door')[1]));actor('figure',[.3,0,1.05],'knock',knock,Math.PI);cam([2.2,.85,3.5],[1.9,.85,3.2],[0,1.2,.2],k,38);},
dinner(t,k){look('diningRoom',{exposure:.88});const p=progress(t,'dinner','lights',cue('dinner','silver'));tableCandles(t,p,.12*(1-p));R.diningRoom.parts.candleLight.intensity*=p;cam([1.2,1.25,1.4],[.48,1.02,.94],[0,.93,0],k,30);},
steal(t,k){const garden=t>=cue('steal','jumps');group('diningRoom').visible=!garden;group('gardenWall').visible=garden;look(garden?'gardenWall':'diningRoom',{exposure:garden?.65:.68});const basket=group('silverBasket');basket.rotation.set(0,0,0);R.silverBasket.update(t,{empty:garden});if(!garden){const p=progress(t,'steal','silver',cue('steal','jumps'));basket.position.copy(R.diningRoom.anchors.basket);basket.position.y+=p*1.4;R.diningRoom.parts.candleLight.intensity=0;R.diningRoom.parts.hearthLight.intensity=.5;R.diningRoom.parts.moon.intensity=60;R.diningRoom.parts.cupboardDoors.forEach((d,i)=>d.rotation.y=(i?1:-1)*1.4);group('figure').visible=false;cam([2,1.6,.9],[2.2,1.6,.3],[2.7,1.25,-2.1],k,34);}else{const p=progress(t,'steal','jumps',cue('steal','wall'));basket.position.copy(R.gardenWall.anchors.basket);basket.position.y+=1.3*(1-p);basket.rotation.z=p*.45;actor('figure',[0,.3,-.1],'vault',p,Math.PI);setCam([5,3.4,7],[0,1,-1],38);}},
caught(t,k){look('bishopDoor',{bg:0x605b50,exposure:.9});R.bishopDoor.update(t,1);actor('figure',[0,0,1.1],'held');[-1,1,0].forEach((x,i)=>actor(['gendarme','guard2','guard3'][i],[x*.65,0,i===2?.2:1.05],'stand',0,Math.PI));cam([2.5,1.4,6],[2.1,1.4,5],[0,1.1,.8],k,36);},
gift(t,k){look('diningRoom',{exposure:.82});const p=progress(t,'gift','candlesticks',lineEnd('gift'));const a=R.diningRoom.anchors;const ps=[a.mantelLeft,a.mantelRight].map((v,i)=>v.clone().lerp(v.clone().set(-1.65+(i?1:-1)*.15,1.43,-1.85),p));candles(t,ps,1);cam([-1.65,1.59,-1.55],[-1.65,1.68,-.8],[-1.65,1.55,lerp(-2.6,-1.85,p)],k,32);},
soul(t,k){setLook({bg:0x0c0703,fog:null,exposure:lerp(.7,1.05,eio(k)),bloom:.16,grain:.009,vignette:.28});group('diningRoom').visible=false;group('candle2').visible=false;candles(t,R.diningRoom.anchors.candlesticks,1);const p=group('candlestick').position;cam([p.x+.018,p.y+.294,.16],[p.x+.012,p.y+.299,.13],[p.x,p.y+.297,0],k,28);},
coin(t,k){look('plain',{exposure:.7,fog:{color:0x88705a,density:.09}});const a=shotRange('coin')[0],step=cue('coin','steps'),stop=cue('coin','coin');const p=eio(seg(t,a,step)),down=eio(seg(t,step,stop));const c=group('coin40Sous');c.position.set(lerp(-.16,0,p),lerp(.014,.002,down),0);c.rotation.set(lerp(Math.PI/2,0,down),0,(1-p)*Math.PI*4);actor('figure',[.04,lerp(.25,0,down),-.11],'stand',0,Math.PI);actor('boy',R.plain.anchors.boy.toArray(),'stand',0,Math.PI);setCam([.09,.07,.31],[0,.026,-.02],32);},
weep(t,k){look('crossroads',{exposure:.72});const p=progress(t,'weep','breaks',cue('weep','weeps'));actor('figure',[1.9,.48,1.1],'kneel_collapse',p,0);R.crossroads.group.traverse(o=>{if(o.name==='moon')o.position.set(-6,6,-18);});cam([3.8,1.65,5.5],[6,10,12],[.4,1.5,0],k,40);},
end(t,k){setLook({bg:0x030405,fog:null,exposure:.75,bloom:.18,grain:.009,vignette:.3});candles(t,R.diningRoom.anchors.candlesticks,1);cam([.05,1.03,1.65],[.03,1.03,1.4],[0,.97,0],k,30);}
};
const sets={open:['townDusk','figure'],bread:['bakeryWindow'],years:['cellWall'],passport:['passportTable'],rejected:['nightStreet','innDoor','prisonDoor','kennel','figure'],door:['bishopDoor','figure'],dinner:['diningRoom','candlestick','candle2','settings'],steal:['diningRoom','gardenWall','silverBasket','figure'],caught:['bishopDoor','figure','gendarme','guard2','guard3'],gift:['diningRoom','candlestick','candle2'],soul:['diningRoom','candlestick','candle2'],coin:['plain','coin40Sous','figure','boy'],weep:['crossroads','figure'],end:['candlestick','candle2']};
export const SHOTS=Object.fromEntries(Object.entries(spec).map(([id,[tag,callouts]])=>[id,{sets:sets[id],tag,callouts,render:renderers[id]}]));
export function setRegistry(registry){R=registry;
// Overlay layout is part of the shot composition; leave captions in their reserved band.
const callouts=document.getElementById('callouts');Object.assign(callouts.style,{left:'110px',top:'44%',maxWidth:'560px',fontSize:'50px'});
for(const id of ['title','end'])Object.assign(document.getElementById(id).style,{bottom:'auto',top:'140px',height:'190px'});
R.candle2=makeCandlestick({lit:true});scene.add(R.candle2.group);const settings=R.settings={group:group('placeSetting')};settings.group.clear();R.diningRoom.anchors.placeSettings.forEach((p,i)=>{const s=makePlaceSetting();s.group.position.copy(p);s.group.position.x-=.17;s.group.rotation.y=p.z<0?Math.PI:0;settings.group.add(s.group);});}
