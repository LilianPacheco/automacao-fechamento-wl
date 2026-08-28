# Prova técnica — Gaveta 08

**Data:** 25/07/2026  
**Resultado:** aprovada integralmente. A Gaveta 08 foi fechada após o bloqueio de uma duplicidade e a importação de uma linha nova aprovada na cópia, com fórmulas replicadas sem erros.

## 1. Insumos testados

- Cópia editável de `MEDIÇÕES AWL - 2026 - Automatização.xlsx`.
- `Carga 29.pdf` e `Carga 115.pdf`.
- Um romaneio em imagem e dez fotos de etiquetas.
- Regras confirmadas nas Gavetas 03, 04 e 07.

O arquivo oficial de origem não foi alterado. A prova foi exportada como `outputs/019f9ade-a6c7-7c42-89d1-d8a87bd84d05/Prova_Tecnica_Fechamento_WL.xlsx`.

## 2. Estrutura da planilha confirmada

A planilha contém dez abas quinzenais, uma aba `TABELA` e uma aba `RELAÇÃO DE PEÇAS FÁBRICA`. Nas abas atuais:

- volume total é calculado pela fórmula da planilha; a automação não o preenche nem o recalcula;
- unidade e valor unitário vêm da aba `TABELA`;
- valor total depende da unidade de cobrança;
- `PEÇAS ESTOQUE` é a grafia literal usada para o tipo de carga.

A nova aba `CONFERÊNCIA AUTO` mantém os dados propostos separados das abas oficiais e oferece `APROVAR`, `EDITAR` e `REJEITAR`.

## 3. Validação principal

O PDF `Carga 29.pdf` contém 21 itens idênticos com:

- obra `AMPLIAÇÃO ALUMÍNIO SJ`;
- produto `VIGA`, grupo `TERÇA T`;
- peça `TP1`;
- seção `24X30`;
- comprimento `11,34`;
- volume unitário `0,320`.

O motor de regras gerou uma única linha `VIGA TERÇA`, quantidade 21. Essa saída coincide com a linha já existente em `2ª quinz.julho`, inclusive dimensões, volume total e valores calculados. Isso comprova a regra de agrupamento para a amostra.

## 4. Demais agrupamentos preparados

Foram gerados 27 agrupamentos ao todo:

- 1 agrupamento da Carga 29;
- 5 agrupamentos das fotos de etiquetas;
- 2 agrupamentos do romaneio em imagem da Carga 34;
- 19 agrupamentos da Carga 115.

Exemplos de normalização observados:

- `PAINEL - MACIÇO → PAINEL`;
- `VIGA` + grupo `TERÇA → VIGA TERÇA`;
- `VIGA - RETANGULAR` + comprimento `11,025 → VIGA 10,1m ATÉ 15,55m`.

Portanto, Tipo tem origem em Produto, mas deve ser normalizado pelas regras e pela tabela da planilha.

## 5. Pendências preservadas sem adivinhação

- Os PDFs testados não possuem camada textual; são documentos escaneados e exigem OCR/visão.
- Os arquivos baixados não conservam a data da mensagem do WhatsApp nos metadados. A data impressa no romaneio e a marca da câmera são apenas referências e não substituem a data da mensagem.
- A quantidade 81 de `VTE-1-A`, na Carga 115, foi reconciliada pelo total de 102 peças, mas permanece marcada para revisão devido a uma página sem conteúdo visível na renderização.
- Nenhum OK foi aplicado durante a prova offline.

## 6. Verificações do arquivo exportado

- 13 abas presentes: as 12 originais mais `CONFERÊNCIA AUTO`.
- 27 linhas agrupadas para conferência.
- Nenhum erro de fórmula encontrado na nova área.
- Formatação, fórmulas, listas de ação e estados foram renderizados e inspecionados após a exportação.

## 7. Decisão técnica resultante

A parte local do piloto pode seguir com:

1. OCR/visão para PDFs escaneados e etiquetas;
2. validação de confiança, sem completar campos duvidosos;
3. motor determinístico de normalização e agrupamento;
4. aba temporária no Excel para revisão humana;
5. importação na aba oficial somente após aprovação.

A Gaveta 08 foi fechada em 25/07/2026. A prova localizou o grupo `AWL x Expedição Prellog`, navegou pelo período, reconheceu datas, horários, fotos, álbuns, PDFs e identificadores únicos. A `Carga 29.pdf` foi capturada integralmente, recebeu 🆗 e teve sua duplicidade bloqueada ao coincidir com `2ª quinz.julho!A7:M7`. Em seguida, a etiqueta `PL-14-B`, enviada em 24/07/2026 às 10:46, foi capturada, recebeu 🆗, passou pela área temporária e foi aprovada por Lilian. A linha nova entrou em `2ª quinz.julho!A11:M11`; os campos de origem foram escritos e as fórmulas replicadas produziram `0,419 m³`, unidade `PÇ`, valor unitário `R$ 25,00` e total `R$ 25,00`, sem erros.

As linhas 8, 9 e 10 sem data são exemplos preexistentes da cópia, não saídas válidas da automação. No fechamento real, cada linha deverá trazer a data da respectiva mensagem do WhatsApp, e a ausência dessa data bloqueará a importação.
