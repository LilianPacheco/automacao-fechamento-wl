# Gaveta 10 — Operação

**Status:** fechada em 25/07/2026  
**Responsável operacional:** Lilian  
**Objetivo:** definir como executar, conferir, recuperar e encerrar o fechamento no dia a dia.

## 1. Documentos operacionais

| Documento | Finalidade | Estado |
|---|---|---|
| `SOP_Fechamento_WL.md` | Define a rotina e as responsabilidades | Validado |
| `Instrucao_Uso_Fechamento_WL.md` | Ensina detalhadamente como operar e recuperar | Validado |
| `Checklist_Fechamento_WL.md` | Confirma somente os passos críticos | Validado |

## 2. Princípios da operação

- A automação roda no computador de Lilian.
- Lilian inicia cada fechamento e informa mês, ano e quinzena.
- A automação prepara; Lilian aprova, edita ou rejeita.
- O 🆗 indica captura integral, não aprovação.
- Se o 🆗 automático falhar, a automação avisa e Lilian reage manualmente.
- Antes da importação é criado um backup automático da planilha.
- Somente linhas aprovadas e com data podem ser importadas.
- O envio para Deise permanece manual e encerra o processo.
- O log é mantido por 12 meses.

## 3. Decisões operacionais a validar

| ID | Decisão | Proposta inicial |
|---|---|---|
| D10-01 | Como a automação localizará a planilha oficial? | **Confirmado:** Lilian seleciona o arquivo uma vez; a automação valida a estrutura, memoriza o caminho e mostra o nome antes de cada execução |
| D10-02 | Onde os backups serão guardados? | **Confirmado:** subpasta automática `Backups Fechamento` ao lado da planilha |
| D10-03 | Como os avisos aparecerão? | **Confirmado:** aviso curto na tela da automação e detalhes persistidos na aba `CONFERÊNCIA AUTO` |

## 4. Critério de fechamento

Atendido em 25/07/2026: Lilian validou o SOP, a instrução, o checklist, a seleção única do arquivo oficial, a pasta automática de backups e os avisos na tela com detalhes na aba `CONFERÊNCIA AUTO`. A Gaveta 11 — Medição Contínua — pode ser aberta.
