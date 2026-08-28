# Matriz de Rastreabilidade — Gaveta 09

| ID | Regra/requisito | Origem | Contrato | Prova ou teste |
|---|---|---|---|---|
| RT-01 | Selecionar mês, ano e quinzena | Gaveta 08 §4.3 | PRD §3.1; SRS §2.1 | Navegação até 16/07 comprovada |
| RT-02 | Usar data da mensagem | Gaveta 03 decisão 1 | PRD RN-01 | PL-14-B importada com 24/07/2026 |
| RT-03 | Bloquear linha sem data | Gaveta 07 decisão 8 | PRD RN-01; Agente §4 | Linhas 8–10 identificadas como exemplos inválidos |
| RT-04 | Agrupar somente chaves iguais | Gaveta 03 decisões 2 e 3 | PRD RN-02; SRS §2.5 | Carga 29 agrupou 21 TP1 |
| RT-05 | CEJEN → METRO CÚBICO | Gaveta 03 decisão 10 | PRD RN-03; SRS §2.5 | Caso incluído no conjunto de prova local |
| RT-06 | VIGA + TERÇA T → VIGA TERÇA | Gaveta 03 decisão 11 | PRD RN-03; SRS §2.5 | Carga 29 classificada como VIGA TERÇA |
| RT-07 | Nunca usar TERÇA I | Confirmação de Lilian | PRD RN-03; Agente §4 | Busca documental sem variante ativa |
| RT-08 | Tipo de carga = PEÇAS ESTOQUE | Gaveta 03 decisão 6 | PRD §4.1; SRS §2.5 | Carga 29 e PL-14-B |
| RT-09 | Não inventar dúvida | Gaveta 07 §2 | PRD RN-05; Agente §4–5 | Amostras sem data ficaram pendentes |
| RT-10 | Área temporária com três ações | Gaveta 07 decisão 5 | PRD §3.3; SRS §2.6 | Dropdown APROVAR/EDITAR/REJEITAR |
| RT-11 | 🆗 após captura integral | Gaveta 07 decisão 3 | PRD RN-04; Agente §6 | Carga 29 e PL-14-B receberam 🆗 após captura |
| RT-12 | Aprovação humana antes da importação | Gaveta 07 §6 | PRD §3.3; Agente §3 e §7 | PL-14-B importada após autorização explícita |
| RT-13 | Bloquear duplicidade | Gaveta 07 §7 | PRD RN-06; SRS §2.7 | Carga 29 não foi duplicada |
| RT-14 | Escrever apenas campos de origem | Gaveta 03 decisão 13 | PRD §4; SRS §2.7 | PL-14-B escreveu A:H e J |
| RT-15 | Fórmulas calculam quatro campos | Gaveta 03 decisão 13 | PRD §4.2; SRS §2.7 | PL-14-B: 0,419; PÇ; R$25; R$25 |
| RT-16 | Rastrear origem e estados | Gaveta 03 §2 | PRD §2; SRS §2.8 | CONFERÊNCIA AUTO e LOG IMPORTAÇÃO |
| RT-17 | Outro grupo fora do escopo | Gaveta 04 | PRD §3.2 e §6; Agente §4 | Contrato documentado; teste futuro |
| RT-18 | Envio para Deise permanece manual | Gaveta 07 decisão 4 | PRD §2 e §6; Agente §4 | Contrato documentado; teste operacional futuro |
| RT-19 | Retomada segura | Diagnóstico/Gaveta 08 | SRS §5–6 | Teste futuro obrigatório |
| RT-20 | Recuperação da planilha | Critério de segurança | PRD §7 e §9; SRS §3 | Backup automático aprovado antes de cada importação |
| RT-21 | Retenção do log por 12 meses | Decisão D09-02 | PRD §9; SRS §2.8 | Teste futuro de limpeza por data |
| RT-22 | Fallback manual do 🆗 com aviso | Decisão D09-03 | PRD §7; SRS §3; Agente §6 | Teste futuro de falha simulada |
| RT-23 | Texto `16x10=600` → ESTACA, Peça 16, Quantidade 6.000, dimensões/volume vazios | CR-001; confirmação de Lilian em 26/07/2026 | PRD RN-07; SRS §2.4; Agente §2 e §4 | Teste obrigatório do parser no piloto |

## Cobertura atual

- Regras provadas tecnicamente: RT-01 a RT-16.
- Regras contratuais para validação operacional: RT-17 a RT-19.
- Decisões contratuais concluídas: RT-20 a RT-22; testes operacionais seguem para as Gavetas 10 e 11.
