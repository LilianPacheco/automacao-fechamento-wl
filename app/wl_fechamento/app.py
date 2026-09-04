from __future__ import annotations

import tkinter as tk
import threading
import os
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .config import load_configuration, save_configuration
from .chrome_bridge import (
    load_latest_complete_whatsapp_session,
    probe_whatsapp_chrome,
)
from .models import MONTH_NAMES, MONTH_NUMBERS, AppConfiguration, PeriodSelection
from .label_parser import LabelDraft
from .local_import_service import import_local_evidence
from .grouping_service import ConsolidatedRow, group_approved_drafts
from .review_service import build_advanced_review_drafts
from .workbook_writer_service import write_approved_rows
from .stake_parser import parse_stake_text
from .whatsapp_service import WhatsAppProbeResult, restrict_result_to_period
from .workbook_service import validate_workbook


COLORS = {
    "navy": "#17365D",
    "blue": "#2F75B5",
    "light_blue": "#D9EAF7",
    "green": "#2E7D32",
    "light_green": "#E2F0D9",
    "amber": "#9C6500",
    "light_amber": "#FFF2CC",
    "red": "#9C0006",
    "light_red": "#FCE4D6",
    "background": "#F4F7FA",
    "card": "#FFFFFF",
    "text": "#1F2937",
    "muted": "#667085",
    "border": "#D0D5DD",
}


class FechamentoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Automação do Fechamento WL — Leitura Visual 2 — v0.4.2")
        self.geometry("1040x610+35+25")
        self.minsize(900, 550)
        self.configure(bg=COLORS["background"])

        self.config_data = load_configuration()
        self.workbook_var = tk.StringVar(value=self.config_data.workbook_path)
        self.month_var = tk.StringVar(
            value=MONTH_NAMES.get(self.config_data.last_month, "julho")
        )
        self.year_var = tk.StringVar(value=str(self.config_data.last_year))
        self.fortnight_var = tk.IntVar(value=self.config_data.last_fortnight)
        self.period_var = tk.StringVar(value="Selecione o período para validar.")
        self.status_var = tk.StringVar(value="Aguardando configuração")
        self.stake_input_var = tk.StringVar(value="16x10=600")
        self.stake_result_var = tk.StringVar(value="")
        self.last_whatsapp_result: WhatsAppProbeResult | None = None
        self.last_probe_period: PeriodSelection | None = None
        # A review is valid only for the read performed in this app session.
        # Never preload the generic HTML from a previous fortnight.
        self.review_html_path: Path | None = None
        self.review_period_key: str | None = None
        self.review_window: ReviewWindow | None = None

        self._build_styles()
        self._build_layout()
        self._update_period_preview()

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            padding=8,
            fieldbackground="white",
            bordercolor=COLORS["border"],
        )
        style.configure("TSpinbox", padding=8)
        style.configure(
            "Primary.TButton",
            background=COLORS["blue"],
            foreground="white",
            borderwidth=0,
            padding=(18, 11),
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Primary.TButton", background=[("active", "#245E91")])
        style.configure(
            "Secondary.TButton",
            background="white",
            foreground=COLORS["navy"],
            bordercolor=COLORS["border"],
            padding=(14, 9),
            font=("Segoe UI", 10),
        )
        style.configure("TRadiobutton", background=COLORS["card"], font=("Segoe UI", 10))

    def _build_layout(self) -> None:
        header = tk.Frame(self, bg=COLORS["navy"], height=62)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="Automação do Fechamento WL",
            bg=COLORS["navy"],
            fg="white",
            font=("Segoe UI", 20, "bold"),
        ).pack(anchor="w", padx=34, pady=(10, 0))

        body = tk.Frame(self, bg=COLORS["background"])
        body.pack(fill="both", expand=True, padx=28, pady=10)
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        left = tk.Frame(body, bg=COLORS["card"], highlightbackground=COLORS["border"], highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        right = tk.Frame(body, bg=COLORS["card"], highlightbackground=COLORS["border"], highlightthickness=1)
        right.grid(row=0, column=1, sticky="nsew")

        self._build_configuration_card(left)
        self._build_status_card(right)

    def _section_title(self, parent: tk.Widget, title: str, subtitle: str) -> None:
        tk.Label(parent, text=title, bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 15, "bold")).pack(anchor="w")
        tk.Label(
            parent,
            text=subtitle,
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            anchor="w",
            justify="left",
        ).pack(fill="x", anchor="w", pady=(2, 8))

    def _build_configuration_card(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=COLORS["card"])
        content.pack(fill="both", expand=True, padx=24, pady=12)
        self._section_title(
            content,
            "Preparar fechamento",
            "Escolha a planilha oficial e o período.\nEsta etapa apenas valida; nenhum dado será escrito.",
        )

        tk.Label(content, text="Planilha oficial", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
        file_row = tk.Frame(content, bg=COLORS["card"])
        file_row.pack(fill="x", pady=(5, 9))
        entry = tk.Entry(file_row, textvariable=self.workbook_var, relief="solid", bd=1, fg=COLORS["text"], readonlybackground="white", font=("Segoe UI", 9), state="readonly")
        entry.pack(side="left", fill="x", expand=True, ipady=9)
        ttk.Button(file_row, text="Escolher arquivo", style="Secondary.TButton", command=self._choose_workbook).pack(side="left", padx=(10, 0))

        tk.Label(content, text="Período", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
        period_row = tk.Frame(content, bg=COLORS["card"])
        period_row.pack(fill="x", pady=(7, 10))

        month_combo = ttk.Combobox(period_row, textvariable=self.month_var, values=list(MONTH_NAMES.values()), state="readonly", width=18)
        month_combo.pack(side="left", padx=(0, 10))
        month_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_period_preview())

        year_spin = ttk.Spinbox(period_row, from_=2020, to=2100, textvariable=self.year_var, width=9, command=self._update_period_preview)
        year_spin.pack(side="left")
        year_spin.bind("<FocusOut>", lambda _event: self._update_period_preview())
        year_spin.bind("<KeyRelease>", lambda _event: self._update_period_preview())

        fortnight_box = tk.Frame(content, bg=COLORS["card"])
        fortnight_box.pack(fill="x", pady=(3, 11))
        ttk.Radiobutton(fortnight_box, text="1ª quinzena (dias 1 a 15)", variable=self.fortnight_var, value=1, command=self._update_period_preview).pack(side="left")
        ttk.Radiobutton(fortnight_box, text="2ª quinzena (dia 16 ao fim)", variable=self.fortnight_var, value=2, command=self._update_period_preview).pack(side="left", padx=(22, 0))

        preview = tk.Label(content, textvariable=self.period_var, bg=COLORS["light_blue"], fg=COLORS["navy"], font=("Segoe UI", 10, "bold"), anchor="w", padx=13, pady=11)
        preview.pack(fill="x", pady=(0, 10))

        ttk.Button(content, text="Validar planilha e período", style="Primary.TButton", command=self._validate_selection).pack(anchor="w")

        separator = ttk.Separator(content, orient="horizontal")
        separator.pack(fill="x", pady=12)

        tk.Label(content, text="Teste da nova entrada de Estaca", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(content, text="Confirma a regra textual antes da integração com o WhatsApp.", bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 8))
        stake_row = tk.Frame(content, bg=COLORS["card"])
        stake_row.pack(fill="x")
        tk.Entry(stake_row, textvariable=self.stake_input_var, relief="solid", bd=1, font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, ipady=8)
        ttk.Button(stake_row, text="Calcular", style="Secondary.TButton", command=self._test_stake_entry).pack(side="left", padx=(10, 0))
        tk.Label(content, textvariable=self.stake_result_var, bg=COLORS["card"], fg=COLORS["green"], font=("Segoe UI", 9, "bold"), wraplength=590, justify="left").pack(anchor="w", pady=(9, 0))

    def _build_status_card(self, parent: tk.Frame) -> None:
        content = tk.Frame(parent, bg=COLORS["card"])
        content.pack(fill="both", expand=True, padx=22, pady=12)
        self._section_title(content, "Situação do piloto", "A configuração precisa estar válida antes da leitura do WhatsApp.")

        self.status_banner = tk.Label(content, textvariable=self.status_var, bg=COLORS["light_amber"], fg=COLORS["amber"], font=("Segoe UI", 12, "bold"), anchor="w", padx=14, pady=14)
        self.status_banner.pack(fill="x")

        tk.Label(content, text="Verificações", bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(15, 7))
        self.details_text = tk.Text(content, height=17, wrap="word", relief="flat", bg="#F9FAFB", fg=COLORS["text"], font=("Segoe UI", 9), padx=12, pady=12, state="disabled")
        self.details_text.pack(fill="both", expand=True)
        self._set_details([
            "• Selecione a planilha oficial.",
            "• Escolha o mês, ano e quinzena.",
            "• Clique em Validar planilha e período.",
            "",
            "A validação é somente leitura e não modifica o arquivo.",
        ])

        self.next_button = ttk.Button(
            content,
            text="Ler evidências da quinzena",
            style="Secondary.TButton",
            state="disabled",
            command=self._start_whatsapp_probe,
        )
        self.next_button.pack(fill="x", pady=(12, 0))
        self.local_import_button = ttk.Button(
            content,
            text="Importar ZIP ou pasta de fotos",
            style="Primary.TButton",
            state="disabled",
            command=self._select_local_evidence,
        )
        self.local_import_button.pack(fill="x", pady=(8, 0))
        self.saved_read_button = ttk.Button(
            content,
            text="Usar última leitura salva desta quinzena",
            style="Secondary.TButton",
            state="disabled",
            command=self._use_saved_read,
        )
        self.saved_read_button.pack(fill="x", pady=(8, 0))
        self.review_button = ttk.Button(
            content,
            text="Analisar fotos com Leitura Visual 2",
            style="Primary.TButton",
            state="disabled",
            command=self._start_photo_review,
        )
        self.review_button.pack(fill="x", pady=(8, 0))

    def _choose_workbook(self) -> None:
        initial = Path(self.workbook_var.get()).parent if self.workbook_var.get() else Path.home()
        selected = filedialog.askopenfilename(
            title="Escolha a planilha oficial",
            initialdir=str(initial),
            filetypes=[("Planilhas Excel", "*.xlsx *.xlsm"), ("Todos os arquivos", "*.*")],
        )
        if selected:
            self.workbook_var.set(selected)
            self.status_var.set("Arquivo selecionado; falta validar")
            self._set_status("warning")

    def _period(self) -> PeriodSelection:
        month = MONTH_NUMBERS[self.month_var.get()]
        return PeriodSelection(
            year=int(self.year_var.get()),
            month=month,
            fortnight=int(self.fortnight_var.get()),
        )

    def _update_period_preview(self) -> None:
        try:
            period = self._period()
            self.period_var.set(f"{period.label}  •  Aba esperada: {period.sheet_name}")
        except (ValueError, KeyError):
            self.period_var.set("Informe um mês, ano e quinzena válidos.")

    def _validate_selection(self) -> None:
        workbook_path = self.workbook_var.get().strip()
        if not workbook_path:
            messagebox.showwarning("Planilha necessária", "Escolha a planilha oficial antes de validar.")
            return
        try:
            period = self._period()
        except (ValueError, KeyError) as exc:
            messagebox.showwarning("Período inválido", str(exc))
            return

        self.status_var.set("Validando planilha…")
        self.update_idletasks()
        result = validate_workbook(workbook_path, period)
        details = list(result.messages)
        details.append("")
        details.append(f"Arquivo: {result.path.name}")
        details.append(f"Período: {period.label}")
        details.append(f"Aba: {period.sheet_name}")

        if result.valid:
            # Validating a period starts a fresh review context. A previous
            # fortnight can no longer be opened from this selection.
            if self.review_window is not None and self.review_window.winfo_exists():
                self.review_window.destroy()
            self.review_window = None
            self.last_whatsapp_result = None
            self.last_probe_period = None
            self.review_html_path = None
            self.review_period_key = None
            self.review_button.configure(state="disabled", text="Analisar fotos com Leitura Visual 2")
            self.config_data = AppConfiguration(
                workbook_path=str(result.path),
                last_year=period.year,
                last_month=period.month,
                last_fortnight=period.fortnight,
            )
            save_configuration(self.config_data)
            self.status_var.set("Configuração válida")
            self._set_status("success")
            self.next_button.configure(state="normal")
            self.local_import_button.configure(state="normal")
            self.saved_read_button.configure(state="normal")
            details.append("")
            details.append("✓ Localização memorizada para a próxima execução.")
            details.append("✓ Nenhuma célula foi modificada.")
        else:
            self.status_var.set("Configuração precisa de correção")
            self._set_status("error")
            self.next_button.configure(state="disabled")
            self.local_import_button.configure(state="disabled")
            self.saved_read_button.configure(state="disabled")
            details.append("")
            details.append("A planilha não foi configurada. Corrija os itens acima.")
        self._set_details(details)

    def _start_whatsapp_probe(self) -> None:
        try:
            period = self._period()
        except (ValueError, KeyError) as exc:
            messagebox.showwarning("Período inválido", str(exc))
            return

        if self.review_window is not None and self.review_window.winfo_exists():
            self.review_window.destroy()
        self.review_window = None
        self.last_whatsapp_result = None
        self.last_probe_period = None
        self.review_html_path = None
        self.review_period_key = None
        self.review_button.configure(state="disabled", text="Analisar fotos com Leitura Visual 2")
        self.next_button.configure(state="disabled")
        self.status_var.set("Conectando ao WhatsApp…")
        self._set_status("warning")
        self._set_details([
            "• Grupo: AWL x Expedição Prellog",
            f"• Data inicial procurada: {period.start_date.strftime('%d/%m/%Y')}",
            "• Use somente uma aba do WhatsApp Web no perfil AWL.",
            "• Deixe o grupo aberto nessa aba antes de iniciar.",
            "• A extensão instalada fará a leitura somente do WhatsApp Web.",
            "",
            "Este teste não reage, não envia mensagens e não altera a planilha.",
        ])

        worker = threading.Thread(
            target=self._run_whatsapp_probe,
            args=(period,),
            daemon=True,
        )
        worker.start()

    def _use_saved_read(self) -> None:
        try:
            period = self._period()
            result = load_latest_complete_whatsapp_session(
                period.start_date, period.end_date
            )
            result = restrict_result_to_period(
                result, period.start_date, period.end_date
            )
        except Exception as exc:
            messagebox.showwarning("Leitura salva indisponível", str(exc))
            return
        self.review_html_path = None
        self.review_period_key = None
        self._show_whatsapp_result(result, period)

    def _select_local_evidence(self) -> None:
        choice = messagebox.askyesnocancel(
            "Escolher evidências",
            "Como você quer importar as evidências?\n\n"
            "Sim: escolher o ZIP do WhatsApp.\n"
            "Não: escolher uma pasta normal com as fotos.",
            parent=self,
        )
        if choice is None:
            return
        if choice:
            selected = filedialog.askopenfilename(
                title="Escolha o ZIP exportado pelo WhatsApp com as mídias",
                filetypes=[("Arquivo ZIP", "*.zip")],
            )
            source_label = "ZIP selecionado"
        else:
            selected = filedialog.askdirectory(
                title="Escolha a pasta normal que contém as fotos"
            )
            source_label = "Pasta selecionada"
        if not selected:
            return
        try:
            period = self._period()
        except (ValueError, KeyError) as exc:
            messagebox.showwarning("Período inválido", str(exc), parent=self)
            return
        self.local_import_button.configure(state="disabled")
        self.status_var.set("Copiando evidências locais…")
        self._set_status("warning")
        self._set_details([
            f"• {source_label}: {selected}",
            f"• Período escolhido: {period.label}",
            "• O conteúdo do ZIP será validado antes da análise.",
            "• O WhatsApp e a planilha não serão alterados.",
        ])
        threading.Thread(
            target=self._run_local_import,
            args=(selected, period),
            daemon=True,
        ).start()

    def _run_local_import(self, selected: str, period: PeriodSelection) -> None:
        try:
            result = import_local_evidence(
                selected, period.start_date, period.end_date
            )
        except Exception as exc:
            error = str(exc)
            self.after(0, lambda: self._show_local_import_error(error))
            return
        self.after(0, lambda: self._show_whatsapp_result(result, period))

    def _show_local_import_error(self, error: str) -> None:
        self.local_import_button.configure(state="normal")
        self.status_var.set("Não foi possível importar as fotos")
        self._set_status("error")
        self._set_details([
            f"Motivo: {error}",
            "Nenhuma mensagem e nenhum dado da planilha foram alterados.",
        ])

    def _run_whatsapp_probe(self, period: PeriodSelection) -> None:
        try:
            result = probe_whatsapp_chrome(period.start_date, period.end_date)
            result = restrict_result_to_period(result, period.start_date, period.end_date)
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda: self._show_whatsapp_error(message))
            return
        self.after(0, lambda: self._show_whatsapp_result(result, period))

    def _show_whatsapp_error(self, message: str) -> None:
        self.status_var.set("WhatsApp não conectado")
        self._set_status("error")
        self._set_details([
            "• Não foi possível concluir o teste.",
            f"• Motivo: {message}",
            "",
            "Nenhuma mensagem e nenhum dado da planilha foram alterados.",
        ])
        self.next_button.configure(state="normal")

    def _show_whatsapp_result(
        self,
        result: WhatsAppProbeResult,
        period: PeriodSelection,
    ) -> None:
        self.last_whatsapp_result = result
        self.last_probe_period = period
        if not result.period_scan_complete:
            self.status_var.set("Leitura incompleta; revisão bloqueada")
            self._set_status("warning")
        elif result.incomplete_albums:
            self.status_var.set("Evidências encontradas; álbuns incompletos")
            self._set_status("warning")
        elif result.start_date_found:
            self.status_var.set(
                "Período e evidências lidos"
                if result.evidences
                else "WhatsApp e período comprovados"
            )
            self._set_status("success")
        elif result.sync_in_progress:
            self.status_var.set("WhatsApp ainda está sincronizando")
            self._set_status("warning")
        else:
            self.status_var.set("WhatsApp conectado; histórico incompleto")
            self._set_status("warning")

        stake_text = (
            ", ".join(result.stake_messages)
            if result.stake_messages
            else "nenhuma visível"
        )
        evidence_lines = []
        for evidence in result.evidences[:8]:
            sender = f" • {evidence.sender}" if evidence.sender else ""
            evidence_lines.append(
                f"  {evidence.message_date} {evidence.message_time}{sender} • "
                f"{evidence.kind_label}"
            )
        if len(result.evidences) > 8:
            evidence_lines.append(
                f"  … e mais {len(result.evidences) - 8} mensagens no inventário."
            )
        if result.evidence_truncated:
            evidence_lines.append("  ⚠ O inventário atingiu o limite de segurança.")

        valid_evidence_dates = []
        for evidence in result.evidences:
            try:
                valid_evidence_dates.append((
                    datetime.strptime(evidence.message_date, "%d/%m/%Y"),
                    evidence.message_date,
                ))
            except ValueError:
                continue
        first_evidence_date = min(valid_evidence_dates)[1] if valid_evidence_dates else ""
        configured_start = period.start_date.strftime("%d/%m/%Y")
        if (
            result.start_date_found
            and first_evidence_date
            and first_evidence_date != configured_start
        ):
            start_check = (
                f"• Início {configured_start}: sem movimento; primeira evidência "
                f"em {first_evidence_date} reconhecida"
            )
        else:
            start_check = (
                f"• Data inicial {configured_start}: "
                f"{'encontrada' if result.start_date_found else 'não encontrada'}"
            )

        local_source = result.group_name == "Pasta ou ZIP local"
        details = [
            (
                "• Fonte local: OK"
                if local_source
                else f"• Conexão: {'OK' if result.connected else 'não'}"
            ),
            (
                "• WhatsApp Web: não utilizado"
                if local_source
                else f"• Grupo correto: {'OK' if result.group_found else 'não encontrado'}"
            ),
            (
                "• Cobertura da quinzena: "
                f"{'completa' if result.period_scan_complete else 'incompleta'}"
            ),
            start_check,
            f"• Etapas de carregamento: {result.load_attempts}",
            f"• Esperas pela sincronização: {result.sync_waits}",
            (
                "• Sincronização do celular: "
                f"{'em andamento' if result.sync_in_progress else 'concluída'}"
            ),
            f"• Fotos visíveis: {result.visible_images}",
            f"• Fotos copiadas com segurança: {len(result.captured_attachments)}",
            f"• Álbuns ainda incompletos: {len(result.incomplete_albums)}",
            f"• PDFs visíveis: {result.visible_pdfs}",
            f"• Entradas de Estaca visíveis: {stake_text}",
            f"• Mensagens com evidência no período: {len(result.evidences)}",
            "",
            "Inventário (primeiras mensagens):",
            *(evidence_lines or ["  Nenhuma evidência estruturada foi encontrada."]),
            "",
            result.message,
            "Nenhuma mensagem e nenhum dado da planilha foram alterados.",
        ]
        self._set_details(details)
        self.next_button.configure(state="normal", text="Atualizar leitura das evidências")
        self.local_import_button.configure(state="normal")
        if (
            result.period_scan_complete
            and result.start_date_found
            and result.captured_attachments
            and not result.incomplete_albums
        ):
            self.review_button.configure(state="normal")
            # Open the temporary review automatically when the read produced
            # period evidence; the button remains available for reopening it.
            if result.evidences and not local_source:
                self.after(350, self._start_photo_review)
        elif not result.period_scan_complete:
            self.review_button.configure(
                state="disabled",
                text="Concluir leitura de toda a quinzena antes da revisão",
            )
        elif result.incomplete_albums:
            self.review_button.configure(
                state="disabled",
                text="Concluir captura dos álbuns antes da revisão",
            )

    def _start_photo_review(self) -> None:
        try:
            selected_period = self._period()
        except (ValueError, KeyError) as exc:
            messagebox.showwarning("Período inválido", str(exc))
            return
        if self.review_window is not None and self.review_window.winfo_exists():
            self.review_window.deiconify()
            self.review_window.lift()
            self.review_window.focus_force()
            return
        result = self.last_whatsapp_result
        if self.last_probe_period != selected_period:
            messagebox.showwarning(
                "Leia esta quinzena primeiro",
                "As evidências disponíveis não pertencem ao período selecionado. "
                "Clique em 'Ler evidências da quinzena' antes de abrir a revisão.",
            )
            return
        if result is None or not result.captured_attachments:
            messagebox.showwarning(
                "Fotos necessárias",
                "A leitura desta quinzena ainda não copiou fotos para analisar.",
            )
            return
        if result.incomplete_albums:
            messagebox.showwarning(
                "Captura incompleta",
                f"Ainda há {len(result.incomplete_albums)} álbum(ns) incompleto(s). "
                "Clique em 'Atualizar leitura das evidências' antes de analisar.",
            )
            return
        self.review_button.configure(state="disabled")
        self.status_var.set("Leitura Visual 2: analisando etiquetas…")
        self._set_status("warning")
        worker = threading.Thread(
            target=self._run_photo_review,
            args=(result, selected_period),
            daemon=True,
        )
        worker.start()

    def _run_photo_review(
        self,
        result: WhatsAppProbeResult,
        period: PeriodSelection,
    ) -> None:
        def progress(current: int, total: int, filename: str) -> None:
            self.after(0, lambda: self._set_details([
                f"• Foto {current} de {total}",
                f"• Arquivo: {filename}",
                "• A leitura é local e não altera o WhatsApp nem a planilha.",
            ]))

        try:
            drafts = build_advanced_review_drafts(result, progress)
        except Exception as exc:
            error = str(exc)
            self.after(0, lambda: self._show_photo_review_error(error))
            return
        self.after(0, lambda: self._show_photo_review(drafts, result, period))

    def _show_photo_review_error(self, error: str) -> None:
        self.status_var.set("A leitura visual não foi concluída")
        self._set_status("error")
        self.review_button.configure(
            state="normal", text="Tentar novamente com Leitura Visual 2"
        )
        self._set_details([
            "A revisão temporária não foi substituída.",
            f"Motivo: {error}",
            "As fotos já analisadas continuam salvas para a próxima tentativa.",
        ])

    def _show_photo_review(
        self,
        drafts: list[LabelDraft],
        result: WhatsAppProbeResult,
        period: PeriodSelection,
    ) -> None:
        self.status_var.set("Área temporária pronta para revisão")
        self._set_status("success")
        self.review_button.configure(state="normal", text="Reabrir revisão integrada")
        self.review_window = ReviewWindow(
            self, drafts, self.workbook_var.get().strip(), period
        )
        self._set_details([
            "Revisão integrada aberta no próprio aplicativo.",
            f"Período: {period.label}",
            "Use o filtro Pendente para revisar apenas os campos incertos.",
            "Depois, aprove os confirmados, consolide e importe com backup.",
        ])

    def _test_stake_entry(self) -> None:
        try:
            entry = parse_stake_text(self.stake_input_var.get())
            self.stake_result_var.set(
                f"ESTACA • Peça {entry.piece} • {entry.multiplier} × "
                f"{entry.base_value} = Quantidade {entry.quantity:,}".replace(",", ".")
                + " • Dimensões e volume unitário vazios"
            )
        except ValueError as exc:
            self.stake_result_var.set(str(exc))

    def _set_status(self, status: str) -> None:
        schemes = {
            "success": (COLORS["light_green"], COLORS["green"]),
            "warning": (COLORS["light_amber"], COLORS["amber"]),
            "error": (COLORS["light_red"], COLORS["red"]),
        }
        bg, fg = schemes[status]
        self.status_banner.configure(bg=bg, fg=fg)

    def _set_details(self, lines: list[str]) -> None:
        self.details_text.configure(state="normal")
        self.details_text.delete("1.0", "end")
        self.details_text.insert("1.0", "\n".join(lines))
        self.details_text.configure(state="disabled")


class ReviewWindow(tk.Toplevel):
    OPTIONS = (
        "BLOCO", "ESTACA", "ESCADA", "MURO", "PAINEL", "PILAR", "VIGA",
        "LAJE", "VIGA 15,56m ATÉ 25m", "VIGA 10,1m ATÉ 15,55m",
        "VIGA 9m ATÉ 10m", "VIGA 6,1 ATÉ 8,9m", "VIGA ATÉ 6m",
        "LAJE ALVEOLAR", "METRO CÚBICO", "VIGA TERÇA",
    )
    FIELDS = (
        ("data da mensagem", "message_date"), ("obra", "work"),
        ("produto", "product"), ("peça", "piece"),
        ("seção", "section"), ("comprimento", "length"),
        ("dimensão", "dimensions"), ("volume unitário", "unit_volume"),
        ("tipo", "type_name"), ("quantidade", "quantity"),
    )

    def __init__(self, parent: tk.Widget, drafts: list[LabelDraft], workbook_path: str, period: PeriodSelection) -> None:
        super().__init__(parent)
        self.title("Revisão temporária — Fechamento WL")
        self.geometry("1180x720+45+20")
        self.minsize(920, 620)
        self.configure(bg=COLORS["background"])
        self.drafts = drafts
        self.workbook_path = workbook_path
        self.period = period
        self.filter_name = "TODOS"
        self.position = 0
        self.filtered: list[int] = []
        self.variables: dict[str, tk.StringVar] = {}
        self.status_choice = tk.StringVar()
        self.protocol("WM_DELETE_WINDOW", self._close)

        header = tk.Frame(self, bg=COLORS["background"])
        header.pack(fill="x", padx=24, pady=(18, 8))
        tk.Label(header, text="Revisão temporária do fechamento WL", bg=COLORS["background"], fg=COLORS["text"], font=("Segoe UI", 20, "bold")).pack(anchor="w")
        self.summary = tk.Label(header, bg=COLORS["background"], fg=COLORS["text"], font=("Segoe UI", 10))
        self.summary.pack(anchor="w", pady=(4, 8))
        filters = tk.Frame(header, bg=COLORS["background"])
        filters.pack(fill="x")
        tk.Label(filters, text="Exibir:", bg=COLORS["background"], fg=COLORS["text"]).pack(side="left")
        for name in ("TODOS", "PENDENTE", "CONFIRMADO", "APROVADO", "REJEITADO"):
            ttk.Button(filters, text=name.title(), style="Secondary.TButton", command=lambda value=name: self._set_filter(value)).pack(side="left", padx=(7, 0))

        self.card = tk.Frame(self, bg=COLORS["card"], highlightthickness=2, highlightbackground=COLORS["amber"])
        self.card.pack(fill="both", expand=True, padx=24, pady=10)
        self.entry_title = tk.Label(self.card, bg=COLORS["card"], fg=COLORS["text"], font=("Segoe UI", 16, "bold"))
        self.entry_title.grid(row=0, column=0, columnspan=4, sticky="w", padx=18, pady=(16, 4))
        self.photo_button = ttk.Button(self.card, text="Abrir foto original", style="Secondary.TButton", command=self._open_photo)
        self.photo_button.grid(row=1, column=0, sticky="w", padx=18, pady=4)
        self.warning_label = tk.Label(self.card, bg=COLORS["card"], fg=COLORS["amber"], justify="left", wraplength=1040)
        self.warning_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=18, pady=(4, 10))
        for column in range(4):
            self.card.grid_columnconfigure(column, weight=1)
        for offset, (label, attribute) in enumerate(self.FIELDS):
            row, column = 3 + (offset // 4) * 2, offset % 4
            tk.Label(self.card, text=label, bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 9)).grid(row=row, column=column, sticky="sw", padx=10, pady=(6, 0))
            variable = tk.StringVar()
            self.variables[attribute] = variable
            if attribute in {"product", "type_name"}:
                widget = ttk.Combobox(self.card, textvariable=variable, values=self.OPTIONS, state="readonly")
                other = "type_name" if attribute == "product" else "product"
                widget.bind(
                    "<<ComboboxSelected>>",
                    lambda _event, source=attribute, target=other: self.variables[target].set(
                        self.variables[source].get()
                    ),
                )
            else:
                widget = tk.Entry(self.card, textvariable=variable, relief="solid", bd=1, font=("Segoe UI", 10))
            widget.grid(row=row + 1, column=column, sticky="ew", padx=10, pady=(2, 6), ipady=6)
        status_row = 9
        tk.Label(self.card, text="situação", bg=COLORS["card"], fg=COLORS["muted"], font=("Segoe UI", 9)).grid(row=status_row, column=0, sticky="sw", padx=10)
        ttk.Combobox(self.card, textvariable=self.status_choice, values=("PENDENTE", "CONFIRMADO", "APROVADO", "REJEITADO"), state="readonly").grid(row=status_row + 1, column=0, sticky="ew", padx=10, pady=(2, 14), ipady=6)

        navigation = tk.Frame(self, bg=COLORS["background"])
        navigation.pack(fill="x", padx=24, pady=(0, 18))
        ttk.Button(navigation, text="← Anterior", style="Secondary.TButton", command=lambda: self._move(-1)).pack(side="left")
        self.counter = tk.Label(navigation, bg=COLORS["background"], fg=COLORS["text"], font=("Segoe UI", 10, "bold"))
        self.counter.pack(side="left", padx=12)
        ttk.Button(navigation, text="Próxima →", style="Secondary.TButton", command=lambda: self._move(1)).pack(side="left")
        ttk.Button(navigation, text="Aprovar todos os confirmados", style="Secondary.TButton", command=self._approve_confirmed).pack(side="right", padx=(8, 0))
        ttk.Button(navigation, text="Consolidar aprovados", style="Primary.TButton", command=self._show_consolidated).pack(side="right")
        self._set_filter("PENDENTE" if any(self._display_status(item) == "PENDENTE" for item in drafts) else "TODOS")

    @staticmethod
    def _display_status(draft: LabelDraft) -> str:
        if draft.status in {"APROVADO", "REJEITADO", "CONFIRMADO"}:
            return draft.status
        return "PENDENTE" if draft.warnings or draft.status in {"CONFIRMAR", "PENDENTE"} else "CONFIRMADO"

    def _set_filter(self, name: str) -> None:
        self._save_current(silent=True)
        self.filter_name = name
        self.filtered = [index for index, draft in enumerate(self.drafts) if name == "TODOS" or self._display_status(draft) == name]
        self.position = 0
        self._load_current()

    def _load_current(self) -> None:
        counts = {name: sum(self._display_status(item) == name for item in self.drafts) for name in ("PENDENTE", "CONFIRMADO", "APROVADO", "REJEITADO")}
        self.summary.configure(text=f"{len(self.drafts)} entradas · {counts['PENDENTE']} pendentes · {counts['CONFIRMADO']} confirmadas · {counts['APROVADO']} aprovadas")
        if not self.filtered:
            self.entry_title.configure(text=f"Nenhuma entrada em {self.filter_name.title()}")
            self.warning_label.configure(text="Escolha outro filtro.")
            self.counter.configure(text="0 de 0")
            return
        self.position = max(0, min(self.position, len(self.filtered) - 1))
        index = self.filtered[self.position]
        draft = self.drafts[index]
        if draft.type_name:
            draft.product = draft.type_name
        self.entry_title.configure(text=f"Entrada {index + 1}")
        self.warning_label.configure(text=" · ".join(draft.warnings) if draft.warnings else "Sem alerta automático")
        for _, attribute in self.FIELDS:
            value = getattr(draft, attribute)
            if attribute in {"unit_volume", "quantity"} and value is not None:
                value = str(value).replace(".", ",")
            self.variables[attribute].set("" if value is None else str(value))
        self.status_choice.set(self._display_status(draft))
        self.counter.configure(text=f"{self.position + 1} de {len(self.filtered)} no filtro")

    def _save_current(self, silent: bool = False) -> bool:
        if not self.filtered:
            return True
        draft = self.drafts[self.filtered[self.position]]
        try:
            volume_text = self.variables["unit_volume"].get().strip()
            quantity_text = self.variables["quantity"].get().strip()
            draft.unit_volume = float(volume_text.replace(",", ".")) if volume_text else None
            quantity = float(quantity_text.replace(",", ".")) if quantity_text else 1
            draft.quantity = int(quantity) if quantity.is_integer() else quantity
        except ValueError:
            if not silent:
                messagebox.showwarning("Número inválido", "Revise quantidade e volume unitário.", parent=self)
            return False
        for _, attribute in self.FIELDS:
            if attribute not in {"unit_volume", "quantity"}:
                setattr(draft, attribute, self.variables[attribute].get().strip())
        selected = self.status_choice.get() or self._display_status(draft)
        draft.status = selected
        if selected in {"CONFIRMADO", "APROVADO"}:
            draft.warnings = []
        self._persist()
        return True

    def _persist(self) -> None:
        if not self.drafts:
            return
        cache_path = Path(self.drafts[0].source_path).parent / "revisao_temporaria.json"
        if not cache_path.exists():
            return
        try:
            loaded = json.loads(cache_path.read_text(encoding="utf-8"))
            replacements = {(item.message_id, item.source_path): asdict(item) for item in self.drafts}
            for group in loaded.values():
                if not isinstance(group, list):
                    continue
                for index, row in enumerate(group):
                    key = (str(row.get("message_id") or ""), str(row.get("source_path") or ""))
                    if key in replacements:
                        group[index] = replacements[key]
            temporary = cache_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(loaded, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(cache_path)
        except (OSError, ValueError, TypeError):
            pass

    def _move(self, step: int) -> None:
        if not self._save_current():
            return
        self.position = max(0, min(self.position + step, len(self.filtered) - 1)) if self.filtered else 0
        self._load_current()

    def _open_photo(self) -> None:
        if self.filtered:
            os.startfile(self.drafts[self.filtered[self.position]].source_path)

    def _approve_confirmed(self) -> None:
        self._save_current(silent=True)
        changed = 0
        for draft in self.drafts:
            if self._display_status(draft) == "CONFIRMADO":
                draft.status = "APROVADO"
                draft.warnings = []
                changed += 1
        self._persist()
        messagebox.showinfo("Aprovação concluída", f"{changed} entrada(s) confirmada(s) foram aprovadas.", parent=self)
        self._set_filter(self.filter_name)

    def _close(self) -> None:
        self._save_current(silent=True)
        self.destroy()

    def _show_consolidated(self) -> None:
        if not self._save_current():
            return
        rows = group_approved_drafts(self.drafts)
        if not rows:
            messagebox.showinfo(
                "Nenhuma linha aprovada",
                "Aprove pelo menos uma etiqueta antes de consolidar.",
                parent=self,
            )
            return
        ConsolidatedWindow(self, rows, self.workbook_path, self.period)


class ConsolidatedWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, rows: list[ConsolidatedRow], workbook_path: str, period: PeriodSelection) -> None:
        super().__init__(parent)
        self.title("Resumo consolidado — ainda não enviado ao Excel")
        self.geometry("1120x500+75+65")
        self.rows = rows
        self.workbook_path = workbook_path
        self.period = period
        tk.Label(
            self,
            text="Resumo das linhas aprovadas",
            font=("Segoe UI", 16, "bold"),
            fg=COLORS["navy"],
        ).pack(anchor="w", padx=18, pady=(15, 2))
        tk.Label(
            self,
            text=(
                f"{sum(row.source_count for row in rows)} etiquetas aprovadas → "
                f"{len(rows)} linhas. Mesmo dia e todos os campos iguais foram unidos."
            ),
            fg=COLORS["muted"],
        ).pack(anchor="w", padx=18, pady=(0, 10))
        columns = ("data", "tipo", "obra", "quantidade", "peca", "dimensoes", "volume", "carga")
        tree = ttk.Treeview(self, columns=columns, show="headings")
        titles = {
            "data": "Data", "tipo": "Tipo", "obra": "Obra", "quantidade": "Quantidade",
            "peca": "Peça", "dimensoes": "Dimensões", "volume": "Vol. unit.", "carga": "Tipo de carga",
        }
        widths = {"data": 90, "tipo": 155, "obra": 210, "quantidade": 85, "peca": 80, "dimensoes": 170, "volume": 85, "carga": 135}
        for column in columns:
            tree.heading(column, text=titles[column])
            tree.column(column, width=widths[column], minwidth=65)
        for row in rows:
            volume = "" if row.unit_volume is None else str(row.unit_volume).replace(".", ",")
            tree.insert("", "end", values=(
                row.message_date, row.type_name, row.work, row.quantity,
                row.piece, row.dimensions, volume, row.cargo_type,
            ))
        tree.pack(fill="both", expand=True, padx=18)
        tk.Label(
            self,
            text="Volume total, unidade de medida, valor unitário e valor total continuam sob responsabilidade das fórmulas da planilha.",
            fg=COLORS["amber"],
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=18, pady=10)
        actions = tk.Frame(self)
        actions.pack(fill="x", padx=18, pady=(0, 14))
        self.import_button = ttk.Button(
            actions,
            text="Importar aprovados na planilha selecionada",
            style="Primary.TButton",
            command=self._confirm_import,
        )
        self.import_button.pack(side="left")
        ttk.Button(actions, text="Fechar", style="Secondary.TButton", command=self.destroy).pack(side="right")

    def _confirm_import(self) -> None:
        confirmed = messagebox.askyesno(
            "Confirmar importação",
            f"Será criado um backup e {len(self.rows)} linha(s) serão incluídas em:\n\n"
            f"{self.workbook_path}\n\nApenas os campos de origem serão preenchidos. Continuar?",
            parent=self,
        )
        if not confirmed:
            return
        self.import_button.configure(state="disabled", text="Criando backup e importando…")
        threading.Thread(target=self._run_import, daemon=True).start()

    def _run_import(self) -> None:
        try:
            result = write_approved_rows(self.workbook_path, self.period, self.rows)
        except Exception as exc:
            message = str(exc)
            self.after(0, lambda: self._import_error(message))
            return
        self.after(0, lambda: self._import_success(result))

    def _import_error(self, message: str) -> None:
        self.import_button.configure(state="normal", text="Tentar importar novamente")
        messagebox.showerror("Importação não concluída", message, parent=self)

    def _import_success(self, result) -> None:
        self.import_button.configure(state="disabled", text="Importação concluída")
        messagebox.showinfo(
            "Importação concluída",
            "As linhas aprovadas foram incluídas.\n\n"
            f"Linhas: {', '.join(str(row) for row in result.imported_rows)}\n"
            f"Backup: {result.backup_path}",
            parent=self,
        )


def run() -> None:
    app = FechamentoApp()
    app.mainloop()
