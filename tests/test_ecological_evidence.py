"""Synthetic raster tests; these are not environmental observations."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
MODULE_PATH = Path(__file__).resolve().parents[1] / 'tools' / 'export_ecoradar_alinya_netlify.py'
spec = importlib.util.spec_from_file_location('ecology_exporter', MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        (self.project/'indicators').mkdir()
        (self.project/'processed/teledeteccio').mkdir(parents=True)
        self.meta={'acquired_at_utc':'2026-07-07T10:00:00Z','source_scene':'synthetic-test-only','valid_pixels':4,'methods':{'quality_mask':'synthetic mask'},'metrics':{'ndvi':{'median':0.5,'mean':0.5},'ndmi':{'median':0.25,'mean':0.25}}}
        self.write_meta()
        for name,value in [('ndvi',0.5),('ndmi',0.25)]:
            with rasterio.open(self.project/f'processed/teledeteccio/{name}.tif','w',driver='GTiff',width=2,height=2,count=1,dtype='float32',crs='EPSG:25831',transform=from_origin(300000,4600000,20,20),nodata=-9999) as dst:
                dst.write(np.full((2,2),value,dtype='float32'),1)
    def tearDown(self): self.temp.cleanup()
    def write_meta(self): (self.project/'indicators/teledeteccio_sentinel2.json').write_text(json.dumps(self.meta))
    def test_matching_rasters(self):
        result=module.build_ecological_evidence(self.project)
        self.assertEqual(set(result),{'vigor','moisture'})
        self.assertEqual(result['vigor']['grid_id'],result['moisture']['grid_id'])
        self.assertEqual(result['vigor']['mask_id'],result['moisture']['mask_id'])
        self.assertEqual(result['vigor']['resolution'],[20,20])
    def test_summary_mismatch_blocks_only_affected_source(self):
        self.meta['metrics']['ndmi']['median']=0.8;self.write_meta()
        self.assertEqual(set(module.build_ecological_evidence(self.project)),{'vigor'})
    def test_missing_quality_or_wrong_valid_count_blocks_evidence(self):
        self.meta['valid_pixels']=3;self.write_meta();self.assertEqual(module.build_ecological_evidence(self.project),{})
        self.meta['valid_pixels']=4;self.meta['methods']={};self.write_meta();self.assertEqual(module.build_ecological_evidence(self.project),{})
    def test_missing_files_are_explicitly_empty(self):
        self.assertEqual(module.build_ecological_evidence(self.project/'absent'),{})
    def test_contrasts_use_actual_paired_pixels(self):
        for name,values in [('ndvi',[0.2,0.4,0.6,0.8]),('ndmi',[0.4,0.3,0.2,0.1])]:
            with rasterio.open(self.project/f'processed/teledeteccio/{name}.tif','r+') as dst:
                dst.write(np.array(values,dtype='float32').reshape(2,2),1)
        result=module.build_ecological_evidence(self.project)
        contrast=result['vigor']['spatial_contrasts'][0]
        self.assertEqual(contrast['peer'],'moisture')
        self.assertAlmostEqual(contrast['low_peer_median'],0.4,places=6)
        self.assertAlmostEqual(contrast['high_peer_median'],0.1,places=6)
        self.assertEqual(contrast['low_pixels'],1)
        self.assertEqual(contrast['high_pixels'],1)
    def test_flat_rasters_do_not_fabricate_extreme_sectors(self):
        result=module.build_ecological_evidence(self.project)
        self.assertNotIn('spatial_contrasts',result['vigor'])
    def test_different_grids_never_produce_paired_contrasts(self):
        for name,values in [('ndvi',[0.2,0.4,0.6,0.8]),('ndmi',[0.4,0.3,0.2,0.1])]:
            with rasterio.open(self.project/f'processed/teledeteccio/{name}.tif','r+') as dst:
                dst.write(np.array(values,dtype='float32').reshape(2,2),1)
                if name=='ndmi':dst.transform=from_origin(300020,4600000,20,20)
        result=module.build_ecological_evidence(self.project)
        self.assertEqual(result['vigor']['spatial_contrasts'],[])
if __name__=='__main__': unittest.main()
