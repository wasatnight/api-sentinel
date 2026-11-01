import test,{afterEach} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const moduleUrls=new Map();
async function moduleUrl(path){
 if(moduleUrls.has(path))return moduleUrls.get(path);
 const text=await readFile(new URL('../'+path,import.meta.url),'utf8');
 let code=ts.transpileModule(text,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
 const imports=[...code.matchAll(/from ['"](\.[^'"]+)['"]/g)];
 for(const item of imports){
  const base=new URL('../'+path,import.meta.url);
  const resolved=new URL(item[1]+(item[1].endsWith('.ts')?'':'.ts'),base);
  const project=new URL('../',import.meta.url);
  const child=decodeURIComponent(resolved.pathname.slice(project.pathname.length));
  code=code.replace(item[0],`from '${await moduleUrl(child)}'`);
 }
 const url='data:text/javascript;base64,'+Buffer.from(code).toString('base64');moduleUrls.set(path,url);return url;
}
async function source(path){return import(await moduleUrl(path));}
const {request}=await source('src/lib/http.ts');
const {statisticsCsv}=await source('src/lib/reportCsv.ts');
const {NotificationTracker}=await source('src/lib/notifications.ts');
const originalFetch=globalThis.fetch;
afterEach(()=>{globalThis.fetch=originalFetch});
test('HTTP JSON body and response preserve the application contract',async()=>{
 globalThis.fetch=async(url,options)=>{assert.equal(url,'/api/v1/services');assert.equal(options.method,'POST');assert.equal(options.headers['Content-Type'],'application/json');assert.equal(JSON.parse(options.body).name,'Servicio Ñ');return new Response(JSON.stringify({id:'one'}),{status:201})};
 assert.deepEqual(await request('/services','POST',{name:'Servicio Ñ'}),{id:'one'});
});
test('HTTP 204 is accepted without parsing an absent body',async()=>{
 globalThis.fetch=async()=>new Response(null,{status:204});
 assert.equal(await request('/services/one','DELETE'),undefined);
});
test('Server validation errors remain readable',async()=>{
 globalThis.fetch=async()=>new Response(JSON.stringify({detail:[{msg:'Name is required'},{msg:'Invalid URL'}]}),{status:422});
 await assert.rejects(request('/services','POST',{}),/Name is required · Invalid URL/);
});
test('Proxy errors do not leak HTML and transport errors are understandable',async()=>{
 globalThis.fetch=async()=>new Response('<html>proxy internals</html>',{status:502});
 await assert.rejects(request('/workspace'),/Check the backend connection/);
 globalThis.fetch=async()=>{throw new Error('private connection detail')};
 await assert.rejects(request('/workspace'),e=>e.message.includes('backend is running')&&!e.message.includes('private'));
});
test('Cancelling a superseded query aborts fetch without claiming a backend failure',async()=>{
 const controller=new AbortController();
 globalThis.fetch=(_url,options)=>new Promise((_resolve,reject)=>{options.signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true})});
 const response=request('/statistics','GET',undefined,controller.signal);
 controller.abort();
 await assert.rejects(response,e=>e.name==='AbortError');
});
const metric={total_checks:0,evaluated_checks:0,unknown_checks:0,successes:0,failures:0,availability:null,error_rate:null,latency_count:0,latency_avg:null,latency_min:null,latency_max:null,p50:null,p95:null,p99:null};
const data={period:'1H',start:'2026-10-27T00:00:00Z',end:'2026-10-27T01:00:00Z',summary:metric,services:[{...metric,id:'one',name:'=HYPERLINK("bad")'},{...metric,id:'two',name:'Nombre, con "comillas"'}]};
test('CSV preserves empty metrics rather than exporting false 100 percent or zero latency',()=>{
 const text=statisticsCsv(data);
 assert.ok(text.startsWith('\uFEFF'));
 const rows=text.split('\r\n');
 assert.equal(rows.length,4);
 assert.ok(rows[0].includes('"Service ID"'));
 const fields=line=>[...line.matchAll(/"((?:[^"]|"")*)"/g)].map(match=>match[1].replaceAll('""','"'));
 const result=Object.fromEntries(fields(rows[0]).map((name,index)=>[name,fields(rows[1])[index]]));
 assert.equal(result['Check-based availability %'],'');
 assert.equal(result['Average ms'],'');
 assert.equal(result['Latency samples'],'0');
 assert.ok(!text.includes('100%'));
});
test('CSV neutralizes formulas and quotes names while retaining IDs and dates',()=>{
 const text=statisticsCsv(data);
 assert.ok(text.includes("\"'=HYPERLINK(\"\"bad\"\")\""));
 assert.ok(text.includes('"Nombre, con ""comillas"""'));
 assert.ok(text.includes('"2026-10-27T00:00:00Z"'));
 assert.ok(text.includes('"one"'));
});
const notice=(id,time=1,read=false)=>({id,created_at:new Date(time*1000).toISOString(),read_at:read?new Date().toISOString():null,message:'event '+id});
test('Notification history is silent on first load; only new unread events notify once',()=>{
 const tracker=new NotificationTracker();
 assert.deepEqual(tracker.poll([notice('old')]),[]);
 assert.deepEqual(tracker.poll([notice('new',2),notice('old')]).map(a=>a.id),['new']);
 assert.deepEqual(tracker.poll([notice('new',2,true),notice('old')]),[]);
 assert.deepEqual(tracker.poll([notice('old')]),[]);
});
test('Older history surfacing after deletion does not become a new notification',()=>{
 const tracker=new NotificationTracker();
 tracker.poll([notice('initial',10)]);
 assert.deepEqual(tracker.poll([notice('older',5)]),[]);
});
test('Notification tracking is bounded and reset starts a silent new session',()=>{
 const tracker=new NotificationTracker(3);
 tracker.poll([]);
 for(let n=1;n<=8;n++)assert.equal(tracker.poll([notice(String(n),n)]).length,1);
 assert.equal(tracker.size,3);
 assert.deepEqual(tracker.poll([notice('1',1)]),[]);
 tracker.reset();
 assert.deepEqual(tracker.poll([notice('restored',20)]),[]);
 assert.equal(tracker.size,1);
});


const {getLanguage,getLocale,setLanguage,t,localizeMessage,subscribeLanguage}=await source('src/lib/i18n.ts');
test('English is the default application language',()=>{setLanguage('en');assert.equal(getLanguage(),'en');assert.equal(getLocale(),'en-US');assert.equal(t('Save changes'),'Save changes')});
test('Language switching notifies subscribers and uses Spanish text and locale',()=>{let calls=0;const unsubscribe=subscribeLanguage(()=>calls++);setLanguage('es');assert.equal(t('Save changes'),'Guardar cambios');assert.equal(getLocale(),'es-MX');assert.equal(calls,1);unsubscribe();setLanguage('en')});
test('Language choice is persisted without modifying profile or service data',()=>{const writes=[];const previous=Object.getOwnPropertyDescriptor(globalThis,'localStorage');Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{setItem:(key,value)=>writes.push([key,value])}});try{assert.equal(setLanguage('es'),true);assert.deepEqual(writes,[['api-sentinel-language-v1','es']])}finally{if(previous)Object.defineProperty(globalThis,'localStorage',previous);else delete globalThis.localStorage;setLanguage('en')}});
test('Unavailable browser storage keeps the language usable for the session',()=>{const previous=Object.getOwnPropertyDescriptor(globalThis,'localStorage');Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{setItem:()=>{throw Error('quota')}}});try{assert.equal(setLanguage('es'),false);assert.equal(t('Save changes'),'Guardar cambios')}finally{if(previous)Object.defineProperty(globalThis,'localStorage',previous);else delete globalThis.localStorage;setLanguage('en')}});
test('Legacy Spanish errors are displayed in English without rewriting history',()=>{setLanguage('en');assert.equal(localizeMessage('HTTP 200 fuera del rango esperado 500–599.'),'HTTP 200 outside the expected range 500–599.');assert.equal(localizeMessage('My API: Se agotó el tiempo de espera (10 s).'),'My API: Request timed out (10 s).');assert.equal(localizeMessage('Mi API volvió a responder dentro de las condiciones configuradas.'),'Mi API is responding within the configured conditions again.')});
test('Dynamic English errors and messages support Spanish display',()=>{setLanguage('es');assert.equal(localizeMessage('HTTP 500 outside the expected range 200–299.'),'HTTP 500 fuera del rango esperado 200–299.');assert.equal(localizeMessage('Latency 500 ms exceeds the threshold of 400 ms.'),'Latencia 500 ms mayor al umbral de 400 ms.');setLanguage('en')});
test('CSV headings use the chosen language while retaining user-authored names',()=>{setLanguage('es');const text=statisticsCsv(data);assert.ok(text.includes('"ID de servicio"'));assert.ok(text.includes('Nombre, con'));setLanguage('en');assert.ok(statisticsCsv(data).includes('"Service ID"'))});

const {avatarPlacement}=await source('src/lib/avatar.ts');
test('Portrait, landscape and square avatars retain all four image corners inside the circle',()=>{
 for(const [width,height] of [[200,800],[800,200],[400,400]]){
  const frame=avatarPlacement(width,height);const radius=128;
  assert.ok(Math.abs(frame.width/frame.height-width/height)<1e-9);
  assert.ok(Math.abs(frame.x+frame.width/2-radius)<1e-9);
  assert.ok(Math.abs(frame.y+frame.height/2-radius)<1e-9);
  for(const x of [frame.x,frame.x+frame.width])for(const y of [frame.y,frame.y+frame.height])assert.ok(Math.hypot(x-radius,y-radius)<=radius+1e-9);
 }
});
test('Invalid avatar dimensions are rejected before drawing',()=>{for(const dims of [[0,50],[-1,50],[Infinity,50],[50,NaN]])assert.throws(()=>avatarPlacement(...dims),/positive finite/)});
const {avatarFrame,avatarFillZoom,normalizeAvatarAdjustment}=await source('src/lib/avatar.ts');
test('Zoom increases the image around the same center without changing its aspect ratio',()=>{
 const first=avatarFrame(300,600,{zoom:1,x:0,y:0});const closer=avatarFrame(300,600,{zoom:3,x:0,y:0});
 assert.ok(Math.abs(closer.width-first.width*3)<1e-9);assert.ok(Math.abs(closer.height-first.height*3)<1e-9);
 assert.ok(Math.abs(closer.x+closer.width/2-128)<1e-9);assert.ok(Math.abs(closer.y+closer.height/2-128)<1e-9);
});
test('The same framing renders identically at preview and export resolutions',()=>{
 const adjustment={zoom:2.75,x:0.42,y:-0.63};const preview=avatarFrame(500,800,adjustment,224);const saved=avatarFrame(500,800,adjustment,256);
 for(const key of ['x','y','width','height'])assert.ok(Math.abs(preview[key]/224-saved[key]/256)<1e-9);
});
test('Fill circle covers the frame for portrait, landscape and square images',()=>{
 for(const [width,height] of [[200,800],[800,200],[400,400]]){const frame=avatarFrame(width,height,{zoom:avatarFillZoom(width,height)});assert.ok(frame.width>=256-1e-9&&frame.height>=256-1e-9)}
});
test('Position controls can reach image edges at high zoom',()=>{
 const left=avatarFrame(400,400,{zoom:8,x:1,y:1});const right=avatarFrame(400,400,{zoom:8,x:-1,y:-1});
 assert.ok(Math.abs(left.x)<1e-9&&Math.abs(left.y)<1e-9);
 assert.ok(Math.abs(right.x+right.width-256)<1e-9&&Math.abs(right.y+right.height-256)<1e-9);
});
test('Saved framing values are bounded and invalid values fall back safely',()=>{
 assert.deepEqual(normalizeAvatarAdjustment({zoom:99,x:5,y:-5}),{zoom:8,x:1,y:-1});
 assert.deepEqual(normalizeAvatarAdjustment({zoom:NaN,x:Infinity}),{zoom:1,x:0,y:0});
});
