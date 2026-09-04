from __future__ import annotations

import tempfile
import unittest
import zipfile
import json
from datetime import date
from pathlib import Path

from PIL import Image

from wl_fechamento.local_import_service import (
    import_local_evidence,
    parse_exported_chat,
)


class LocalEvidenceImportTests(unittest.TestCase):
    def test_parses_android_and_ios_export_lines(self) -> None:
        messages = parse_exported_chat(
            "17/08/2026 08:30 - Ana: IMG-20260817-WA0001.jpg (arquivo anexado)\n"
            "[18/08/2026, 09:45] Bruno: <anexado: IMG-20260818-WA0002.jpg>"
        )
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].message_date, "17/08/2026")
        self.assertEqual(messages[1].sender, "Bruno")

    def test_imports_folder_and_associates_chat_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "exportacao"
            captures = root / "capturas"
            source.mkdir()
            Image.new("RGB", (40, 40), "orange").save(
                source / "IMG-20260817-WA0001.jpg"
            )
            (source / "_chat.txt").write_text(
                "17/08/2026 08:30 - Ana: IMG-20260817-WA0001.jpg (arquivo anexado)",
                encoding="utf-8",
            )
            result = import_local_evidence(
                source, date(2026, 8, 16), date(2026, 8, 31), captures
            )
            self.assertTrue(result.period_scan_complete)
            self.assertEqual(len(result.captured_attachments), 1)
            self.assertEqual(result.evidences[0].sender, "Ana")
            self.assertEqual(result.evidences[0].message_date, "17/08/2026")
            self.assertTrue(Path(result.captured_attachments[0].path).exists())
            self.assertTrue(Path(result.captured_attachments[0].path).parent.joinpath("sessao_whatsapp.json").exists())

    def test_imports_zip_without_whatsapp_browser(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "IMG-20260820-WA0003.jpg"
            Image.new("RGB", (40, 40), "orange").save(image)
            archive = root / "grupo.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.write(image, image.name)
            result = import_local_evidence(
                archive,
                date(2026, 8, 16),
                date(2026, 8, 31),
                root / "capturas",
            )
            self.assertEqual(len(result.captured_attachments), 1)
            self.assertEqual(result.evidences[0].message_date, "20/08/2026")
            self.assertEqual(result.group_name, "Pasta ou ZIP local")

    def test_zip_without_media_explains_that_images_were_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "sem_fotos.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr(
                    "chat.txt",
                    "[8/17/26, 8:06:33 AM] Ana: <imagem ocultada>",
                )
            with self.assertRaisesRegex(RuntimeError, "exportado sem as fotos"):
                import_local_evidence(
                    archive,
                    date(2026, 8, 16),
                    date(2026, 8, 31),
                    root / "capturas",
                )

    def test_folder_containing_one_zip_is_opened_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "pasta"
            source.mkdir()
            image = root / "IMG-20260820-WA0004.jpg"
            Image.new("RGB", (40, 40), "orange").save(image)
            with zipfile.ZipFile(source / "grupo.zip", "w") as zipped:
                zipped.write(image, image.name)
            result = import_local_evidence(
                source,
                date(2026, 8, 16),
                date(2026, 8, 31),
                root / "capturas",
            )
            self.assertEqual(len(result.captured_attachments), 1)

    def test_reuses_metadata_from_previous_saved_capture_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "captura_anterior"
            source.mkdir()
            Image.new("RGB", (40, 40), "orange").save(
                source / "ABC123_hash_foto_1.jpg"
            )
            (source / "sessao_whatsapp.json").write_text(json.dumps({
                "connected": True,
                "group_found": True,
                "start_date_found": True,
                "period_scan_complete": True,
                "start_date": "16/08/2026",
                "evidences": [{
                    "message_id": "ABC123",
                    "message_date": "22/08/2026",
                    "message_time": "10:15",
                    "sender": "Wilian",
                    "image_count": 1,
                }],
            }), encoding="utf-8")
            result = import_local_evidence(
                source,
                date(2026, 8, 16),
                date(2026, 8, 31),
                root / "novas_capturas",
            )
            self.assertEqual(result.evidences[0].message_date, "22/08/2026")
            self.assertEqual(result.evidences[0].sender, "Wilian")


if __name__ == "__main__":
    unittest.main()
