from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
