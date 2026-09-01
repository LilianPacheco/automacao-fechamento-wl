from __future__ import annotations

import unittest

from wl_fechamento.vision_service import (
    VisionAnalysis,
    VisionReading,
    decide_fields,
    evaluate_against_reference,
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


if __name__ == "__main__":
    unittest.main()
