import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';
import {createHash} from 'node:crypto';
const directory=new URL('../../vendor/',import.meta.url);
const sandbox={window:{},Date}; vm.createContext(sandbox);
for (const name of ['ecoradar-alinya-report-profiles.js','ecoradar-reading-report.js']) vm.runInContext(readFileSync(new URL(name,directory),'utf8'),sandbox);
const api=sandbox.window.EcoRadarAlinyaReportProfiles, render=sandbox.window.EcoRadarReadingReport.reportHtml;
const data=JSON.parse(readFileSync(new URL('current-viewer.json',import.meta.url),'utf8'));
const now=new Date('2026-09-08T17:50:00Z');
const copy=()=>structuredClone(data);
test('Real snapshot: maximum, independent Alfa, aged NDMI, current limiting wind',()=>{
 const original=JSON.stringify(data);
 const r=api.buildFireReport(data,now),html=render(r,'');
 assert.equal(r.maximum,'69,4/100');assert.match(r.facts[1].value,/Nivell 2/);
 assert.ok(r.limit.some(t=>t.includes('1,8 km/h'))); assert.match(r.scenario[0],/pendent i la continuïtat/);
 assert.ok(r.explanation.some(t=>t.includes('Només context històric')));
 assert.equal((html.match(/<h2>/g)||[]).length,7); assert.equal((html.match(/Fonts, dades i limitacions/g)||[]).length,1);
 assert.doesNotMatch(html,/dada no disponible\/100|NaN|undefined/);
 assert.ok(r.top.every(t=>data.currentFire.cells.features.some(f=>f.properties.cell_id===t.label)));
 assert.equal(JSON.stringify(data),original);
});
test('Missing or malformed maximum has no numeric suffix',()=>{
 for(const value of [null,undefined,NaN,Infinity,'69.4',-1,101]) {
  const d=copy(); d.currentFire.summary.maximum_index_0_100=value; delete d.currentFire.summary.max_index_0_100;
  assert.equal(api.buildFireReport(d,now).maximum,'No calculable amb les dades disponibles');
 }
});
test('Stale weather never generates an ignition-now interpretation',()=>{
 const r=api.buildFireReport(data,new Date('2026-09-10T17:50:00Z'));
 assert.match(r.scenario[0],/No es pot establir/);assert.ok(!r.limit.some(t=>t.includes('senyal observat')));
});
test('Old NDMI cannot drive a current drought narrative even if its value changes',()=>{
 const d=copy();d.currentFire.variables.ndmi_dryness.value='mediana -0.9';
 const before=api.buildFireReport(data,now),after=api.buildFireReport(d,now);
 assert.equal(JSON.stringify(before.favour),JSON.stringify(after.favour));
 assert.equal(JSON.stringify(before.scenario),JSON.stringify(after.scenario));
});
test('Alfa never changes the scenario or numerical index',()=>{
 const d=copy();d.currentFire.plaAlfa.level=4;d.currentFire.plaAlfa.label='extrem';
 const a=api.buildFireReport(data,now),b=api.buildFireReport(d,now);
 assert.equal(a.facts[0].value,b.facts[0].value); assert.equal(JSON.stringify(a.scenario),JSON.stringify(b.scenario));
});
test('Mismatched cells are not ranked as current sectors',()=>{
 const d=copy();d.currentFire.checkedAtUtc='2026-09-08T17:49:00Z';const r=api.buildFireReport(d,now);assert.equal(r.top.length,0);assert.match(r.sectors,/No es poden/);
});
test('Missing data and stale exposure stay explicit',()=>{
 const r=api.buildFireReport({},now);assert.equal(r.ignition.status,'no_ignition');assert.match(r.scenario[0],/No es pot/);assert.doesNotMatch(render(r,''),/NaN|undefined|disponible\/100/);
 const d=copy();d.biodiversityEcology.metadata.dynamic_data.current_fire.checked_at_utc='2026-09-01T00:00:00Z';assert.match(api.buildFireReport(d,now).exposure.join(' '),/altra comprovació/);
});
test('Ignition architecture rejects absent, invalid, outside and incomplete points',()=>{
 assert.equal(api.prepareIgnitionScenario({},now).status,'no_ignition');
 assert.equal(api.prepareIgnitionScenario({ignition:{geometry:{type:'Point',coordinates:[1,42]}}},now).status,'invalid_ignition');
 const point={type:'Feature',geometry:{type:'Point',coordinates:[1,42]},properties:{source:'test fixture, not an observation',observed_at_utc:'2026-09-08T17:45:00Z'}};
 const r=api.prepareIgnitionScenario({ignition:point,cells:{features:[]}},now);assert.equal(r.status,'insufficient_data');assert.equal(r.potentialCorridor,null);
});
test('Complete synthetic ignition inputs prepare axes, never a fabricated corridor',()=>{
 const ignition={type:'Feature',geometry:{type:'Point',coordinates:[1,42]},properties:{source:'synthetic test only',observed_at_utc:'2026-09-08T17:45:00Z'}};
 const layer={verified:true,source:'synthetic test only',coverage_verified:true,features:[],data_at_utc:'2026-09-08T17:45:00Z'};
 const input={ignition,cells:{features:[{geometry:{type:'Polygon',coordinates:[[[0,41],[2,41],[2,43],[0,43],[0,41]]]},properties:{cell_id:'TEST',raw:{slope_deg:25,aspect_deg:180}}}]},wind:{speed_kmh:10,from_degrees:270,source:'synthetic test only',spatial_scope:'ignition_local',timestamp_utc:'2026-09-08T17:45:00Z'},fuel:layer,barriers:layer,exposedElements:layer};
 const r=api.prepareIgnitionScenario(input,now);assert.equal(r.status,'ready_for_validated_model');assert.equal(r.axes.upslope_degrees,0);assert.equal(r.axes.downwind_degrees,90);assert.equal(r.potentialDirection,null);assert.equal(r.potentialCorridor,null);
 input.wind.spatial_scope='station';assert.equal(api.prepareIgnitionScenario(input,now).status,'insufficient_data');
});
test('Other reading profiles retain the previous behaviour',()=>{
 const hashes=JSON.parse(readFileSync(new URL('non-fire-profile-hashes.json',import.meta.url),'utf8'));
 const build=api.buildFactory(data,{},{});
 for(const [key,expected] of Object.entries(hashes)) {
  const report=build({key,type:'mode',guide:{}});delete report.generatedAt;delete report.ecologicalContext;
  assert.equal(createHash('sha256').update(JSON.stringify(report)).digest('hex'),expected,key);
 }
});
