const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const template=fs.readFileSync(process.argv[2]||'crates/hyst-previz/src/ensemble.html','utf8');
const data={duration:1,fps:2,rig:{channels:[{name:'base_yaw'}]},placements:[],frames:[
  [[[[0,0,0],[0,0,1]],[[1,0,0],[1,0,1]]],0],
  [[[[0,0,0],[0,0,2]],[[1,0,0],[1,0,2]]],0],
  [[[[0,0,0],[0,0,3]],[[1,0,0],[1,0,3]]],1]
],cues:[
  {start:0,end:.7,character:'quiet',formation:'unison',reason:'source quiet',sourceActivity:[.2,0,.5,0],confidence:.2},
  {start:.7,end:1,character:'full',formation:'canon',reason:'source rise',sourceActivity:[.8,0,.5,0],confidence:.8}
]};
const source=template.replace('__ENSEMBLE_DATA__',JSON.stringify(data)).replace('__TRACK_URL_JSON__','"song.m4a"').replace('__DURATION__','1');
const script=source.match(/<script>([\s\S]*?)<\/script>/)[1];
const events={};
function element(id) { return {id,value:'0',textContent:'',addEventListener(name,fn){events[`${id}:${name}`]=fn;}}; }
const ids=['audio','ensemble','seek','play','offset','clock','decision','evidence','uncertainty','rig-description'];
const elements=Object.fromEntries(ids.map(id=>[id,element(id)]));
const context2d=Object.fromEntries(['fillRect','beginPath','moveTo','lineTo','closePath','fill','stroke','arc','fillText','save','restore','clip','translate','scale'].map(k=>[k,()=>{}]));
context2d.createLinearGradient=context2d.createRadialGradient=()=>({addColorStop(){}});
elements.ensemble.getContext=()=>context2d;
elements.audio.paused=true;elements.audio.currentTime=0;elements.audio.playCalls=0;
elements.audio.play=async function(){this.playCalls++;this.paused=false;events['audio:play']();};
elements.audio.pause=function(){this.paused=true;events['audio:pause']();};
const sandbox={document:{getElementById:id=>elements[id]},window:{},requestAnimationFrame:()=>{},console};
vm.createContext(sandbox);vm.runInContext(script,sandbox);
const api=sandbox.window.__ENSEMBLE_PREVIEW__;
const near=(a,b)=>assert(Math.abs(a-b)<1e-9,`${a} != ${b}`);
assert.equal(elements.audio.playCalls,0,'sound must await Play');
assert.equal(elements.audio.paused,true);
assert.equal(elements.audio.src,'song.m4a');
near(api.inspect(.25).agents[0][1][2],1.5);
near(api.inspect(.75).agents[1][1][2],2.5);
near(api.inspect(.25).visual.confidence,.2);
near(api.inspect(.75).visual.confidence,.5);
near(api.inspect(-4).time,0);near(api.inspect(9).time,1);
assert.equal(api.inspect(1).cue.reason,'source rise');
assert.equal(api.inspect(.75).visual.formation,'canon');
assert.deepEqual(JSON.parse(JSON.stringify(api.inspect(.25))),JSON.parse(JSON.stringify(api.inspect(.25))),'random access repeatable');
near(api.scoreTime(3,.4,10),2.6);near(api.scoreTime(.1,.4,10),0);
elements.offset.value='.2';events['offset:input']();
elements.audio.currentTime=.6;events['audio:seeked']();
assert.equal(elements.clock.textContent,'0:00.60');
near(api.inspect(api.scoreTime(elements.audio.currentTime,Number(elements.offset.value),data.duration)).time,.4);
const frozen=elements.clock.textContent;
events['audio:pause']();
assert.equal(elements.clock.textContent,frozen,'pause must retain audio position');
elements.seek.value='.8';events['seek:input']();
near(elements.audio.currentTime,.8);
assert.equal(elements.clock.textContent,'0:00.80');
assert.match(elements.evidence.textContent,/source quiet/);
console.log('ensemble preview: seek, pause, offset, deterministic sample passed');
