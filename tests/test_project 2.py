from pathlib import Path
import json
import tempfile
import unittest

from ecoradar.core.project import create_project_workspace, slugify_site_name


class ProjectWorkspaceTest(unittest.TestCase):
    def test_slugify_site_name(self):
        self.assertEqual(slugify_site_name("Muntanya d'Alinya"), "muntanya-d-alinya")

    def test_create_project_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = create_project_workspace(
                "Espai Test",
                root=tmpdir,
                municipality="Municipi",
                comarca="Comarca",
            )

            self.assertTrue(workspace.root.exists())
            self.assertTrue((workspace.root / "area_estudi").is_dir())
            self.assertTrue((workspace.root / "data" / "raw").is_dir())
            self.assertTrue((workspace.root / "metadata" / "project_manifest.json").is_file())

            manifest = json.loads(workspace.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["project_id"], "espai-test")
            self.assertEqual(manifest["site_name"], "Espai Test")
            self.assertEqual(manifest["municipality"], "Municipi")
            self.assertEqual(manifest["comarca"], "Comarca")


if __name__ == "__main__":
    unittest.main()

