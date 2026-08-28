# PRD — Automação do Fechamento Quinzenal WL

**Versão:** 1.0 — validada em 25/07/2026  
**Responsável de negócio:** Lilian  
**Gaveta:** 09 — Contratos

## 1. Problema e objetivo

O fechamento quinzenal exige localizar mensagens, abrir fotos e romaneios, interpretar etiquetas, agrupar peças e digitar dados na planilha. O processo atual consome aproximadamente três horas e envolve de 8.000 a 9.000 peças por fechamento.

O produto deverá reduzir a transcrição e a comparação manuais, preservando a conferência de Lilian antes de qualquer lançamento na aba oficial.

## 2. Usuária e resultado esperado

**Usuária principal:** Lilian.  
**Recebedora do resultado:** Deise.

Ao final de uma execução, Lilian deverá ter:

- todas as mensagens do período em escopo verificadas;
- linhas completas e rastreáveis na área temporária;
- pendências separadas e explicadas;
- somente linhas aprovadas na aba quinzenal correta;
- fórmulas e tabela oficial preservadas;
- log das capturas, correções, aprovações, rejeições, duplicidades e importações;
- planilha pronta para conferência final e envio manual a Deise.

## 3. Escopo funcional

### 3.1 Início

Lilian informa `mês + ano + 1ª ou 2ª quinzena`.

- 1ª quinzena: dias 1 a 15.
- 2ª quinzena: dia 16 ao último dia do mês.

### 3.2 Fonte

- Grupo: `AWL x Expedição Prellog`.
- Entradas: fotos de etiquetas, romaneios em PDF e mensagens textuais de Estaca no formato aprovado.
- Outros grupos ficam fora do escopo atual.

### 3.3 Processamento

O produto deverá:

1. localizar as mensagens do período;
2. ignorar mensagens já reagidas com 🆗;
3. registrar grupo, remetente, data/hora, anexo e referência da evidência;
4. extrair todos os itens da mensagem, não apenas a primeira página ou foto;
5. criar pendência quando algo estiver ilegível, ausente ou duvidoso;
6. normalizar Tipo conforme as regras aprovadas;
7. agrupar somente itens do mesmo dia com todos os campos da chave iguais;
8. apresentar o resultado para revisão;
9. aplicar 🆗 depois da captura integral na área temporária;
10. permitir `APROVAR`, `EDITAR` e `REJEITAR`;
11. importar somente linhas aprovadas;
12. validar fórmulas e resultados depois da importação;
13. impedir duplicidades;
14. manter um log rastreável.

## 4. Campos do produto

### 4.1 Campos preenchidos pela automação

- Tipo;
- Data da mensagem;
- Obra;
- Quantidade;
- Peça;
- Dimensões, formadas por seção e comprimento;
- Volume unitário;
- Tipo de carga, sempre `PEÇAS ESTOQUE`.

### 4.2 Campos pertencentes à planilha

A automação não digita:

- Volume total;
- Unidade de medida;
- Valor unitário;
- Valor total.

Esses campos devem ser calculados pelas fórmulas e pela tabela oficial.

## 5. Regras de negócio obrigatórias

### RN-01 — Data

A data da linha é a data da mensagem do WhatsApp. Data do romaneio, data da etiqueta ou marca da câmera não a substituem. Linha sem data da mensagem não pode ser importada.

### RN-02 — Agrupamento

A chave mínima é:

`data da mensagem + obra + tipo + código da peça + seção + comprimento + volume unitário + tipo de carga`.

Somente chaves integralmente iguais podem somar quantidade. Dias diferentes sempre geram linhas separadas.

### RN-03 — Prioridade do Tipo

1. Obra `CEJEN - PORTO IMBITUBA` → `METRO CÚBICO`.
2. Fora dessa obra, Produto `VIGA` + Grupo `TERÇA T` → `VIGA TERÇA`.
3. Depois aplicar Produto e, para vigas, a faixa de comprimento cadastrada.

Não existe regra `TERÇA I`.

### RN-04 — Processado

O 🆗 na mensagem significa que seu conteúdo já foi integralmente capturado na área temporária. Aprovação e importação são estados separados.

### RN-05 — Dúvida

Nada pode ser adivinhado. Lilian decide e consulta William quando necessário.

### RN-06 — Duplicidade

Antes da importação, comparar a chave com a área temporária, o log e a aba de destino. Uma correspondência não pode gerar uma segunda linha silenciosamente.

### RN-07 — Entrada textual de Estaca

No padrão `16x10=600`:

- `16` → Peça;
- `10 × 600` → Quantidade `6.000`;
- Tipo → `ESTACA`;
- Dimensões e Volume unitário → vazios.

Não converter o valor `600` nem inferir dimensões ou volume. Formato incompleto ou duvidoso gera pendência.

## 6. Fora do escopo

- corrigir a evidência original;
- alterar fórmulas, preços ou cadastros da planilha;
- aprovar linhas sem Lilian;
- enviar automaticamente para Deise nesta versão;
- automatizar faturamento, nota fiscal ou cobrança;
- processar outros grupos.

## 7. Critérios de aceite do produto

1. O período escolhido limita corretamente as mensagens analisadas.
2. Cada linha contém a data real da mensagem.
3. Toda evidência é rastreável até o WhatsApp.
4. Nenhuma mensagem recebe 🆗 antes da captura integral.
5. Nenhuma linha entra na aba oficial sem aprovação.
6. Campos duvidosos produzem pendência, não suposição.
7. Agrupamentos respeitam integralmente RN-02.
8. Duplicidades são bloqueadas e registradas.
9. As fórmulas calculam os quatro campos reservados sem erros.
10. O arquivo original ou a versão anterior pode ser recuperado em caso de falha.

Se a aplicação automática do 🆗 falhar por mudança ou indisponibilidade do WhatsApp, o processamento pode continuar. O produto deverá avisar Lilian, marcar a mensagem como `OK PENDENTE` na área temporária e solicitar que a reação seja aplicada manualmente.

## 8. Indicadores do piloto

- tempo total por fechamento;
- número de peças processadas;
- número de mensagens e anexos analisados;
- percentual de linhas aprovadas sem edição;
- quantidade de pendências;
- duplicidades bloqueadas;
- erros de fórmula;
- intervenções manuais necessárias.

## 9. Retenção e execução aprovadas

- A automação rodará no computador de Lilian.
- O log operacional será guardado por 12 meses.
- Registros de log com mais de 12 meses poderão ser apagados automaticamente.
- Será criado backup automático da planilha antes de cada importação.
- Se o 🆗 automático falhar, Lilian será avisada e fará a reação manualmente.
