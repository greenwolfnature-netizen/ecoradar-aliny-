import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';
const box={window:{},Date};vm.createContext(box);
for(const file of ['ecoradar-alinya-report-profiles.js','ecoradar-reading-report.js'])vm.runInContext(fs.readFileSync(new URL('../../vendor/'+file,import.meta.url),'utf8'),box);
const api=box.window.EcoRadarAlinyaReportProfiles,html=box.window.EcoRadarReadingReport.reportHtml;
const data=JSON.parse(fs.readFileSync(new URL('current-viewer.json',import.meta.url),'utf8'));
const now=new Date('2026-09-08T18:00:00Z');
const keys=['base','habitats','biodiversity','vegetation','vigor','moisture','temperature','albedo','climateRefuges','fireDanger','fireCurrent','fires','management','access','publicUse','places','landcover'];
test('All existing reading modes/layers get the shared contextual layer',()=>{
 const build=api.buildFactory(data,{},{}),before=JSON.stringify(data);
 for(const key of keys){const p=build({key,type:['access','publicUse','places','landcover'].includes(key)?'layer':'mode',guide:{}});assert.equal(p.ecologicalContext.key,key);assert.equal(p.ecologicalContext.scenarios.length,3);assert.ok(p.ecologicalContext.relations.length);assert.match(html(p,''),/gestió/);assert.doesNotMatch(html(p,''),/undefined|NaN/);}
 assert.equal(JSON.stringify(data),before);
});
test('Existing satellite scene retains date/value and cannot become today’s observation',()=>{
 const d=structuredClone(data);d.dailyReadings.readings.ndvi.value='0,900';d.dailyReadings.readings.ndvi.data_at_utc='2026-09-08T17:00:00Z';
 const c=api.buildEcologicalContext(d,'vigor',{},now);assert.match(c.observation,/0,616/);assert.match(c.observation,/Context històric/);assert.ok(c.relations.every(r=>!r.compatible && r.evidence===null));
 assert.match(c.processes.join(' '),/biomassa|combustible/);
});
const evidence={label:'Synthetic evidence',value:0.5,source:'Test only',quality_verified:true,coverage_verified:true,data_at_utc:'2026-09-08T17:00:00Z',resolution_m:20,support_id:'test-domain',grid_id:'test-grid',mask_id:'test-mask'};
test('Matching verified observations permit a dated association',()=>{const c=api.compatibleEvidence(evidence,{...evidence,value:0.2},now);assert.equal(c.compatible,true);assert.equal(c.scope,'dated');});
test('Every compatibility dimension blocks independently',()=>{
 for(const patch of [{data_at_utc:'2026-08-01T17:00:00Z'},{resolution_m:100},{support_id:'station'},{grid_id:'other'},{mask_id:'partial'},{coverage_verified:false},{quality_verified:false},{source:''},{value:null},{value:NaN},{data_at_utc:'2027-01-01'},{period_start_utc:'2026-09-09',period_end_utc:'2026-09-08'}])assert.equal(api.compatibleEvidence(evidence,{...evidence,...patch},now).compatible,false,JSON.stringify(patch));
});
test('Compatible historical observations remain historical',()=>{const a={...evidence,data_at_utc:'2026-07-07T10:00:00Z'};const c=api.compatibleEvidence(a,a,now);assert.equal(c.compatible,true);assert.equal(c.scope,'historical');});
test('Missing metadata never infers common resolution/coverage from same date/source',()=>{
 const c=api.buildEcologicalContext(data,'moisture',{},now);assert.equal(c.relations.find(r=>r.key==='vigor').compatible,false);assert.match(c.meaning,/no és una mesura directa/);assert.ok(c.combinations.every(t=>!t.includes('demostra')));
});
test('Verified evidence rendered with provenance and without causal claim',()=>{
 const d=structuredClone(data);d.ecologicalEvidence={vigor:{...evidence,label:'NDVI'},moisture:{...evidence,label:'NDMI',value:0.2}};
 const c=api.buildEcologicalContext(d,'vigor',{},now),r=c.relations.find(r=>r.key==='moisture');assert.equal(r.compatible,true);assert.match(r.provenance,/20 m/);assert.match(r.provenance,/Test only/);
 const h=html({ecologicalContext:c,facts:[],sources:[],limits:[]},'');assert.match(h,/no demostra causalitat/);assert.match(h,/Diagnosi conjunta i interpretacions alternatives/);
});
test('Missing data and unknown reading produce explicit limits without invented values',()=>{const c=api.buildEcologicalContext({},'unknown',{},now);assert.equal(c.relations.length,0);assert.match(c.meaning,/sense perfil/);assert.doesNotMatch(html({ecologicalContext:c,facts:[],sources:[]},''),/undefined|NaN/);});
test('Biodiversity detail and fire-specific output remain accessible',()=>{
 const build=api.buildFactory(data,{},{}),b=build({key:'biodiversity',type:'mode',guide:{}}),f=build({key:'fireCurrent',type:'mode',guide:{}});
 assert.match(html(b,''),/Consultar la diagnosi específica/);assert.match(html(b,''),/Buits de coneixement/);assert.match(html(f,''),/ignició ara/);assert.match(html(f,''),/Pla Alfa/);
});
test('Every indicator has distinct ecological scenarios, without inherited generic management',()=>{
 const build=api.buildFactory(data,{},{}),seen=new Set();
 for(const key of keys){const p=build({key,type:'mode',guide:{}}),c=p.ecologicalContext;
  const signature=JSON.stringify(c.scenarios);assert.ok(!seen.has(signature),key);seen.add(signature);
  assert.doesNotMatch(html(p,''),/Prioritzar unitats on el camp confirmi|Si el patró es manté en observacions comparables|recuperació de la funció objectiu/);
 }
});
test('Compatible NDVI and NDMI produce different interpretations when hydration differs',()=>{
 const d={ecologicalEvidence:{vigor:{...evidence,value:0.7},moisture:{...evidence,value:0.3}}};
 const wet=api.buildEcologicalContext(d,'vigor',{},now).relations.find(r=>r.key==='moisture').purpose;
 d.ecologicalEvidence.moisture.value=-0.2;
 const dry=api.buildEcologicalContext(d,'vigor',{},now).relations.find(r=>r.key==='moisture').purpose;
 assert.notEqual(wet,dry);assert.match(dry,/menor senyal hídric/);
 d.ecologicalEvidence.moisture.data_at_utc='2026-07-07';
 assert.equal(api.buildEcologicalContext(d,'vigor',{},now).relations.find(r=>r.key==='moisture').purpose,'');
});
const contrast={peer:'vigor',method:'native_same_mask_spatial_quartiles_v1',quality_verified:true,low_max:0.1,high_min:0.2,low_pixels:20,high_pixels:20,low_peer_median:0.7,high_peer_median:0.2};
test('Same albedo with different compatible vegetation contrasts gives opposite diagnoses',()=>{
 const d={ecologicalEvidence:{albedo:{...evidence,value:0.17,spatial_contrasts:[{...contrast}]},vigor:{...evidence,value:0.4}}};
 const dry=api.buildEcologicalContext(d,'albedo',{},now).combinations.join(' ');
 d.ecologicalEvidence.albedo.spatial_contrasts[0].high_peer_median=0.8;
 const green=api.buildEcologicalContext(d,'albedo',{},now).combinations.join(' ');
 assert.match(dry,/tenen menys verdor/);assert.match(green,/conserven més verdor/);assert.notEqual(dry,green);
});
test('Spatial contrasts cannot bypass compatibility, quality or physical ordering',()=>{
 for(const patch of [{quality_verified:false},{method:'unknown'},{low_max:0.3},{low_pixels:0},{high_peer_median:NaN}]){
 const d={ecologicalEvidence:{albedo:{...evidence,value:0.17,spatial_contrasts:[{...contrast,...patch}]},vigor:{...evidence,value:0.4}}};
 assert.doesNotMatch(api.buildEcologicalContext(d,'albedo',{},now).combinations.join(' '),/20 píxels/);
 }
});
test('New verified evidence never inherits old satellite distribution',()=>{
 const d=structuredClone(data);d.ecologicalEvidence={vigor:{...evidence,value:0.9}};
 assert.doesNotMatch(api.buildEcologicalContext(d,'vigor',{},now).meaning,/0,341|0,757/);
});
test('Missing albedo never becomes zero reflectance; null stats stay absent',()=>{
 const c=api.buildEcologicalContext({},'albedo',{},now);
 assert.doesNotMatch(c.meaning,/0,0 %|NaN/);assert.match(c.meaning,/No hi ha un valor/);
});
test('Precomputed structural intersections actively inform habitat and biodiversity diagnoses',()=>{
 const c=api.buildEcologicalContext(data,'biodiversity',{},new Date('2026-09-08T19:00:00Z'));
 assert.match(c.combinations.join(' '),/13 interseccions reals/);
 assert.match(c.management,/32 unitats/);
});
test('Future readings require their own registered diagnostic policy',()=>{
 assert.throws(()=>api.registerDiagnosticPolicy('new',{}));
 api.registerDiagnosticPolicy('testFuture',{peers:[],diagnose:()=>({meaning:'Specific test meaning',processes:['Specific process'],alternatives:'Specific alternative',scenarios:[['Test','Specific trajectory']],management:'Specific action'})});
 assert.equal(api.buildEcologicalContext({},'testFuture',{},now).meaning,'Specific test meaning');
 assert.throws(()=>api.registerDiagnosticPolicy('testFuture',{peers:[],diagnose:()=>({})}));
});
