import copy
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from alinya_reading_freshness import evaluate, fingerprint, apply_policies

class ReadingFreshnessTest(unittest.TestCase):
    now=datetime(2026,9,10,12,tzinfo=timezone.utc)
    policy={'max_age_hours':2}
    def item(self,**kwargs):
        return {'reading_id':'air_temperature','value':12,'data_at_utc':'2026-09-10T11:00:00Z','quality_verified':True,'qa':'validada',**kwargs}
    def test_same_day_can_be_stale(self):
        f=evaluate(self.item(data_at_utc='2026-09-10T04:00:00Z'),self.policy,self.now)
        self.assertEqual(f['status'],'DESACTUALITZADA')
    def test_check_does_not_create_new_valid_data(self):
        first=evaluate(self.item(),self.policy,self.now)
        second=evaluate(self.item(),self.policy,self.now,first)
        self.assertEqual(second['status'],'ÚLTIMA VALIDADA')
        self.assertFalse(second['new_valid_data'])
    def test_provisional_retains_last_validation(self):
        first=evaluate(self.item(),self.policy,self.now)
        second=evaluate(self.item(qa='provisional XEMA',value=14),self.policy,self.now,first)
        self.assertEqual(second['status'],'PENDENT QA')
        self.assertEqual(second['last_validated_value'],12)
        self.assertFalse(second['new_valid_data'])
    def test_composite_never_current(self):
        f=evaluate(self.item(temporal_kind='multitemporal_composite',data_at_utc=None,period_end_utc='2026-09-10T11:00:00Z'),self.policy,self.now)
        self.assertEqual(f['status'],'ÚLTIMA VALIDADA')
    def test_future_observation_rejected(self):
        self.assertEqual(evaluate(self.item(data_at_utc='2026-09-11T12:00:00Z'),self.policy,self.now)['status'],'PENDENT QA')
    def test_metadata_checks_do_not_change_content_identity(self):
        self.assertEqual(fingerprint({'value':3,'checked_at_utc':'a','nested':{'snapshot_id':'a'}}),fingerprint({'value':3,'checked_at_utc':'b','nested':{'snapshot_id':'b'}}))
        self.assertNotEqual(fingerprint({'value':3}),fingerprint({'value':4}))
    def test_unknown_reading_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'sense política'):
            apply_policies(ROOT/'projectes/Alinya',{'unknown':{}},{},{},self.now)
    def test_complete_registry_has_policy_and_does_not_modify_values(self):
        registry=json.loads((ROOT/'projectes/Alinya/metadata/reading_registry.json').read_text())
        original=copy.deepcopy(registry['readings'])
        daily=json.loads((ROOT/'projectes/Alinya/indicators/daily_readings.json').read_text())
        result=apply_policies(ROOT/'projectes/Alinya',registry['readings'],daily,registry,self.now)
        for key,item in result.items():
            self.assertIn('freshness',item)
            if key in original:
                self.assertEqual(item.get('value'),original[key].get('value'))
    def test_missing_candidate_keeps_last_validated(self):
        first=evaluate(self.item(),self.policy,self.now)
        second=evaluate(self.item(quality_verified=False,value=None),self.policy,self.now,first)
        self.assertEqual(second['status'],'ÚLTIMA VALIDADA')
        self.assertEqual(second['last_validated_value'],12)

    def test_source_outage_is_visible(self):
        f=evaluate(self.item(),self.policy,self.now,source_check={'status':'service_unavailable'})
        self.assertEqual(f['status'],'ÚLTIMA VALIDADA')
        self.assertEqual(f['blocking_reason'],'service_unavailable')

if __name__=='__main__':unittest.main()
