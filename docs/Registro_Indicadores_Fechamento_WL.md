# Registro de Indicadores — Fechamento WL

Este é o contrato de dados da futura aba `RESUMO EXECUÇÃO`. Os valores serão preenchidos automaticamente.

| Campo | Origem automática |
|---|---|
| Execução | Identificador do fechamento |
| Período | Mês, ano e quinzena selecionados |
| Início | Horário de início |
| Fim | Horário do encerramento |
| Duração | Diferença entre início e fim |
| Peças analisadas | Soma das quantidades processadas |
| Mensagens processadas | Contagem de mensagens do período capturadas |
| Evidências processadas | Contagem de fotos, álbuns e PDFs |
| Linhas aprovadas | Contagem da decisão `APROVAR` |
| Linhas editadas | Contagem de linhas corrigidas por Lilian |
| Linhas rejeitadas | Contagem da decisão `REJEITAR` |
| Linhas importadas | Contagem do estado `IMPORTADO` |
| Pendências | Contagem ainda aberta no encerramento |
| Duplicidades bloqueadas | Contagem do estado `DUPLICIDADE BLOQUEADA` |
| Erros de fórmula | Contagem de erros na validação pós-importação |
| OK pendentes | Contagem de reações manuais ainda necessárias |
| Backup | Nome/caminho do backup criado |
| Enviado a Deise | Confirmação humana de encerramento |

## Alertas automáticos

- `VERMELHO`: duplicidade importada, linha importada sem data ou erro de fórmula não resolvido.
- `AMARELO`: pendência ou 🆗 manual ainda aberto.
- `VERDE`: execução encerrada, sem erro crítico, com envio confirmado.

Os registros do resumo e do log serão mantidos por 12 meses.
