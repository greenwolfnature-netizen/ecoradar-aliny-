#!/usr/bin/env python3
"""Daily publication watch. A changed catalogue is a QA candidate, never validated data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse, urlencode

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'projectes/Alinya'
OUTPUT=PROJECT/'metadata/source_version_checks.json'


def check(url, checked, previous):
    record={'url':url,'checked_at_utc':checked,'status':'pending_verification',
            'note':'Vigilància de publicació; no substitueix el QA de dades ni acredita una nova edició.'}
    if not url or urlparse(url).scheme!='https':
        return {**record,'status':'blocked','note':'Endpoint de publicació no documentat.'}
    try:
        request=Request(url,headers={'User-Agent':'EcoRadar-source-publication-watch/1.0'})
        with urlopen(request,timeout=20) as response:
            data=response.read(2_000_001)
            if len(data)>2_000_000:
                return {**record,'note':'Catàleg supera el límit de lectura; comprovació de versió pendent.'}
            digest=hashlib.sha256(data).hexdigest()
            record.update(http_status=response.status,publication_sha256=digest,
                          etag=response.headers.get('ETag'),last_modified=response.headers.get('Last-Modified'),
                          publication_changed=bool(previous.get('publication_sha256') and previous['publication_sha256']!=digest))
            record['note']='Canvi al catàleg: pendent de QA i promoció.' if record['publication_changed'] else 'Catàleg accessible; edició vigent no acreditada automàticament.'
    except Exception as error:
        record.update(status='service_unavailable',note=type(error).__name__+': consulta de publicació fallida; conservada última validada.')
    return record


def main():
    policies=json.loads((ROOT/'config/alinya_reading_policies.json').read_text())['readings']
    previous=json.loads(OUTPUT.read_text()).get('sources',{}) if OUTPUT.exists() else {}
    checked=os.environ.get('ECORADAR_CHECKED_AT_UTC') or datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    groups={}
    for key,policy in policies.items():
        if policy['automation']!='version_watch_qa_gate':
            continue
        url=policy.get('source_url')
        if url and '/wfs' in url and '?' not in url:
            url+='?'+urlencode({'service':'WFS','request':'GetCapabilities'})
        if url and '/wms' in url and '?' not in url:
            url+='?'+urlencode({'service':'WMS','request':'GetCapabilities'})
        groups.setdefault(url,[]).append(key)
        for index,additional in enumerate(policy.get("additional_source_urls",[])):
            groups.setdefault(additional,[]).append(key+"::"+str(index+1))
    with ThreadPoolExecutor(max_workers=4) as executor:
        results=list(executor.map(lambda pair:(pair[1],check(pair[0],checked,previous.get(pair[1][0],{}))),groups.items()))
    payload={'checked_at_utc':checked,'sources':{key:result for keys,result in results for key in keys}}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v['status'] for k,v in payload['sources'].items()},ensure_ascii=False))

if __name__=='__main__':
    main()
