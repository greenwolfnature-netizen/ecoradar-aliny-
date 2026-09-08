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
 const h=html({ecologicalContext:c,facts:[],sources:[],limits:[]},'');assert.match(h,/no demostra causalitat/);assert.match(h,/Hipòtesis condicionals/);
});
test('Missing data and unknown reading produce explicit limits without invented values',()=>{const c=api.buildEcologicalContext({},'unknown',{},now);assert.equal(c.relations.length,0);assert.match(c.meaning,/sense perfil/);assert.doesNotMatch(html({ecologicalContext:c,facts:[],sources:[]},''),/undefined|NaN/);});
test('Biodiversity detail and fire-specific output remain accessible',()=>{
 const build=api.buildFactory(data,{},{}),b=build({key:'biodiversity',type:'mode',guide:{}}),f=build({key:'fireCurrent',type:'mode',guide:{}});
 assert.match(html(b,''),/Consultar la diagnosi específica/);assert.match(html(b,''),/Buits de coneixement/);assert.match(html(f,''),/ignició ara/);assert.match(html(f,''),/Pla Alfa/);
});
