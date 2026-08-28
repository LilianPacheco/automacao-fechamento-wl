# Gaveta 03 — Ontologia

**Status:** fechada em 25/07/2026  
**Dona das definições:** Lilian  
**Objetivo:** impedir que palavras iguais representem regras diferentes na planilha, na origem e na futura automação.

## 1. Dicionário controlado inicial

| Termo | Definição operacional proposta | Fonte/estado |
|---|---|---|
| Fechamento quinzenal | Conjunto conferido das movimentações pertencentes a uma quinzena, registrado na aba correspondente e encaminhado a Deise | Confirmado |
| Quinzena | 1ª: dias 1–15. 2ª: dia 16 ao último dia do mês | Confirmado |
| Movimentação | Evento ainda não marcado com OK, evidenciado em conversa autorizada, que deve produzir ou compor um registro de medição | Confirmado |
| Evidência de origem | Mensagem e seu anexo (PDF ou foto), com conversa, remetente, data/hora e posição rastreáveis | Proposto |
| Romaneio de cargas | Documento PDF tabular de uma carga, com cabeçalho da obra/carga e itens transportados | Observado |
| Foto de etiqueta | Imagem de etiqueta fixada à peça, contendo obra, peça/produto, seção, comprimento, peso, volume e identificadores | Observado |
| Carga | Agrupamento logístico identificado no romaneio; pode conter vários itens físicos | Proposto |
| Linha-fonte | Item individual ou agrupamento mostrado no romaneio/etiqueta antes da transformação | Proposto |
| Linha de medição | Registro da planilha que consolida itens integralmente iguais e do mesmo dia, com tipo, data, obra, quantidade, peça, dimensões, volume unitário e tipo de carga | Confirmado |
| Obra | Destino/empreendimento ao qual a movimentação pertence | Observado; falta regra de normalização |
| Tipo | Classificação da planilha derivada do campo **Produto** da etiqueta/romaneio e, quando necessário, do grupo, da faixa de comprimento ou de uma regra prioritária por obra | Confirmado e tecnicamente detalhado na Gaveta 08 |
| Peça | Código da peça presente na etiqueta ou no romaneio; integra obrigatoriamente a chave de agrupamento | Confirmado |
| Quantidade | Soma das peças que possuem todos os campos de agrupamento iguais e pertencem à mesma data de mensagem | Confirmado |
| Dimensões | Composição da **seção** com o **comprimento** informados na etiqueta ou no romaneio | Confirmado |
| Volume unitário | Valor de volume informado na peça/etiqueta ou na linha correspondente do romaneio | Confirmado |
| Volume total | Resultado calculado pela planilha para a linha; não deve ser sobrescrito pela automação | Confirmado em especificação anterior |
| Tipo de carga | Valor fixo da planilha **PEÇAS ESTOQUE** para as movimentações deste processo/grupo | Confirmado |
| Unidade de medida | Unidade física da cobrança, como `PÇ`, `m` ou `m³`; é diferente de valor unitário e vem das fórmulas/tabela da planilha | Confirmado; não preencher pela automação |
| Valor unitário | Valor obtido pelas fórmulas/tabela oficial; não deve ser digitado pela automação | Confirmado |
| Valor total | Resultado calculado pela planilha; não deve ser digitado pela automação | Confirmado |
| Registro pendente | Linha que não pode ser aprovada por falta, ilegibilidade, conflito ou possível duplicidade | Proposto |
| Aba temporária | Área onde a automação apresenta os registros e alertas para conferência | Confirmado como decisão de arquitetura, ainda sem desenho técnico |
| Aba oficial | Aba quinzenal que conserva fórmulas e recebe somente registros aprovados | Confirmado |
| Conferência humana | Decisão de aceitar, corrigir ou rejeitar cada proposta antes do lançamento oficial | Confirmado |
| OK no WhatsApp | Reação aplicada pela responsável à mensagem/evidência depois de seu lançamento; indica que aquele conteúdo já foi processado | Confirmado |

## 2. Identidade e rastreabilidade propostas

Cada registro preparado deverá conservar, no mínimo:

- conversa/grupo de origem;
- data e hora da mensagem;
- remetente;
- nome ou identificador do anexo;
- página/linha do PDF ou identificação visual da foto;
- chave de carga, quando houver;
- estado: preparado, pendente, aprovado, rejeitado ou importado;
- motivo da pendência/correção.

Esses metadados podem ficar na aba temporária ou em um log separado; não precisam alterar as colunas da aba oficial.

## 3. Decisões aprovadas pela responsável

1. **Data da linha:** é sempre a data da mensagem no WhatsApp, não a data do romaneio.
2. **Agrupamento:** itens só compartilham uma linha quando pertencem ao mesmo dia e todos os campos relevantes são iguais. A chave mínima é `data da mensagem + obra + tipo/produto + código da peça + seção + comprimento + volume unitário + tipo de carga`.
3. **Separação:** qualquer diferença em data, obra, tipo/produto, código, seção, comprimento ou volume gera outra linha.
4. **Controle de processado:** a reação de OK aplicada à mensagem no WhatsApp indica que seu conteúdo já foi lançado. A ausência do OK torna a mensagem candidata à análise.
5. **Tipo:** tem origem no campo **Produto**, mas o valor lançado é normalizado conforme a tabela oficial. Exemplos provados: `PAINEL - MACIÇO → PAINEL`; `VIGA` com grupo `TERÇA → VIGA TERÇA`; `VIGA - RETANGULAR → faixa de comprimento da viga`.
6. **Tipo de carga:** é sempre **PEÇAS ESTOQUE**, conforme a grafia usada na planilha oficial.
7. **Dimensões:** são formadas pela seção e pelo comprimento da peça.
8. **Volume unitário:** é copiado do volume informado para a peça.
9. **Foto e romaneio:** podem compor a mesma linha quando forem do mesmo dia e todos os campos de agrupamento forem iguais; em dias diferentes permanecem separados.
10. **Exceção CEJEN - PORTO IMBITUBA:** qualquer movimentação cuja obra seja `CEJEN - PORTO IMBITUBA` deve usar o Tipo `METRO CÚBICO`, independentemente do Produto, código ou espécie da peça. Essa regra de obra tem prioridade sobre a normalização comum de Tipo. A automação apenas define o Tipo; unidade, volume total e valores continuam calculados pelas fórmulas da planilha.
11. **Viga Terça:** fora da exceção de obra acima, quando o Produto for `VIGA` e o Grupo do romaneio for `TERÇA T`, o Tipo lançado será `VIGA TERÇA`. Não existe variante `TERÇA I` nesta regra. A tabela oficial define a unidade como metro linear (`m`).
12. **Prioridade das regras de Tipo:** primeiro verificar `CEJEN - PORTO IMBITUBA → METRO CÚBICO`; depois verificar `VIGA + Grupo TERÇA T → VIGA TERÇA`; somente então aplicar as demais normalizações de Produto e faixa de comprimento.
13. **Campos calculados:** a automação não preenche `Volume total`, `Unidade de medida`, `Valor unitário` nem `Valor total`. Depois que os campos de origem forem inseridos, as fórmulas e a tabela oficial da planilha devem preencher os quatro.
14. **Entrada textual de Estaca:** uma mensagem no formato `16x10=600` deve ser interpretada como Tipo `ESTACA`, Peça `16` e Quantidade `10 × 600 = 6.000`. O número antes do `x` identifica a Peça; o número entre `x` e `=` multiplica o número posterior ao `=`. Dimensões e Volume unitário ficam vazios e não são inferidos.

## 4. Critério de fechamento

Atendido: a responsável confirmou a data oficial, a identidade da peça, a fonte de tipo, dimensões e volume, o valor de tipo de carga, a chave de agrupamento e o controle de conteúdo já processado.

## 5. Próxima gaveta

A Gaveta 04 foi aberta para desenhar o AS-IS com, no mínimo, estas decisões: pertence à quinzena? já tem OK? a fonte está legível e completa? todos os campos de agrupamento são iguais? a fórmula retornou erro? a conferência aprovou?
