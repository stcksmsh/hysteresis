const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const template=fs.readFileSync(process.argv[2],'utf8');
const studies=Array.from({length:3},()=>({frames:Array.from({length:257},()=>[0,30,0,55,0,67,0,0,0,'rest'])}));
let now=0;
class ClassList { add(){} toggle(){} }
class Element {
  constructor(id){this.id=id;this.value='0';this.textContent='';this.firstChild={nodeValue:''};this.classList=new ClassList;this.style={};this.clientWidth=960;this.clientHeight=440;this.width=960;this.height=440;this.listeners={};}
  addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
  emit(name){for(const fn of this.listeners[name]??[])fn();}
  setAttribute(){} append(){} querySelector(){return {disabled:false,textContent:''};}
  getContext(){return new Proxy({}, {get:()=>()=>{}});}
}
class Media extends Element {
  constructor(mode){super('track');this.paused=true;this.muted=false;this.currentTime=0;this.duration=400;this.playMode=mode;}
  play(){if(this.playMode==='reject')return Promise.reject(new Error('blocked'));if(this.playMode==='pending')return new Promise((resolve,reject)=>{this.resolvePending=resolve;this.rejectPending=reject;});this.paused=false;this.emit('play');return Promise.resolve();}
  pause(){this.paused=true;this.emit('pause');}
  end(){this.paused=true;this.emit('ended');}
}
function boot(mode){
  const ids=['arm','visual','play','study','bpm','bpm-value','next-accent','enable-audio','sound','grid','offset','beat-zero','tempo-label','clock-label','timeline-label','seek','elapsed','beats','sound-error','event','phase','position','q0','q1','q2'];
  const elements=Object.fromEntries(ids.map(id=>[id,new Element(id)]));
  const media=new Media(mode);elements.track=media;elements.study.value='2';elements.grid.value='manual';
  const document={body:{classList:new ClassList},hidden:false,getElementById:id=>elements[id],createElement:id=>new Element(id),addEventListener(){}};
  const source=template.match(/<script>([\s\S]*)<\/script>/)[1].replace('__ARM_DATA__',JSON.stringify(studies)).replace('__LOOP_BEATS__','16').replace('__SAMPLES_PER_BEAT__','16').replace('__TRACK_URL_JSON__','"track.m4a"').replace('__SIDECAR_JSON_STRING__','""').replace('__SONG_DATA__','null');
  const window={};const context={window,document,location:{search:'?remote=1'},URLSearchParams,performance:{now:()=>now},matchMedia:()=>({matches:false}),requestAnimationFrame:()=>0,setInterval:()=>0,devicePixelRatio:1,console};
  vm.createContext(context);vm.runInContext(source,context);return {elements,media,inspect:()=>window.__ARM_PREVIEW__.inspect()};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  now=0;let view=boot('reject');await tick();now=2500;
  assert.equal(view.inspect().state.remotePreviewing,true);assert.equal(view.inspect().state.rawMediaSeconds,2.5);
  view.media.playMode='resolve';await view.elements.play.onclick();
  assert.equal(view.media.muted,false);assert.equal(view.media.currentTime,2.5);assert.equal(view.inspect().state.remotePreviewing,false);
  view.media.currentTime=3.25;view.media.pause();now=9000;assert.equal(view.inspect().state.rawMediaSeconds,3.25);

  now=0;view=boot('reject');await tick();view.elements.seek.value='17.25';view.elements.seek.oninput();now=9000;
  assert.equal(view.inspect().state.rawMediaSeconds,17.25);assert.equal(view.inspect().state.remotePreviewing,false);
  view.media.playMode='resolve';await view.elements.play.onclick();assert.equal(view.media.muted,false);assert.equal(view.media.currentTime,17.25);

  now=0;view=boot('resolve');await tick();view.media.currentTime=4.5;await view.elements['enable-audio'].onclick();
  assert.equal(view.media.muted,false);assert.equal(view.media.currentTime,4.5);assert.equal(view.elements['enable-audio'].hidden,true);
  view.media.currentTime=8;view.media.end();now=15000;assert.equal(view.inspect().state.rawMediaSeconds,8);assert.equal(view.inspect().state.remotePreviewing,false);

  now=0;view=boot('reject');await tick();view.elements['sound-error'].textContent='Pause is final.';view.media.playMode='pending';
  const pending=view.elements['enable-audio'].onclick();view.media.currentTime=6;view.media.pause();view.media.rejectPending(new Error('AbortError'));await pending;
  assert.equal(view.elements['sound-error'].textContent,'Pause is final.');
  console.log('arm media transport: passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
