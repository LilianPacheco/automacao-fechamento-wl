from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


MONTH_NAMES = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

MONTH_NUMBERS = {name: number for number, name in MONTH_NAMES.items()}


@dataclass(frozen=True)
class PeriodSelection:
    year: int
    month: int
    fortnight: int

    def __post_init__(self) -> None:
        if self.month not in MONTH_NAMES:
            raise ValueError("Mês inválido.")
        if self.fortnight not in (1, 2):
            raise ValueError("A quinzena deve ser 1 ou 2.")
        if self.year < 2020 or self.year > 2100:
            raise ValueError("Ano inválido.")

    @property
    def start_date(self) -> date:
        return date(self.year, self.month, 1 if self.fortnight == 1 else 16)

    @property
    def end_date(self) -> date:
        if self.fortnight == 1:
            return date(self.year, self.month, 15)
        if self.month == 12:
            next_month = date(self.year + 1, 1, 1)
        else:
            next_month = date(self.year, self.month + 1, 1)
        return date.fromordinal(next_month.toordinal() - 1)

    @property
    def sheet_name(self) -> str:
        ordinal = "1ª" if self.fortnight == 1 else "2ª"
        return f"{ordinal} quinz.{MONTH_NAMES[self.month]}"

    @property
    def label(self) -> str:
        return (
            f"{self.start_date.strftime('%d/%m/%Y')} a "
            f"{self.end_date.strftime('%d/%m/%Y')}"
        )

    @property
    def review_key(self) -> str:
        """Stable identifier used to isolate captures and reviews by period."""
        return f"{self.year:04d}-{self.month:02d}_{self.fortnight}a-quinzena"


@dataclass(frozen=True)
class StakeTextEntry:
    piece: str
    multiplier: int
    base_value: int
    quantity: int
    type_name: str = "ESTACA"
    dimensions: str = ""
    unit_volume: None = None
    cargo_type: str = "PEÇAS ESTOQUE"


@dataclass
class WorkbookValidation:
    path: Path
    valid: bool
    target_sheet: str
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppConfiguration:
    workbook_path: str = ""
    last_year: int = datetime.now().year
    last_month: int = datetime.now().month
    last_fortnight: int = 1 if datetime.now().day <= 15 else 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "workbook_path": self.workbook_path,
            "last_year": self.last_year,
            "last_month": self.last_month,
            "last_fortnight": self.last_fortnight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfiguration":
        return cls(
            workbook_path=str(data.get("workbook_path", "")),
            last_year=int(data.get("last_year", datetime.now().year)),
            last_month=int(data.get("last_month", datetime.now().month)),
            last_fortnight=int(data.get("last_fortnight", 1)),
        )
