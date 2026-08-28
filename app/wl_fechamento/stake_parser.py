from __future__ import annotations

import re

from .models import StakeTextEntry


STAKE_PATTERN = re.compile(r"^\s*\d+(?:\s*[xX×+＝=]\s*\d+)+\s*$")


def parse_stake_text(value: str) -> StakeTextEntry:
    """Parseia entradas de Estaca com dois ou mais separadores.

    A peça é o primeiro número; a quantidade é sempre o penúltimo número
    multiplicado pelo último. Assim, ``16x10=600`` usa 10×600 e
    ``16x16x8+100`` usa 8×100.
    """
    if not STAKE_PATTERN.fullmatch(value or ""):
        raise ValueError(
            "Formato não reconhecido. Use, por exemplo, 16x10=600 ou 16x16x8+100. "
            "Nenhum valor foi calculado."
        )

    numbers = [int(item) for item in re.findall(r"\d+", value or "")]
    if len(numbers) < 3:
        raise ValueError(
            "Informe pelo menos três números: peça, penúltimo número e último número."
        )
    piece = str(numbers[0])
    multiplier = numbers[-2]
    base_value = numbers[-1]
    if multiplier <= 0 or base_value <= 0:
        raise ValueError("Penúltimo e último números devem ser maiores que zero.")

    return StakeTextEntry(
        piece=piece,
        multiplier=multiplier,
        base_value=base_value,
        quantity=multiplier * base_value,
    )
