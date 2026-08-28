# Gaveta 09 — Contratos

**Status:** fechada em 25/07/2026  
**Responsável de negócio:** Lilian  
**Objetivo:** transformar as decisões aprovadas nas gavetas anteriores em contratos claros para negócio, tecnologia, agente e testes.

## 1. Entregas

| Documento | Pergunta respondida | Estado |
|---|---|---|
| `PRD_Fechamento_WL.md` | O que será construído e por quê? | Validado |
| `SRS_ETO_Fechamento_WL.md` | Como a solução deverá funcionar tecnicamente? | Validado |
| `Regras_Agente_Fechamento_WL.md` | O que o agente pode ou não pode decidir e executar? | Validado |
| `Matriz_Rastreabilidade_Gaveta_09.md` | Onde cada regra foi especificada e testada? | Criada |

## 2. Contratos centrais já confirmados

1. Lilian escolhe mês, ano e quinzena; a automação calcula o intervalo.
2. O único grupo em escopo nesta fase é `AWL x Expedição Prellog`.
3. A data válida é a data da mensagem do WhatsApp.
4. A automação prepara; Lilian aprova, edita ou rejeita.
5. Nenhum dado ilegível, ausente ou duvidoso pode ser inventado.
6. O 🆗 é aplicado depois da captura integral da mensagem na área temporária, antes da aprovação humana.
7. Somente linhas aprovadas entram na aba quinzenal.
8. A automação escreve apenas Tipo, Data, Obra, Quantidade, Peça, Dimensões, Volume unitário e Tipo de carga.
9. Volume total, Unidade de medida, Valor unitário e Valor total são calculados pelas fórmulas e pela tabela da planilha.
10. O fechamento termina depois da conferência final e do envio manual para Deise.

## 3. Pontos que ainda exigem decisão

| ID | Decisão pendente | Por que importa |
|---|---|---|
| D09-01 | A rotina definitiva rodará no computador de Lilian ou em outro ambiente? | **Confirmado:** rodará no computador de Lilian |
| D09-02 | Por quanto tempo o log e as referências das evidências serão guardados? | **Confirmado:** 12 meses; registros anteriores podem ser apagados automaticamente |
| D09-03 | Se uma mudança do WhatsApp impedir a leitura ou o 🆗, o fechamento poderá continuar sem reação e registrar a pendência? | **Confirmado:** continuar, avisar Lilian e deixar o 🆗 para aplicação manual |
| D09-04 | Deve ser criada automaticamente uma cópia de segurança da planilha antes de cada importação? | **Confirmado:** criar backup automático antes de cada importação |

## 4. Critério de fechamento

Atendido em 25/07/2026: Lilian validou os contratos e confirmou execução em seu computador, retenção do log por 12 meses, fallback manual do 🆗 com aviso e backup automático antes de cada importação. A Gaveta 10 — Operação — pode ser aberta.
