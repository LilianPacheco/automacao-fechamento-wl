from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


class ReviewHtmlBehaviorTests(unittest.TestCase):
    def test_whatsapp_caption_quantity_parser(self) -> None:
        parser_path = (
            Path(__file__).resolve().parents[1]
            / "chrome_extension"
            / "quantity.js"
        )
        program = (
            "const {parseQuantityHint}=require(process.argv[1]);"
            "console.log(JSON.stringify(["
            "parseQuantityHint('Wilian Socio\\n21\\n15:52'),"
            "parseQuantityHint('Wilian Socio\\n15:52'),"
            "parseQuantityHint('12,5')]))"
        )
        completed = subprocess.run(
            ["node", "-e", program, str(parser_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )

        self.assertEqual(json.loads(completed.stdout), [21, None, 12.5])

    def test_manifest_loads_quantity_parser_before_reader(self) -> None:
        manifest_path = (
            Path(__file__).resolve().parents[1]
            / "chrome_extension"
            / "manifest.json"
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["content_scripts"][0]["js"],
            ["quantity.js", "content_v185.js"],
        )

    def test_only_situation_select_changes_card_status(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "render_current_html_review.py"
        ).read_text(encoding="utf-8")

        self.assertIn("querySelectorAll('select[data-status]')", script)
        self.assertNotIn("querySelectorAll('[data-status]')", script)

    def test_explicit_pending_status_is_not_auto_confirmed(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "render_current_html_review.py"
        ).read_text(encoding="utf-8")

        self.assertIn('if value in {"CONFIRMAR", "PENDENTE"}', script)
        self.assertIn('return "PENDENTE"', script)

    def test_renderer_uses_the_explicit_period_source(self) -> None:
        script = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "render_current_html_review.py"
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "current" / "revisao_temporaria.json"
            source.parent.mkdir()
            source.write_text(json.dumps([{
                "message_date": "18/08/2026",
                "work": "OBRA ATUAL",
                "product": "PILAR",
                "piece": "PH-99",
                "section": "40X40",
                "length": "8,000",
                "dimensions": "40X40 8,000",
                "unit_volume": 1.25,
                "type_name": "PILAR",
                "quantity": 1,
                "status": "PRONTO PARA REVISÃO",
                "warnings": [],
            }]), encoding="utf-8")
            output = root / "review-output"

            completed = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--source", str(source),
                    "--period-key", "2026-08_2a-quinzena",
                    "--output-dir", str(output),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )

            html_path = Path(completed.stdout.strip().splitlines()[-1])
            page = html_path.read_text(encoding="utf-8")
            self.assertIn("2026-08_2a-quinzena", page)
            self.assertIn("18/08/2026", page)
            self.assertIn("PH-99", page)


if __name__ == "__main__":
    unittest.main()
