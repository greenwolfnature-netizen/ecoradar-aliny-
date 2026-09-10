from __future__ import annotations

import csv
import json
import re
from pathlib import Path
import tempfile
import unittest

from pypdf import PdfReader
from tools.build_alinya_public_site import build_public_site


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projectes" / "Alinya"
REPORTS = PROJECT / "reports"
METHODOLOGY = "alinya_core_v2_2026-09-09"

FORBIDDEN_PATTERNS = (
    r"Favorable però vulnerable",
    r"Restauració\s+74(?:\D|$)",
    r"Pèrdua de mosaic\s+71(?:\D|$)",
    r"Pressió d['’]?ús\s+49(?:\D|$)",
    r"Alteració de l['’]?aigua\s+47(?:\D|$)",
    r"Risc d['’]?incendi\s+44(?:\D|$)",
    r"Vulnerabilitat\s+37(?:\D|$)",
    r"731\s+cites públiques",
    r"resiliència al foc\s+44/100",
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pdf_text(path: Path) -> tuple[list[str], str]:
    pages = [page.extract_text() or "" for page in PdfReader(str(path)).pages]
    return pages, "\n".join(pages)


def normalized(text: str) -> str:
    for mark in ("·", "–", "—", "‑", "•"):
        text = text.replace(mark, "-")
    return " ".join(text.split())


class AlinyaPhase2PublicArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical = read_json(PROJECT / "indicators" / "ecoradar_core_indicators.json")
        cls.by_code = {item["code"]: item for item in cls.canonical["indicators"]}

    def assert_no_legacy_results(self, text: str, label: str) -> None:
        for pattern in FORBIDDEN_PATTERNS:
            self.assertIsNone(re.search(pattern, text, flags=re.IGNORECASE), f"{label}: {pattern}")

    def test_active_core_aliases_are_exact_phase2_copies(self):
        canonical_json = PROJECT / "indicators" / "ecoradar_core_indicators.json"
        canonical_csv = PROJECT / "indicators" / "ecoradar_core_indicators.csv"
        self.assertEqual(self.canonical["methodology_version"], METHODOLOGY)
        self.assertTrue(self.canonical.get("snapshot_id"))
        for relative in ("indicators/ecoradar_core.json", "indicators/ecoradar_indicators.json"):
            self.assertEqual(read_json(PROJECT / relative), self.canonical, relative)
        for relative in ("indicators/ecoradar_core.csv", "indicators/ecoradar_indicators_summary.csv"):
            self.assertEqual((PROJECT / relative).read_bytes(), canonical_csv.read_bytes(), relative)
        self.assertTrue(all(item["value_0_100"] is None for item in self.canonical["indicators"]))
        self.assertEqual(canonical_json.read_text(encoding="utf-8"), (PROJECT / "indicators/ecoradar_core.json").read_text(encoding="utf-8"))

    def test_biodiversity_and_accessibility_use_the_phase2_universe(self):
        biodiversity = self.by_code["CORE_06"]
        access = self.by_code["CORE_07"]
        self.assertEqual(biodiversity["profile"]["records_normalized"], 3680)
        self.assertEqual(biodiversity["profile"]["knowledge_grid_1km"]["cells_with_records"], 66)
        self.assertEqual(biodiversity["profile"]["knowledge_grid_1km"]["cells"], 84)
        self.assertEqual(access["primary_result"], "124,8 km · 2,28 km/km² · 18 punts")
        with (PROJECT / "indicators" / "ecoradar_01_resum.csv").open(encoding="utf-8", newline="") as handle:
            basic = {row["indicador"]: row for row in csv.DictReader(handle)}
        self.assertEqual(basic["nombre_registres_biodiversitat"]["valor"], "3680")

    def test_core11_and_core12_keep_the_approved_decision_contract(self):
        core11 = self.by_code["CORE_11"]
        core12 = self.by_code["CORE_12"]
        self.assertEqual(core11["status"], "NO AVALUABLE")
        self.assertIn("falta diagnosi de degradació", core11["primary_result"])
        self.assertEqual(core12["profile"]["result"], "SENSE PRIORITAT ÚNICA")
        results = [row["result"] for row in core12["profile"]["rows"]]
        self.assertEqual(results.count("P1"), 1)
        self.assertEqual(results.count("P2"), 4)
        self.assertEqual(results.count("NO AVALUABLE"), 1)
        self.assertIsNone(core12["profile"]["global_score"])

    def test_current_diagnosis_alias_cannot_recover_the_old_version(self):
        current = read_json(PROJECT / "diagnosis" / "ecoradar_diagnosis.json")
        alias = read_json(PROJECT / "metadata" / "ecoradar_diagnosis.json")
        self.assertEqual(alias, current)
        self.assertEqual(current["methodology_version"], METHODOLOGY)

    def test_current_recommendation_aliases_cannot_recover_the_old_version(self):
        current = read_json(PROJECT / "recommendations" / "recommendations.json")
        alias = read_json(PROJECT / "metadata" / "ecoradar_recommendations.json")
        self.assertEqual(alias, current)
        self.assertEqual(current["methodology_version"], METHODOLOGY)
        self.assertEqual(current["snapshot_id"], self.canonical["snapshot_id"])
        self.assertEqual(
            (PROJECT / "indicators" / "ecoradar_recommendations.csv").read_bytes(),
            (PROJECT / "recommendations" / "priority_matrix.csv").read_bytes(),
        )

    def test_public_text_artifacts_have_no_legacy_results(self):
        paths = [
            ROOT / "index.html",
            PROJECT / "maps" / "ecoradar_alinya_interactiu-v2.html",
            PROJECT / "maps" / "ecoradar-alinya-netlify-v2" / "index.html",
            PROJECT / "maps" / "ecoradar_memoria_foc_alinya_interactiu.html",
            ROOT / "README.md",
            ROOT / "docs" / "deployment" / "alinya_github_repository_readme.md",
        ]
        paths.extend(sorted((PROJECT / "maps" / "ecoradar_core").glob("core_*.md")))
        for path in paths:
            self.assertTrue(path.exists(), path)
            self.assert_no_legacy_results(path.read_text(encoding="utf-8"), str(path))
        fire_viewer = (PROJECT / "maps" / "ecoradar_memoria_foc_alinya_interactiu.html").read_text(encoding="utf-8")
        self.assertIn(METHODOLOGY, fire_viewer)
        self.assertIn("SENSE PRIORITAT ÚNICA", fire_viewer)
        self.assertIn('"records": 3680', fire_viewer)

    def test_all_phase2_pdfs_are_current_and_complete(self):
        pdfs = {
            "fitxa": (REPORTS / "fitxa_ecoradar_alinya_a4.pdf", 1),
            "fitxa_alias": (REPORTS / "fitxa_ecoradar_alinya_v1.pdf", 1),
            "client": (REPORTS / "informe_ecoradar_alinya_a4_client.pdf", 5),
            "body": (REPORTS / "informe_ecoradar_alinya_plantilla_urba_cos.pdf", 5),
            "complete": (REPORTS / "informe_complet_muntanya_alinya.pdf", 6),
        }
        extracted: dict[str, tuple[list[str], str]] = {}
        for label, (path, expected_pages) in pdfs.items():
            self.assertTrue(path.exists(), path)
            pages, text = pdf_text(path)
            extracted[label] = pages, text
            self.assertEqual(len(pages), expected_pages, label)
            self.assert_no_legacy_results(text, label)
        self.assertEqual(pdfs["fitxa"][0].read_bytes(), pdfs["fitxa_alias"][0].read_bytes())

        fitxa_text = normalized(extracted["fitxa"][1])
        for expected in (
            "SENSE PRIORITAT ÚNICA",
            "1 P1 · 4 P2 · 1 NO AVALUABLE",
            "3.680 registres · 66/84 cel·les amb dades",
            "124,8 km · 2,28 km/km² · 18 punts",
            "falta diagnosi de degradació",
        ):
            self.assertIn(normalized(expected), fitxa_text)

        client_text = normalized(extracted["client"][1])
        for item in self.canonical["indicators"]:
            self.assertIn(item["code"].replace("CORE_", "RADAR_"), client_text)
            self.assertIn(normalized(item["primary_result"]), client_text)
        self.assertIn("SENSE PRIORITAT ÚNICA", normalized(extracted["complete"][0][-1]))

    def test_public_bundle_contains_only_current_allowlisted_outputs(self):
        netlify_config = (ROOT / "netlify.toml").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/update-current-fire-danger.yml").read_text(encoding="utf-8")
        self.assertIn('publish = "public"', netlify_config)
        self.assertIn('command = "python3 tools/build_alinya_public_site.py"', netlify_config)
        self.assertIn("netlify-cli deploy --prod --dir public", workflow)
        with tempfile.TemporaryDirectory() as temporary:
            public = build_public_site(Path(temporary) / "public")
            self.assertEqual((public / "index.html").read_bytes(), (ROOT / "index.html").read_bytes())
            self.assertFalse(any(public.rglob("*.py")))
            self.assertFalse((public / "ecoradar-alinya-github-repository-complet").exists())
            self.assertFalse((public / "projectes" / "Alinya" / "legacy_outputs").exists())
            for path in public.rglob("*"):
                if not path.is_file():
                    continue
                if path.suffix.lower() == ".pdf":
                    self.assert_no_legacy_results(pdf_text(path)[1], str(path))
                elif path.suffix.lower() in {".html", ".json", ".jsonl", ".csv", ".md", ".js"}:
                    self.assert_no_legacy_results(path.read_text(encoding="utf-8"), str(path))


if __name__ == "__main__":
    unittest.main()
