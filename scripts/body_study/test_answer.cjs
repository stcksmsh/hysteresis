// test_answer.cjs DIR [URL]: headless check of answer.html on dummy videos (see test_answer.sh).
// DIR holds answer.html, test/t01..t24.mp4 and an empty dl/. Never run on the real videos.
const puppeteer=require('/home/stcksmsh/Programming/Github/Hysteresis/node_modules/puppeteer-core');
const fs=require('fs'),T=process.argv[2];
(async()=>{
 const b=await puppeteer.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
 const p=await b.newPage(); await p.setViewport({width:1366,height:768});
 const reqs=[]; p.on('request',r=>reqs.push(r.url()));
 const cdp=await p.createCDPSession(); await cdp.send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:T+'/dl'});
 await p.goto(process.argv[3]||('file://'+T+'/answer.html'));
 const fit=await p.evaluate(()=>({sw:document.documentElement.scrollWidth,cw:document.documentElement.clientWidth,vh:document.getElementById('v').getBoundingClientRect().height,bottom:document.getElementById('next').getBoundingClientRect().bottom}));
 console.log('fit',JSON.stringify(fit));
 for(let n=0;n<24;n++){
  const before=await p.$eval('.pick',e=>e.disabled);
  if(!before) throw Error('pick enabled before play');
  await p.waitForFunction(()=>document.getElementById('v').readyState>=1);
  await p.click('#play');
  await p.waitForFunction(()=>!document.querySelector('.pick').disabled,{timeout:10000});
  // try to replay: must not play
  await p.evaluate(()=>document.getElementById('v').play().catch(()=>{}));
  await new Promise(r=>setTimeout(r,150));
  const replay=await p.evaluate(()=>!document.getElementById('v').paused);
  if(replay) throw Error('replayed');
  if(!(await p.$eval('#play',e=>e.disabled))) throw Error('play re-enabled');
  const head=await p.$eval('#head',e=>e.textContent); if(!head.startsWith(`${n+1} / 24`)) throw Error(head);
  await p.click(`.pick[data-k="${'ABC'[n%3]}"]`);
  if(n===2) await p.type('#note','slow');
  await p.click('#next');
 }
 await p.click('#save'); await new Promise(r=>setTimeout(r,800));
 const a=JSON.parse(fs.readFileSync(T+'/dl/answers.json'));
 console.log('answers',a.answers.length,JSON.stringify(a.answers[2]));
 console.log('requests not under test/:',reqs.filter(u=>!u.includes('/test/t')&&!u.endsWith('answer.html')));
 console.log('any key request:',reqs.some(u=>u.includes('key')));
 await b.close();
})().catch(e=>{console.error(e);process.exit(1)});
