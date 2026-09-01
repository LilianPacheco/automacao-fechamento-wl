from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


class ReviewHtmlBehaviorTests(unittest.TestCase):
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
