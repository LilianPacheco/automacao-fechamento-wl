from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wl_fechamento.review_service import (
    _stake_delivery_layout_drafts,
    _vision_analysis_to_draft,
    build_advanced_review_drafts,
)
from wl_fechamento.vision_service import (
    VisionAnalysis,
    VisionReading,
    apply_group_context,
    decide_fields,
    evaluate_against_reference,
    _layout_field_readings,
)
from wl_fechamento.paddle_ocr_service import LayoutLine
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
    def test_stake_delivery_uses_meters_column_and_groups_dimension(self) -> None:
        def line(text, left, top, right):
            return LayoutLine(text, 0.99, left, top, right, top + 20)

        lines = [
            line("OBRA: MAP", 250, 70, 390),
            line("BIGUAÇU", 250, 95, 390),
            line("Peça", 10, 200, 90),
            line("Dimensão", 120, 200, 230),
            line("Quantidade", 280, 200, 400),
            line("Comprimento", 450, 200, 580),
            line("Metros", 650, 200, 730),
            line("Peso", 810, 200, 870),
            line("ESTACA", 10, 240, 90), line("20x20", 140, 240, 210),
            line("4", 330, 240, 345), line("8,00", 490, 240, 540),
            line("32", 675, 240, 705), line("0,80", 820, 240, 860),
            line("ESTACA", 10, 280, 90), line("20x20", 140, 280, 210),
            line("4", 330, 280, 345), line("10,00", 490, 280, 550),
            line("40", 675, 280, 705), line("1,00", 820, 280, 860),
            line("ESTACA", 10, 320, 90), line("23x23", 140, 320, 210),
            line("20", 325, 320, 350), line("8,00", 490, 320, 540),
            line("160", 670, 320, 710), line("1,05", 820, 320, 860),
        ]
        result = WhatsAppProbeResult(
            connected=True, group_found=True, start_date_found=True,
            start_date="17/08/2026",
            evidences=[WhatsAppEvidence("msg-1", "17/08/2026")],
        )

        drafts = _stake_delivery_layout_drafts(lines, result, "msg-1", "foto.jpg")

        self.assertEqual([(item.section, item.quantity) for item in drafts], [
            ("20X20", 72), ("23X23", 160),
        ])
        self.assertTrue(all(item.product == "ESTACA" for item in drafts))
        self.assertTrue(all(item.unit_volume is None for item in drafts))
        self.assertTrue(all(item.work == "MAP BIGUAÇU" for item in drafts))
        self.assertTrue(all(item.status == "PRONTO PARA REVISÃO" for item in drafts))

    def test_layout_keeps_length_and_volume_in_their_own_rows(self) -> None:
        lines = [
            LayoutLine("Comprimento", 0.98, 10, 100, 130, 125),
            LayoutLine("11,291", 0.97, 160, 100, 230, 125),
            LayoutLine("Vol. (m3)", 0.96, 310, 160, 390, 185),
            LayoutLine("1,340", 0.95, 420, 160, 475, 185),
        ]

        readings = _layout_field_readings(lines)
        values = {
            reading.field_hint: reading.text for reading in readings
        }

        self.assertIn("11,291", values["length"])
        self.assertIn("1,340", values["unit_volume"])

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

    def test_high_confidence_explicit_measurement_can_be_confirmed(self) -> None:
        decisions = decide_fields([
            VisionReading("motor_neural", COMPLETE_LABEL, 0.93),
        ])

        self.assertEqual(
            decisions["length"].status,
            "CONFIRMADO_AUTOMATICAMENTE",
        )
        self.assertEqual(decisions["piece"].status, "PENDENTE")

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

    def test_advanced_flow_includes_textual_stake_entry(self) -> None:
        readings = [VisionReading("motor_a", COMPLETE_LABEL, 0.95)]
        with tempfile.TemporaryDirectory() as temporary:
            image_path = Path(temporary) / "foto.jpg"
            image_path.write_bytes(b"test-image")
            analysis = VisionAnalysis(
                source_path=str(image_path), label_crop_path="etiqueta.png",
                fields=decide_fields(readings), readings=readings,
                product_type="PILAR",
            )
            result = WhatsAppProbeResult(
                connected=True, group_found=True, start_date_found=True,
                start_date="20/08/2026",
                evidences=[
                    WhatsAppEvidence("msg-foto", "20/08/2026"),
                    WhatsAppEvidence(
                        "msg-estaca", "20/08/2026",
                        message_text="16x16x8+100", stake_text="16x16x8+100",
                    ),
                ],
                captured_attachments=[WhatsAppAttachment(
                    "msg-foto", image_path.name, "image/jpeg", str(image_path),
                    10, "abc123",
                )],
            )
            with patch("wl_fechamento.review_service.analyze_image", return_value=analysis):
                drafts = build_advanced_review_drafts(result)

            stake = next(item for item in drafts if item.message_id == "msg-estaca")
            self.assertEqual(stake.piece, "16")
            self.assertEqual(stake.quantity, 800)
            self.assertIn("Confirmar obra", stake.warnings)
            self.assertTrue(stake.record_id.startswith("wl-"))

    def test_reprocessing_preserves_pending_manual_review(self) -> None:
        readings = [VisionReading("motor_a", COMPLETE_LABEL, 0.95)]
        with tempfile.TemporaryDirectory() as temporary:
            image_path = Path(temporary) / "foto.jpg"
            image_path.write_bytes(b"test-image")
            analysis = VisionAnalysis(
                source_path=str(image_path), label_crop_path="etiqueta.png",
                fields=decide_fields(readings), readings=readings,
                product_type="PILAR",
            )
            result = WhatsAppProbeResult(
                connected=True, group_found=True, start_date_found=True,
                start_date="20/08/2026",
                evidences=[WhatsAppEvidence("msg-1", "20/08/2026")],
                captured_attachments=[WhatsAppAttachment(
                    "msg-1", image_path.name, "image/jpeg", str(image_path),
                    10, "abc123",
                )],
            )
            with patch("wl_fechamento.review_service.analyze_image", return_value=analysis):
                build_advanced_review_drafts(result)
            cache_path = Path(temporary) / "revisao_temporaria.json"
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            row = next(iter(payload.values()))[0]
            row["work"] = "OBRA CORRIGIDA"
            row["status"] = "PENDENTE"
            row["manual_fields"] = ["work"]
            cache_path.write_text(json.dumps(payload), encoding="utf-8")

            second = build_advanced_review_drafts(result)

            self.assertEqual(second[0].work, "OBRA CORRIGIDA")
            self.assertEqual(second[0].status, "PENDENTE")


if __name__ == "__main__":
    unittest.main()
