import { TM, cue, shotRange, seg } from './core.js';
const el=id=>document.getElementById(id);
export function setTag(text){el('chapter').textContent=text;}
export function setCallouts(items,t,end){el('callouts').replaceChildren(...items.filter(item=>t>=item.at&&t<Math.min(end,item.until??end)).map(item=>{const p=document.createElement('p');p.textContent=item.text;const a=seg(t,item.at,item.at+.4)*(1-seg(t,end-.4,end));p.style.opacity=a;p.style.transform=`translateY(${(1-a)*14}px)`;p.style.fontStyle=item.italic?'italic':'normal';return p;}));}
export function updateOverlay(t,id,shot){setTag(shot.tag??'');setCallouts(shot.callouts??[],t,shotRange(id)[1]);
const l=TM.lines.find(l=>t>=Math.min(l.start,l.words[0]?.s??l.start)&&t<=Math.max(l.end,l.words.at(-1)?.e??l.end));
const box=el('captions');box.replaceChildren();if(l){const p=document.createElement('p');l.words.forEach((w,i)=>{const span=document.createElement('span');span.textContent=(i?' ':'')+w.w;span.className=t>=w.s&&t<w.e?'current':'';p.append(span);});box.append(p);}
el('title').style.opacity=id==='open'?1-seg(t,Math.max(shotRange('open')[0],cue('open','walks')-.4),cue('open','walks')):0;
el('end').style.opacity=id==='end'?seg(t,cue('end','Les'),Math.min(cue('end','Les')+.4,TM.duration)):0;
}
