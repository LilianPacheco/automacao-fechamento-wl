# Automação do Fechamento Quinzenal — WL

Continuidade do projeto pelo Método das 12 Gavetas.

## Estado atual

| Gaveta | Estado | Observação |
|---|---|---|
| 00 — Mandato | Fechada | Herdada e coerente com as evidências |
| 01 — Contexto e Escopo | Fechada | Fronteiras, início, fim, papéis e exclusões formalizados |
| 02 — Evidências | Fechada para descoberta | Inventário, rastreabilidade e limitações registrados |
| 03 — Ontologia | Fechada | Fontes dos campos, controle de processado e chave de agrupamento confirmados por Lilian |
| 04 — AS-IS | Fechada | Fluxo, decisões, exceções, autoridade e encerramento confirmados por Lilian |
| 05 — Baseline | Fechada | Baseline mínima aceita para uso interno: 3 horas e 8.000–9.000 peças por fechamento |
| 06 — Diagnóstico | Fechada | Causa raiz e limites da automação confirmados por Lilian |
| 07 — TO-BE | Fechada | Agrupamento, revisão, momento do OK e finalização confirmados por Lilian |
| 08 — Solução e TI | Fechada | Período, leitura, captura, reação 🆗, bloqueio de duplicidade e inclusão aprovada na cópia comprovados |
| 09 — Contratos | Fechada | PRD, SRS/ETO, Regras do Agente e rastreabilidade validados por Lilian |
| 10 — Operação | Fechada | SOP, instrução, checklist, backups e avisos validados por Lilian |
| 11 — Medição contínua | Fechada | Resumo automático, indicadores e ciclo de novos erros validados |

O documento principal é [docs/Projeto_Automacao_Fechamento_WL_v1.1.md](docs/Projeto_Automacao_Fechamento_WL_v1.1.md).

## Aplicativo

O aplicativo Windows está na pasta `app` e integra o fluxo de leitura e revisão temporária. Ele:

- seleciona e valida a planilha e a quinzena;
- lê localmente as evidências visíveis no WhatsApp Web;
- extrai etiquetas e romaneios com OCR;
- apresenta somente os campos incertos como pendentes;
- mantém uma entrada pendente enquanto os campos são editados, até a confirmação explícita;
- reconhece entradas textuais de Estaca e romaneios de Estaca por metros totais;
- consolida apenas registros aprovados antes da escrita na planilha.

Para abrir no Windows, use `Executar_Fechamento_WL.bat` na raiz do projeto.

## Privacidade

Capturas do WhatsApp, planilhas reais, evidências, backups, logs e resultados temporários são locais e estão excluídos do Git. O repositório contém apenas código, testes e documentação.

## Testes

```powershell
$env:PYTHONPATH = "app"
python -m unittest discover -s app/tests -p "test_*.py"
```
