"""Reading lifecycle metadata only; never changes ecological values or formulas."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import csv
import json
from pathlib import Path

VOLATILE = {'snapshot_id', 'checked_at_utc', 'generated_at_utc', 'query_date', 'data_consulta',
            'date_consulted', 'latest_catalog_check_utc', 'updated', 'status_note'}


def semantic(value):
    if isinstance(value, dict):
        return {k: semantic(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [semantic(v) for v in value]
    return value


def fingerprint(value):
    return hashlib.sha256(json.dumps(semantic(value), sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def instant(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).replace(tzinfo=timezone.utc) if len(value) == 10 else datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def evaluate(item, policy, now, previous=None, source_check=None):
    previous = previous or {}
    quality = str(item.get('qa') or item.get('quality') or '').lower()
    provisional = 'provisional' in quality
    available = item.get('quality_verified') is True
    stamp = item.get('data_at_utc')
    period = item.get('period_end_utc')
    data_time = instant(stamp or period)
    # A deterministic solar calculation is a target time, not a future observation.
    future = bool(data_time and data_time > now and item.get('reading_id') != 'terrain_shade')
    accepted = available and not provisional and not future
    content = {k: item.get(k) for k in ('value', 'value_numeric', 'data_at_utc', 'period_start_utc', 'period_end_utc', 'qa', 'source_version')}
    digest = fingerprint(content)
    new = accepted and digest != previous.get('validated_fingerprint')
    maximum = policy.get('max_age_hours')
    age = max(0, (now - data_time).total_seconds()/3600) if data_time else None
    stale = bool(age is not None and maximum is not None and age > maximum)
    block = policy.get('blocking_reason')
    if source_check and source_check.get('status') in {'requires_credentials','service_unavailable','blocked','pending_verification'}:
        block = source_check['status'] + (': ' + source_check.get('note','') if source_check.get('note') else '')
    if future or provisional or (available and not data_time and item.get('temporal_kind') not in {'inventory_version'}):
        state = 'PENDENT QA'
    elif not available:
        previous_time=instant(previous.get('last_validated_data_at_utc'))
        retained_stale=bool(previous_time and maximum is not None and (now-previous_time).total_seconds()>maximum*3600)
        state = ('DESACTUALITZADA' if retained_stale else 'ÚLTIMA VALIDADA') if previous.get('validated_fingerprint') else 'SENSE DADA'
    elif stale:
        state = 'DESACTUALITZADA'
    elif item.get('temporal_kind') in {'multitemporal_composite','mixed_period_derived','inventory_version'} or not new or block:
        state = 'ÚLTIMA VALIDADA'
    else:
        state = 'ACTUAL'
    last = (stamp or period) if accepted else previous.get('last_validated_data_at_utc')
    return {'status':state, 'last_validated_data_at_utc':last,
            'validated_period_start_utc':item.get('period_start_utc') if accepted else previous.get('validated_period_start_utc'),
            'source_version':item.get('source_version'),
            'validated_fingerprint':digest if accepted else previous.get('validated_fingerprint'),
            'last_validated_value':item.get('value') if accepted else previous.get('last_validated_value'),
            'candidate_data_at_utc':stamp if provisional else None,
            'candidate_qa_pending':provisional or future,
            'overdue':stale, 'age_hours':round(age,2) if age is not None else None,
            'evaluated_at_utc':now.isoformat().replace('+00:00','Z'),
            'source_checked_at_utc':(source_check or {}).get('checked_at_utc'),
            'new_valid_data':new, 'blocking_reason':block, 'policy':policy}


def apply_policies(project, readings, daily, previous, now=None):
    project = Path(project)
    root = project.parents[1]
    policies = json.loads((root/'config/alinya_reading_policies.json').read_text())['readings']
    now = now or datetime.now(timezone.utc)
    checks = daily.get('source_checks',{})
    monitors_path = project/'metadata/source_version_checks.json'
    monitors = json.loads(monitors_path.read_text()).get('sources',{}) if monitors_path.exists() else {}
    def read(relative):
        path=project/relative
        return json.loads(path.read_text()) if path.is_file() else {}
    for key,policy in policies.items():
        metadata=read(policy['metadata_path']) if policy.get('metadata_path') else {}
        if key not in readings:
            readings[key]={'reading_id':key,'label':policy['source'],'source':policy['source'],
                'source_url':policy.get('source_url'),'data_at_utc':metadata.get('data_at_utc') or metadata.get('acquired_at_utc'),
                'temporal_kind':'inventory_version' if policy.get('parent_reading') else 'observation',
                'quality_verified':bool(metadata) and metadata.get('connector_status','verified')=='verified',
                'qa':metadata.get('quality') or ('Metadades de font existents; consultar QA específic' if metadata else None)}
        item=readings[key]
        item['source']=policy['source']
        if policy.get('source_version'):
            item['source_version']=policy['source_version']
        if policy.get('artifact_path'):
            item['quality_verified']=(project/policy['artifact_path']).is_file()
        if key=='integrated_fire_danger':
            item['temporal_kind']='mixed_period_derived'
            item['quality_verified']=metadata.get('status')=='verified_analysis'
            item['value']=metadata.get('statistics',{}).get('median')
        if item.get('temporal_kind')=='inventory_version':
            item['source_version']=policy.get('source_version') or metadata.get('coverage_id') or metadata.get('version') or metadata.get('source') or metadata.get('font')
            item['source_retrieved_at_utc']=metadata.get('query_date') or metadata.get('data_consulta') or metadata.get('date_consulted')
        prior=previous.get('readings',{}).get(key,{}).get('freshness',{})
        # Seed the last official validation from the local XEMA series; never
        # confuse its retrieval date with the observation date.
        variable={'air_temperature':'32','relative_humidity':'33','wind':'30','wind_gust':'50'}.get(key)
        if variable and not prior.get('last_validated_data_at_utc'):
            filename='CJ_wind_observations.csv' if key in {'wind','wind_gust'} else 'Y4_observations.csv'
            path=project/'raw/meteocat_xema'/filename
            if path.exists():
                with path.open() as stream:
                    rows=[row for row in csv.DictReader(stream) if row.get('codi_estat')=='V' and row.get('codi_variable')==variable and instant(row.get('data_lectura')) and instant(row['data_lectura'])<=now]
                if rows:
                    row=max(rows,key=lambda row:instant(row['data_lectura']))
                    prior={**prior,'last_validated_data_at_utc':row['data_lectura'],'last_validated_value':row['valor_lectura']}
        check=checks.get(policy.get('check_key')) or monitors.get(key)
        item['freshness']=evaluate(item,policy,now,prior,check)
        if key in {'ndvi','ndmi','albedo'}:
            catalog=read('metadata/sentinel2_cdse_catalog_check.json')
            item['freshness']['candidate_count']=catalog.get('candidate_count')
            if catalog.get('connector_status')=='requires_credentials':
                item['freshness']['blocking_reason']='requires_credentials: CDSE Process API; candidats sense QA AOI'
        if key=='biodiversity' and any(metadata.get('download_limit_reached',{}).values()):
            item['freshness']['blocking_reason']='Mostreig truncat pel límit de descàrrega; no és inventari complet. '+str(item['freshness']['blocking_reason'] or '')
    missing=set(readings)-set(policies)
    if missing:
        raise ValueError('Lectures sense política: '+', '.join(sorted(missing)))
    # Surface old or pending inputs without modifying scores or exclusion formulas.
    for key,policy in policies.items():
        dependencies=policy.get('input_readings',[])
        blocked=[d for d in dependencies if readings[d]['freshness']['status'] in {'PENDENT QA','SENSE DADA','DESACTUALITZADA'}]
        readings[key]['freshness']['input_warnings']=blocked
        if key in {'precipitation_7d','precipitation_30d','days_without_significant_rain','thermal_comfort'} and any(readings[d]['freshness']['status']=='PENDENT QA' for d in dependencies):
            readings[key]['freshness']['status']='PENDENT QA'
            readings[key]['freshness']['new_valid_data']=False
            readings[key]['freshness']['last_validated_data_at_utc']=None
            readings[key]['freshness']['blocking_reason']='Entrades XEMA provisionals; acumulat o derivat pendent de validació de la font'
        if blocked and readings[key]['freshness']['status']=='ACTUAL':
            readings[key]['freshness']['status']='ÚLTIMA VALIDADA'
    return readings


def write_audit(project, registry):
    lines=['# Alinyà — vigència de totes les lectures','',
           'Avaluació local: '+registry['freshness_evaluated_at_utc']+'. La consulta no substitueix la data de dada.','',
           '| lectura | font | freqüència esperada | última dada validada | estat actual | automatització implementada | bloqueig si n’hi ha |',
           '|---|---|---|---|---|---|---|']
    for key,item in registry['readings'].items():
        f=item['freshness']; p=f['policy']
        date=f['last_validated_data_at_utc'] or ('edició: '+str(f['source_version']) if f.get('source_version') else 'data de dada no acreditada')
        if item.get('temporal_kind')=='multitemporal_composite':
            date=str(item.get('period_start_utc'))+' — '+str(item.get('period_end_utc'))+' (composició)'
        cells=[item.get('label') or key,item.get('source') or p['source'],p['expected_frequency'],date,f['status'],{'existing_daily_pipeline':'Circuit diari exist. + control de vigència local','version_watch_qa_gate':'Vigilància diària de catàleg; promoció QA pendent'}.get(p['automation'],p['automation']),f.get('blocking_reason') or '—']
        lines.append('| '+' | '.join(str(c).replace('|','/').replace('\n',' ') for c in cells)+' |')
    path=Path(project)/'reports/reading_freshness_audit.md'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('\n'.join(lines)+'\n')
