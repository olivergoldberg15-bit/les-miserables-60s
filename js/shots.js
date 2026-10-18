import { scene, setCam, setLook, cue, shotRange, lineEnd, seg, lerp, eio } from './core.js';
import { makeCandlestick, makePlaceSetting } from './kit/silver.js';
let R;
const item=(id,word,text,italic=false)=>({at:cue(id,word),text,italic});
const escapes=Array.from({length:4},(_,i)=>lerp(cue('years','Four'),cue('years','nineteen'),i/4));
const spec={
open:['VOL. I · BOOK 2 · CH. I',[item('open','October','Digne · October 1815')]],
bread:['CH. VI · 1796',[item('bread','Jean','1796'),item('bread','seven','7 children')]],
years:['CH. VI',[{...item('years','Five','5 years'),until:escapes[0]},...['+3','+5','+3','+3'].map((text,i)=>({at:escapes[i],until:escapes[i+1]??cue('years','nineteen'),text})),item('years','nineteen','= 19 years')]],
passport:['CH. III · IX',[item('passport','convict','109 francs 15 sous for 19 years of work')]],
rejected:['CH. I',['Inns','prison','kennel'].map((w,i,ws)=>({...item('rejected',w,`Turned away: ${i+1}`),until:i<2?cue('rejected',ws[i+1]):Infinity}))],
door:['CH. III',[]],dinner:['CH. III',[item('dinner','sir','Monsieur')]],steal:['CH. XI',[]],caught:['CH. XII',[]],gift:['CH. XII',[item('gift','candlesticks','≈ 200 francs')]],
soul:['CH. XII',[item('soul','You','You no longer belong to evil, but to good.',true)]],coin:['CH. XIII',[item('coin','coin','40 sous = 2 francs')]],weep:['CH. XIII',[item('weep','nineteen','First tears in 19 years')]],end:['VOL. I · BOOK 2',[]]
};
const group=key=>R[key].group;
const progress=(t,id,word,end=lineEnd(id))=>eio(seg(t,cue(id,word),end));
function look(key,extra={}){if(key==='diningRoom'){R.diningRoom.parts.cupboardDoors.forEach(d=>d.rotation.y=0);}setLook({...R[key].look,grain:.009,vignette:.22,bloom:.11,...extra});}
function cam(a,b,target,k,fov=35){setCam(a.map((v,i)=>lerp(v,b[i],eio(k))),target,fov);}
function actor(key,pos,pose='stand',phase=0,rotation=Math.PI){const a=R[key];a.group.position.set(...pos);a.group.rotation.set(0,rotation,0);a.pose(pose,phase);}
function candles(t,positions,lit=1){['candlestick','candle2'].forEach((key,i)=>{group(key).position.copy(positions[i]);group(key).rotation.set(0,0,0);R[key].update(t,lit);});}
function tableCandles(t,lit=1,lift=0){const ps=R.diningRoom.anchors.candlesticks.map(p=>p.clone());ps.forEach(p=>p.y+=lift);candles(t,ps,lit);}
const renderers={
open(t,k){look('townDusk',{exposure:.78});actor('figure',[0,0,lerp(20,8,eio(k))],'walk',k*4);cam([0,14,34],[0,2.8,30],[0,4,-16],k,38);},
bread(t,k){look('bakeryWindow');R.bakeryWindow.update(t,progress(t,'bread','stole',cue('bread','seven')));cam([.65,1.45,3.2],[.45,1.25,1.9],[.25,1.25,0],k,32);},
years(t,k){look('cellWall');const count=t<cue('years','Five')?0:t<escapes[0]?5:t<escapes[1]?8:t<escapes[2]?13:t<escapes[3]?16:19;R.cellWall.update(t,count/19);cam([-1.4,1.35,3.8],[.6,1.35,3.8],[0,1.35,-.2],k,38);},
passport(t,k){look('passportTable');cam([.15,2.05,.35],[.05,1.65,.2],[0,.78,.05],k,36);},
rejected(t,k){const n=t<cue('rejected','prison')?0:t<cue('rejected','kennel')?1:2;const keys=['innDoor','prisonDoor','kennel'];keys.forEach((key,i)=>group(key).visible=i===n);const key=keys[n],word=['Inns','prison','kennel'][n],end=n<2?cue('rejected',['prison','kennel'][n]):lineEnd('rejected');look(key);const p=progress(t,'rejected',word,lerp(cue('rejected',word),end,.35));R[key].update?.(t,p);actor('figure',[1.05,0,n===2?lerp(1.4,2.3,p):1.4],'stand',0,Math.PI);setCam(n===2?[2.9,1.05,4.2]:[2.6,1.7,4.8],n===2?[0,.45,.3]:[0,1.15,0],38);},
door(t,k){look('bishopDoor');const knock=progress(t,'door','knocks',cue('door','door'));R.bishopDoor.update(t,progress(t,'door','door',shotRange('door')[1]));actor('figure',[.3,0,1.05],'knock',knock,Math.PI);cam([2.2,.85,3.5],[1.9,.85,3.2],[0,1.2,.2],k,38);},
dinner(t,k){look('diningRoom',{exposure:.88});const p=progress(t,'dinner','lights',cue('dinner','silver'));tableCandles(t,p,.12*(1-p));R.diningRoom.parts.candleLight.intensity*=p;cam([1.2,1.25,1.4],[.52,1.12,.96],[0,1.02,0],k,30);},
steal(t,k){const garden=t>=cue('steal','jumps');group('diningRoom').visible=!garden;group('gardenWall').visible=garden;look(garden?'gardenWall':'diningRoom',{exposure:garden?.65:.68});const basket=group('silverBasket');basket.rotation.set(0,0,0);R.silverBasket.update(t,{empty:garden});if(!garden){const p=progress(t,'steal','silver',cue('steal','jumps'));basket.position.copy(R.diningRoom.anchors.basket);basket.position.y+=p*1.4;R.diningRoom.parts.candleLight.intensity=0;R.diningRoom.parts.hearthLight.intensity=.5;R.diningRoom.parts.moon.intensity=60;R.diningRoom.parts.cupboardDoors.forEach((d,i)=>d.rotation.y=(i?1:-1)*1.4);group('figure').visible=false;cam([2,1.6,.9],[2.2,1.6,.3],[2.7,1.25,-2.1],k,34);}else{const p=progress(t,'steal','jumps',cue('steal','wall'));basket.position.copy(R.gardenWall.anchors.basket);basket.position.y+=1.3*(1-p);basket.rotation.z=p*.45;actor('figure',[0,.3,-.1],'vault',p,Math.PI);setCam([5,3.4,7],[0,1,-1],38);}},
caught(t,k){look('bishopDoor',{bg:0x605b50,exposure:.9});R.bishopDoor.update(t,1);actor('figure',[0,0,1.1],'held');[-1,1,0].forEach((x,i)=>actor(['gendarme','guard2','guard3'][i],[x*.65,0,i===2?.2:1.05],'stand',0,Math.PI));cam([2.5,1.4,6],[2.1,1.4,5],[0,1.1,.8],k,36);},
gift(t,k){look('diningRoom',{exposure:.92});const p=progress(t,'gift','candlesticks',lineEnd('gift'));const a=R.diningRoom.anchors;const ps=[a.mantelLeft,a.mantelRight].map((v,i)=>v.clone().lerp(v.clone().set(-.25+i*.5,1.22,-1.25),p));candles(t,ps,1);cam([-1.6,1.65,-.6],[-.7,1.7,1.1],[-1.5+p,1.52,-2.6+p*1.35],k,32);},
soul(t,k){look('diningRoom',{bg:0x120c06,exposure:lerp(.7,1.05,eio(k)),bloom:.2});tableCandles(t);R.diningRoom.parts.candleLight.intensity=2;cam([-.24,1.14,.55],[-.25,1.14,.42],[-.28,1.113,0],k,28);},
coin(t,k){look('plain',{exposure:.7,fog:{color:0x88705a,density:.09}});const stop=cue('coin','coin'),p=eio(seg(t,shotRange('coin')[0],stop));const c=group('coin40Sous');c.position.set(lerp(-.18,0,p),.04,0);c.rotation.set(0,0,(1-p)*Math.PI/2);c.rotation.y=p*Math.PI*5;const down=progress(t,'coin','steps',stop);actor('figure',[.05,lerp(.28,0,down),-.11],'stand',0,Math.PI);actor('boy',[1,0,-14],'stand',0,Math.PI);setCam([.14,.11,.55],[0,.045,0],32);},
weep(t,k){look('crossroads',{exposure:.72});const p=progress(t,'weep','breaks',cue('weep','weeps'));actor('figure',[1.9,.5,1.1],'kneel_collapse',p,0);cam([4,2.6,6],[6,10,12],[1.2,.6,0],k,40);},
end(t,k){setLook({bg:0x030405,fog:null,exposure:.75,bloom:.18,grain:.009,vignette:.3});candles(t,R.diningRoom.anchors.candlesticks,1);cam([.12,1.14,1.9],[.1,1.14,1.6],[0,1.02,0],k,30);}
};
const sets={open:['townDusk','figure'],bread:['bakeryWindow'],years:['cellWall'],passport:['passportTable'],rejected:['nightStreet','innDoor','prisonDoor','kennel','figure'],door:['bishopDoor','figure'],dinner:['diningRoom','candlestick','candle2','settings'],steal:['diningRoom','gardenWall','silverBasket','figure'],caught:['bishopDoor','figure','gendarme','guard2','guard3'],gift:['diningRoom','candlestick','candle2'],soul:['diningRoom','candlestick','candle2'],coin:['plain','coin40Sous','figure','boy'],weep:['crossroads','figure'],end:['candlestick','candle2']};
export const SHOTS=Object.fromEntries(Object.entries(spec).map(([id,[tag,callouts]])=>[id,{sets:sets[id],tag,callouts,render:renderers[id]}]));
export function setRegistry(registry){R=registry;R.candle2=makeCandlestick({lit:true});scene.add(R.candle2.group);const settings=R.settings={group:group('placeSetting')};settings.group.clear();R.diningRoom.anchors.placeSettings.forEach((p,i)=>{const s=makePlaceSetting();s.group.position.copy(p);s.group.position.x-=.17;s.group.rotation.y=p.z<0?Math.PI:0;settings.group.add(s.group);});}
