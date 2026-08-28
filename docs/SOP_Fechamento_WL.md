# SOP — Fechamento Quinzenal WL

**Versão:** 1.0 — validada em 25/07/2026  
**Responsável:** Lilian  
**Periodicidade:** duas vezes por mês

## 1. Objetivo

Executar o fechamento quinzenal a partir das mensagens do grupo `AWL x Expedição Prellog`, com conferência humana, prevenção de duplicidade, preservação das fórmulas e rastreabilidade.

## 2. Gatilho e limites

- Gatilho: Lilian decide iniciar o fechamento da quinzena encerrada.
- 1ª quinzena: dias 1 a 15.
- 2ª quinzena: dia 16 ao último dia do mês.
- Início: seleção do mês, ano e quinzena.
- Fim: planilha conferida e enviada manualmente para Deise.

## 3. Entradas e saídas

### Entradas

- sessão autorizada do WhatsApp no computador de Lilian;
- mensagens, fotos, álbuns e PDFs do grupo em escopo;
- mensagens textuais de Estaca no padrão aprovado, como `16x10=600`;
- planilha oficial com aba quinzenal e tabela de valores;
- decisões de Lilian para pendências.

### Saídas

- aba quinzenal preenchida e conferida;
- backup anterior à importação;
- log de mensagens, decisões, duplicidades, importações e erros;
- fechamento enviado a Deise.

## 4. Responsabilidades

| Atividade | Automação | Lilian | William |
|---|---|---|---|
| Selecionar período | Calcula o intervalo | Informa mês, ano e quinzena | — |
| Ler evidências | Executa | Confere pendências | — |
| Interpretar dúvida | Não decide | Decide | É consultado por Lilian quando necessário |
| Aplicar 🆗 | Executa após captura; avisa se falhar | Faz manualmente no fallback | — |
| Aprovar/editar/rejeitar | Não aprova | Decide | — |
| Criar backup | Executa | Confirma em caso de erro | — |
| Importar | Executa após autorização | Autoriza | — |
| Conferir resultado | Valida fórmulas | Faz a conferência final | — |
| Enviar a Deise | Não envia | Executa | — |

## 5. Procedimento padrão

1. Confirmar que o WhatsApp está conectado e que a planilha correta está disponível.
2. Iniciar uma nova execução e informar mês, ano e quinzena.
3. Conferir o intervalo calculado e a aba de destino.
4. A automação percorre somente as mensagens do período no grupo autorizado.
5. Mensagens já marcadas com 🆗 são registradas como já processadas e não são lançadas novamente.
6. A automação abre e captura integralmente fotos, álbuns e todas as páginas dos PDFs.
7. Dados completos seguem para normalização e agrupamento; dúvidas viram pendências.
   - Para texto de Estaca, o primeiro número vira Peça e a Quantidade é o segundo número multiplicado pelo terceiro; Dimensões e Volume unitário ficam vazios.
8. Depois da captura integral, a automação aplica 🆗. Se falhar, registra `OK PENDENTE` e avisa Lilian.
9. Lilian revisa a área temporária e escolhe `APROVAR`, `EDITAR` ou `REJEITAR`.
10. Antes da importação, a automação verifica datas, chaves, duplicidades, aba de destino e fórmulas-base.
11. A automação cria um backup da planilha.
12. Lilian autoriza a importação.
13. A automação escreve somente os campos de origem e replica as fórmulas.
14. A automação valida os quatro campos calculados e registra erros.
15. Lilian realiza a conferência final da aba.
16. Lilian resolve manualmente os `OK PENDENTE`.
17. Lilian envia o fechamento para Deise.
18. A execução recebe o estado `ENCERRADA`.

Na primeira utilização, Lilian seleciona o arquivo oficial. A automação valida se ele contém as abas, fórmulas e tabela esperadas, memoriza sua localização e mostra o nome para confirmação antes das execuções seguintes. O arquivo de teste não deve ser confundido com o arquivo oficial.

Os backups são cópias completas do arquivo oficial e ficam na subpasta automática `Backups Fechamento`, ao lado da planilha. Avisos imediatos aparecem na tela da automação; os detalhes permanecem na aba `CONFERÊNCIA AUTO`.

## 6. Regras de parada

Não importar quando houver:

- data da mensagem vazia;
- período ou aba divergentes;
- linha sem aprovação;
- possível duplicidade não resolvida;
- fórmula-base ausente;
- planilha indisponível;
- falha na criação do backup;
- campo obrigatório pendente.

Uma pendência de uma evidência não precisa bloquear a leitura das demais. Ela bloqueia apenas a aprovação e a importação das linhas afetadas.

## 7. Recuperação

### Interrupção do computador ou navegador

Retomar a mesma execução pelo log. Não reiniciar tudo como uma execução nova sem verificar as mensagens já capturadas.

### Falha do 🆗

Continuar a preparação, registrar `OK PENDENTE`, avisar Lilian e apresentar a lista de mensagens para reação manual.

### Erro na importação

Parar o lote, manter as linhas na área temporária, registrar o erro e usar o backup se a planilha tiver sido alterada parcialmente.

### Fórmula com erro

Não corrigir preço, cadastro ou fórmula automaticamente. Encaminhar para Lilian e manter o fechamento aberto.

## 8. Registros

O log deverá ser guardado por 12 meses. Backups seguem a política operacional aprovada e não devem ser apagados junto com o log sem confirmação.
