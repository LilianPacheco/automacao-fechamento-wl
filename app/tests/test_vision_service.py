from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wl_fechamento.review_service import (
    _vision_analysis_to_draft,
    build_advanced_review_drafts,
)
from wl_fechamento.vision_service import (
    VisionAnalysis,
    VisionReading,
    apply_group_context,
    decide_fields,
    evaluate_against_reference,
)
from wl_fechamento.whatsapp_service import (
    WhatsAppAttachment,
    WhatsAppEvidence,
    WhatsAppProbeResult,
)


COMPLETE_LABEL = """Obra: TESTE GALPAO
Produto: PILAR
Secao: 40X60
Comprimento: 11,250
Peca: PH-16
Vol: 3,125"""


class VisionDecisionTests(unittest.TestCase):
    def test_two_independent_readings_confirm_each_explicit_field(self) -> None:
        decisions = decide_fields([
            VisionReading("motor_a", COMPLETE_LABEL, 0.91),
            VisionReading("motor_b", COMPLETE_LABEL, 0.87),
        ])

        self.assertEqual(decisions["piece"].value, "PH-16")
        self.assertEqual(
            decisions["piece"].status,
            "CONFIRMADO_AUTOMATICAMENTE",
        )
        self.assertEqual(
            decisions["unit_volume"].status,
            "CONFIRMADO_AUTOMATICAMENTE",
        )

    def test_single_reading_remains_pending(self) -> None:
        decisions = decide_fields([
            VisionReading("motor_a", COMPLETE_LABEL, 0.98),
        ])

        self.assertEqual(decisions["piece"].value, "PH-16")
        self.assertEqual(decisions["piece"].status, "PENDENTE")
        self.assertIn("Somente uma leitura", decisions["piece"].reason)

    def test_conflicting_piece_codes_remain_pending(self) -> None:
        decisions = decide_fields([
            VisionReading("motor_a", COMPLETE_LABEL, 0.91),
            VisionReading("motor_b", COMPLETE_LABEL.replace("PH-16", "PP-16"), 0.92),
        ])

        self.assertEqual(decisions["piece"].status, "PENDENTE")

    def test_isolated_number_is_not_accepted_as_volume(self) -> None:
        decisions = decide_fields([
            VisionReading("motor_a", "Produto: PILAR\n3,125", 0.95),
            VisionReading("motor_b", "Produto: PILAR\n3,125", 0.95),
        ])

        self.assertIsNone(decisions["unit_volume"].value)
        self.assertEqual(decisions["unit_volume"].status, "PENDENTE")

    def test_additional_isolated_field_pass_can_confirm_a_value(self) -> None:
        decisions = decide_fields([
            VisionReading("etiqueta_inteira", COMPLETE_LABEL, 0.88),
            VisionReading(
                "campo_isolado_length",
                "Comprimento (m): 11,25045634",
                0.93,
                field_hint="length",
            ),
        ])

        self.assertEqual(
            decisions["length"].status,
            "CONFIRMADO_AUTOMATICAMENTE",
        )

    def test_field_crop_keeps_volume_out_of_length(self) -> None:
        decisions = decide_fields([
            VisionReading("etiqueta_inteira", COMPLETE_LABEL, 0.88),
            VisionReading(
                "campo_isolado_length",
                "Comprimento (m): 11,25045634",
                0.93,
                field_hint="length",
            ),
            VisionReading(
                "campo_isolado_volume",
                "520 Vol. (m3): 3,125",
                0.94,
                field_hint="unit_volume",
            ),
        ])

        self.assertEqual(decisions["length"].value, "11,250")
        self.assertEqual(decisions["unit_volume"].value, 3.125)
        self.assertEqual(
            decisions["unit_volume"].status,
            "CONFIRMADO_AUTOMATICAMENTE",
        )

    def test_evaluation_counts_correct_automatic_fields(self) -> None:
        readings = [
            VisionReading("motor_a", COMPLETE_LABEL, 0.91),
            VisionReading("motor_b", COMPLETE_LABEL, 0.90),
        ]
        analysis = VisionAnalysis(
            source_path="foto.jpg",
            label_crop_path="etiqueta.png",
            fields=decide_fields(readings),
            readings=readings,
        )
        result = evaluate_against_reference(analysis, {
            "work": "TESTE GALPAO",
            "product": "PILAR",
            "piece": "PH-16",
            "section": "40X60",
            "length": "11,250",
            "unit_volume": 3.125,
        })

        self.assertEqual(result["confirmados_automaticamente"], 6)
        self.assertEqual(result["corretos"], 6)
        self.assertEqual(result["divergentes"], 0)
        self.assertEqual(result["precisao_automatica_percentual"], 100.0)

    def test_group_context_fills_only_safe_shared_fields(self) -> None:
        complete = VisionAnalysis(
            source_path="album-abc_aaaaaaaaaaaa_foto_1.jpg",
            label_crop_path="one.png",
            fields=decide_fields([
                VisionReading("a", COMPLETE_LABEL, 0.9),
                VisionReading("b", COMPLETE_LABEL, 0.9),
            ]),
            readings=[],
        )
        second = VisionAnalysis(
            source_path="album-abc_bbbbbbbbbbbb_foto_2.jpg",
            label_crop_path="two.png",
            fields=decide_fields([
                VisionReading("a", COMPLETE_LABEL.replace("PH-16", "PH-17"), 0.9),
                VisionReading("b", COMPLETE_LABEL.replace("PH-16", "PH-17"), 0.9),
            ]),
            readings=[],
        )
        partial = VisionAnalysis(
            source_path="album-abc_cccccccccccc_foto_3.jpg",
            label_crop_path="three.png",
            fields=decide_fields([
                VisionReading("a", "Peca: PP-10", 0.9),
                VisionReading("b", "Peca: PP-10", 0.9),
            ]),
            readings=[],
        )

        apply_group_context([complete, second, partial])

        self.assertEqual(partial.fields["work"].value, "TESTE GALPAO")
        self.assertEqual(partial.fields["product"].value, "PILAR")
        self.assertEqual(partial.fields["piece"].value, "PP-10")
        self.assertIsNone(partial.fields["section"].value)

    def test_pending_field_stays_pending_when_candidate_is_visible(self) -> None:
        readings = [VisionReading("motor_a", COMPLETE_LABEL, 0.95)]
        analysis = VisionAnalysis(
            source_path="foto.jpg",
            label_crop_path="etiqueta.png",
            fields=decide_fields(readings),
            readings=readings,
            product_type="PILAR",
        )
        result = WhatsAppProbeResult(
            connected=True,
            group_found=True,
            start_date_found=True,
            start_date="02/08/2026",
            evidences=[WhatsAppEvidence(
                message_id="msg-1",
                message_date="02/08/2026",
            )],
        )

        draft = _vision_analysis_to_draft(analysis, result, "msg-1")

        self.assertEqual(draft.piece, "PH-16")
        self.assertEqual(draft.status, "CONFIRMAR")
        self.assertIn("Confirmar peça", draft.warnings)

    def test_advanced_flow_writes_the_cache_consumed_by_html_review(self) -> None:
        readings = [
            VisionReading("motor_a", COMPLETE_LABEL, 0.95),
            VisionReading("motor_b", COMPLETE_LABEL, 0.94),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            image_path = Path(temporary) / "album-x_aaaaaaaaaaaa_foto_1.jpg"
            image_path.write_bytes(b"test-image")
            analysis = VisionAnalysis(
                source_path=str(image_path),
                label_crop_path="etiqueta.png",
                fields=decide_fields(readings),
                readings=readings,
                product_type="PILAR",
            )
            result = WhatsAppProbeResult(
                connected=True,
                group_found=True,
                start_date_found=True,
                start_date="02/08/2026",
                evidences=[WhatsAppEvidence(
                    message_id="msg-1",
                    message_date="02/08/2026",
                )],
                captured_attachments=[WhatsAppAttachment(
                    message_id="msg-1",
                    filename=image_path.name,
                    mime_type="image/jpeg",
                    path=str(image_path),
                    size=10,
                    sha256="abc123",
                )],
            )

            with patch(
                "wl_fechamento.review_service.analyze_image",
                return_value=analysis,
            ):
                drafts = build_advanced_review_drafts(result)

            review_cache = Path(temporary) / "revisao_temporaria.json"
            payload = json.loads(review_cache.read_text(encoding="utf-8"))
            self.assertEqual(len(drafts), 1)
            self.assertEqual(drafts[0].piece, "PH-16")
            self.assertEqual(
                payload["msg-1:abc123"][0]["status"],
                "PRONTO PARA REVISÃO",
            )
            self.assertTrue(
                (Path(temporary) / "analise_visual_v2" / "abc123.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
