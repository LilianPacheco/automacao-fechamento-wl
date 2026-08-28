# Projeto: Automação do Fechamento Quinzenal — WL (v1.1)

**Data da consolidação:** 25/07/2026  
**Responsável de negócio:** Lilian  
**Método:** 12 Gavetas  
**Objetivo desta versão:** consolidar as Gavetas 01–04 e abrir formalmente a Gaveta 05 sem antecipar decisões técnicas.

## 1. Status controlado das gavetas

| # | Gaveta | Status | Critério atual |
|---|---|---|---|
| 00 | Mandato | Fechada | Problema, autoridade e objetivo definidos |
| 01 | Contexto e Escopo | **Fechada em 25/07/2026** | SIPOC, fronteiras, papéis, inclusões e exclusões definidos |
| 02 | Evidências | **Fechada para descoberta em 25/07/2026** | Fontes inventariadas, gravações analisadas e limitações declaradas |
| 03 | Ontologia | **Fechada em 25/07/2026** | Conceitos, fontes dos campos, chave de agrupamento e controle de processado confirmados |
| 04 | AS-IS | **Fechada em 25/07/2026** | Fluxo, exceções, autoridade e encerramento confirmados |
| 05 | Baseline | **Fechada em 25/07/2026** | Baseline mínima aceita para uso interno: 3 horas e 8.000–9.000 peças por fechamento |
| 06 | Diagnóstico | **Fechada em 25/07/2026** | Causa raiz e limites da automação confirmados pela responsável |
| 07 | TO-BE | **Fechada em 25/07/2026** | Agrupamento, revisão temporária, momento do OK e finalização confirmados |
| 08 | Solução e TI | **Fechada em 25/07/2026** | Fluxo completo provado, incluindo WhatsApp, duplicidade e importação aprovada na cópia |
| 09 | Contratos | **Fechada em 25/07/2026** | PRD, SRS/ETO, Regras do Agente e rastreabilidade validados |
| 10 | Operação | **Fechada em 25/07/2026** | SOP, instrução, checklist, seleção do arquivo, backups e avisos validados |
| 11 | Medição contínua | **Fechada em 25/07/2026** | Indicadores, resumo automático e ciclo de novos erros validados |

“Fechada para descoberta” significa que há evidência suficiente para descrever o trabalho atual. Não significa que já existam amostras técnicas suficientes para construir e testar um extrator.

## 2. Gaveta 00 — Mandato (mantida fechada)

- **Problema:** o fechamento quinzenal é manual e consome aproximadamente 3 horas por execução.
- **Autoridade:** Lilian decide, confere e resolve ambiguidades de negócio.
- **Objetivo:** reduzir drasticamente o tempo operacional, mantendo conferência humana antes do lançamento definitivo.
- **Restrição central:** a automação prepara e propõe; a aprovação continua humana.

## 3. Gaveta 01 — Contexto e Escopo (fechada)

### 3.1 SIPOC

| Elemento | Definição consolidada |
|---|---|
| Fornecedores | Participantes dos grupos/conversas do WhatsApp Business; emissão dos romaneios Prellog/OHQ; responsáveis pelas fotos de etiquetas |
| Entradas | Mensagens no período, fotos de etiquetas, romaneios de cargas em PDF e planilha “MEDIÇÕES AWL – 2026” com suas tabelas/fórmulas |
| Processo | Selecionar quinzena → localizar movimentações → abrir evidências → extrair/agrupar dados → preparar linhas → conferir → levar à aba oficial → enviar a Deise |
| Saídas | Aba da quinzena preenchida e conferida; fechamento disponibilizado/enviado a Deise |
| Clientes | Lilian (operação e aprovação) e Deise (recebimento do fechamento) |

### 3.2 Fronteiras

- **Gatilho:** encerramento de uma quinzena ou acionamento manual para preparar seu fechamento.
- **Início operacional:** selecionar o período e localizar, nas conversas pertinentes, todas as movimentações datadas nele.
- **Fim operacional:** registros conferidos na aba oficial e fechamento encaminhado a Deise.
- **Periodicidade:** 1ª quinzena = dias 1–15; 2ª quinzena = dia 16 ao último dia do mês.

### 3.3 Dentro do escopo

- Coletar as evidências da quinzena nas fontes autorizadas.
- Extrair dados de romaneios e fotos de etiquetas.
- Normalizar e, quando a regra for confirmada, agrupar registros.
- Preparar uma área temporária de conferência.
- Sinalizar dados ausentes, ilegíveis, conflitantes ou duplicados.
- Transferir somente registros aprovados para a aba oficial, preservando fórmulas.
- Manter rastreabilidade entre linha preparada e evidência de origem.

### 3.4 Fora do escopo nesta fase

- Criar ou corrigir romaneios, etiquetas ou mensagens de origem.
- Alterar fórmulas, tabelas de preço ou cadastros da planilha oficial.
- Aprovar movimentações sem ação humana.
- Enviar automaticamente o fechamento a Deise antes da aprovação.
- Automatizar faturamento, nota fiscal, cobrança ou processos posteriores ao envio, ainda não evidenciados.
- Assumir integração oficial com WhatsApp ou Excel sem prova técnica na Gaveta 08.

### 3.5 Regras já confirmadas

- Toda movimentação pertinente presente nas conversas do período participa do fechamento.
- Há pelo menos dois tipos de entrada: romaneio em PDF e foto de etiqueta.
- A planilha oficial contém fórmulas e tabelas de referência que devem ser preservadas.
- Volume total, unidade de medida, valor unitário e valor total permanecem calculados pela planilha; a automação não preenche esses quatro campos.
- A automação não escreve diretamente na aba oficial antes da conferência humana.
- Lilian mantém autoridade sobre aprovação e exceções.
- Qualquer peça cuja obra seja `CEJEN - PORTO IMBITUBA` deve ser classificada como `METRO CÚBICO`, independentemente do Produto ou código. A automação não calcula o volume total nem os valores; essas fórmulas permanecem na planilha.

### 3.6 Pendências que não bloqueiam mais a Gaveta 01

- Quantidade média de cargas/movimentações por quinzena: medir na Gaveta 05.
- Frequência de PDFs fora do padrão, fotos ilegíveis e mensagens incompletas: quantificar nas Gavetas 05 e 08.
- Disponibilidade de API/forma de coleta do WhatsApp: provar na Gaveta 08.

### 3.7 Critério de saída da Gaveta 01

Atendido: há dono, fornecedores, entradas, macroprocesso, saídas, clientes, início, fim, inclusões, exclusões e autoridade de exceção. Dúvidas de volume e tecnologia foram corretamente encaminhadas às gavetas responsáveis.

## 4. Gaveta 02 — Evidências (fechada para descoberta)

### 4.1 Evidências analisadas

| ID | Evidência | Conteúdo/uso | Integridade SHA-256 |
|---|---|---|---|
| EV-01 | `metodo-gavetas.html` | Critérios metodológicos das 12 gavetas | `EBD8E7968A057041F3A6B293B06D110C58D8EEE691B4FA15AC043EE4D2E37913` |
| EV-02 | `Projeto_Automacao_Fechamento_WL.md` | Primeira consolidação do caso | `05783E090250C01075E0C6165410F703C27375AB62636EE50442B1021CB9168B` |
| EV-03 | `Projeto_Automacao_Fechamento_WL_v1.0.md` | Regras e arquitetura futura já decididas | `0F8554C8A0015A7A2462B538A64210B023E618004EA73D2BB0CA1CC4ECAA49BF` |
| EV-04 | `Fechamento - Claude.mp4` | Gravação principal, 11:22, 1914×1058, com áudio | `65DBB72BE842913564BCD480E276641E106246DD0414B3B0EEA5CFFA69634204` |
| EV-05 | `Fechemento - Claude 1.mp4` | Gravação complementar, 1:13, 1912×1060, com áudio | `3A535792761F3ABC163FB7A4298E1516776A9D7D8DAE8D3D936BD4A09D8774C4` |
| EV-06 | `Fechemento - Claude 1.zip` | Contêiner com cópias dos dois vídeos | `EFF79888419C619142879400735A087357208927CAC8A0D68A2A99E6C328AB04` |

Os caminhos de origem permanecem em `C:\Users\lilia\Downloads\Automatização`. As imagens em `evidencias/` são derivados de análise e não substituem os arquivos originais.

### 4.2 Constatações visuais da gravação principal

| Intervalo aproximado | Fato observado |
|---|---|
| 00:00–00:20 | A operadora abre a aba da 2ª quinzena de julho na planilha “MEDIÇÕES AWL – 2026” |
| 00:20–01:10 | Acessa o grupo “AWL x Expedição Prellog”, localiza fotos e um PDF de carga |
| 01:10–03:10 | Mantém romaneio e Excel lado a lado e inicia a digitação de uma linha de medição |
| 03:10–05:10 | Consulta mensagens/novo romaneio e a tabela de referência da planilha; continua o lançamento |
| 05:10–06:20 | Completa campos no Excel a partir do romaneio |
| 06:20–11:22 | Abre sucessivas fotos de etiquetas e digita novos registros no Excel, alternando continuamente entre fonte e destino |

Na primeira amostra, várias peças do romaneio resultam em uma linha consolidada na medição. A responsável confirmou posteriormente a regra de agrupamento registrada na Gaveta 03.

### 4.3 Constatações da gravação complementar

- Mostra novamente o grupo “AWL x Expedição Prellog”.
- Exibe foto de peças e conjunto de etiquetas.
- Abre um romaneio de cargas e aproxima sua tabela.
- Confirma que a busca manual por evidências continua além do trecho principal.

### 4.4 Riscos e limitações das evidências atuais

- Não foi fornecida uma cópia editável da planilha; fórmulas, validações, nomes definidos e proteção não puderam ser testados.
- Não foram fornecidos PDFs e fotos originais isolados; ainda não é possível medir precisão de extração ou OCR.
- A gravação demonstra exemplos, mas não prova que todos os romaneios usem o mesmo layout.
- O vídeo não prova, sozinho, como detectar duplicidade nem qual data prevalece em casos divergentes; essas regras foram posteriormente confirmadas pela responsável e registradas na Gaveta 03.
- O áudio não foi usado como fonte normativa; decisões vêm dos documentos e dos fatos visuais verificáveis.

### 4.5 Critério de saída da Gaveta 02

Atendido para análise de processo: fontes registradas, exemplos observados, sequência rastreável, contradições e limitações explícitas. Antes do protótipo técnico, a Gaveta 08 exigirá amostras originais representativas e uma cópia segura da planilha.

## 5. Gaveta 03 — Ontologia (fechada)

O dicionário controlado, as regras confirmadas e o registro das decisões estão em `Gaveta_03_Ontologia.md`.

## 6. Gaveta 04 — AS-IS (fechada)

O fluxo atual formalizado está em `Gaveta_04_AS_IS.md`. Seu encadeamento principal é:

1. Definir a quinzena e abrir a aba correspondente.
2. Percorrer manualmente grupos/conversas do WhatsApp.
3. Ignorar mensagens que já possuam a reação de OK da responsável e analisar as demais.
4. Abrir PDF ou foto e interpretar seus campos.
5. Consultar a tabela auxiliar quando necessário.
6. Agrupar apenas itens com a mesma data da mensagem, obra, produto/tipo, código da peça, dimensões e volume unitário.
7. Digitar os dados na planilha e deixar suas fórmulas preencherem os campos calculados.
8. Marcar no WhatsApp a evidência concluída com uma reação de OK.
9. Repetir a alternância entre WhatsApp e Excel para cada evidência.
10. Conferir o conjunto.
11. Finalizar na aba oficial e encaminhar a Deise.

Esta sequência foi confirmada pela responsável. Em caso de informação ilegível ou dúvida, nada é inferido: o item fica pendente para decisão de Lilian, que consulta William quando necessário. O OK só é aplicado após o lançamento integral do conteúdo da mensagem. Outros grupos ficam fora do escopo atual, e o processo termina quando o fechamento é enviado a Deise.

## 7. Próximo marco

Iniciar a construção do piloto operacional. As Gavetas 00 a 11 estão concluídas; requisitos, arquitetura, autonomia, operação, recuperação e medição contínua foram aprovados por Lilian.
