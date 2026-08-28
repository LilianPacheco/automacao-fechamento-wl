# Instrução de Uso — Automação do Fechamento WL

**Versão:** 1.0 — validada em 25/07/2026  
**Público:** Lilian

> Os nomes exatos dos botões poderão ser ajustados depois da construção da tela. A sequência e as decisões desta instrução são obrigatórias.

## 1. Antes de começar

O aplicativo será instalado no Windows e terá um atalho na área de trabalho. A instalação será necessária apenas na primeira vez ou quando houver uma atualização.

1. Ligue o computador e confirme a conexão com a internet.
2. No perfil `AWL` do Chrome, abra o WhatsApp Web e confirme que sua conta está conectada.
3. Mantenha somente uma aba do WhatsApp Web aberta e deixe o grupo `AWL x Expedição Prellog` visível.
4. Não abra duas execuções do fechamento ao mesmo tempo.
5. Confirme que a planilha oficial não está sendo editada por outra pessoa.
6. Abra a automação e verifique se aparece `Pronto para iniciar`.

Na primeira utilização, escolha o arquivo que será a planilha oficial. Pode ser o arquivo original `MEDIÇÕES AWL - 2026`, desde que a validação confirme as abas, fórmulas e tabela necessárias. Depois disso, a automação memoriza o arquivo; nas próximas execuções, apenas confira o nome mostrado na tela.

## 2. Escolher o fechamento

1. Clique em `Novo fechamento`.
2. Selecione o mês.
3. Informe o ano.
4. Selecione `1ª quinzena` ou `2ª quinzena`.
5. Confira as datas mostradas.
6. Confira o nome da aba de destino.
7. Clique em `Iniciar leitura`.

Se o período ou a aba estiverem errados, cancele e corrija antes de continuar.

## 3. Acompanhar a leitura

A tela deverá mostrar:

- mensagens encontradas;
- mensagens já processadas;
- evidências capturadas;
- pendências;
- mensagens com `OK PENDENTE`;
- progresso da leitura do período.

Os avisos curtos aparecem nessa tela. Informações que precisam continuar disponíveis — pendências, erros, duplicidades e 🆗 pendentes — também ficam registradas na aba `CONFERÊNCIA AUTO` da planilha.

Você não precisa baixar fotos ou PDFs. Não feche o WhatsApp enquanto a captura estiver em andamento.

Quando aparecer uma mensagem textual de Estaca, como `16x10=600`, a automação mostrará `ESTACA`, Peça `16` e Quantidade `6.000`. Dimensões e Volume unitário aparecerão vazios, conforme a regra aprovada. Se os três números não estiverem claros, a mensagem aparecerá como pendente.

## 4. Revisar a área temporária

Para cada linha:

1. Confira Data, Obra, Tipo, Quantidade, Peça, Dimensões, Volume unitário e Tipo de carga.
2. Use a referência da origem para abrir a mensagem quando necessário.
3. Escolha uma ação:
   - `APROVAR`: os dados estão corretos;
   - `EDITAR`: corrija o campo e registre o motivo;
   - `REJEITAR`: a linha não deve entrar no fechamento.
4. Nunca aprove linha com data vazia.
5. Se não conseguir ler ou confirmar um campo, mantenha como pendente e consulte William quando necessário.

## 5. Autorizar a importação

1. Termine a revisão das linhas que deseja importar.
2. Confira o resumo: aprovadas, editadas, rejeitadas, pendentes e duplicidades.
3. Clique em `Preparar importação`.
4. Aguarde a confirmação `Backup concluído`.
5. Confira novamente a aba de destino.
6. Autorize a importação.

A automação preencherá apenas os campos de origem. Volume total, unidade e valores serão calculados pela planilha.

O backup é uma cópia completa do arquivo oficial, criada automaticamente na pasta `Backups Fechamento` ao lado da planilha. Você não precisa criar essa pasta nem outra planilha manualmente.

## 6. Conferir depois da importação

1. Abra a aba quinzenal.
2. Confira se as linhas importadas aparecem na data correta.
3. Confira se não existem linhas duplicadas.
4. Confira se Volume total, Unidade de medida, Valor unitário e Valor total foram calculados.
5. Se aparecer erro de fórmula, não altere a regra da automação: mantenha o fechamento aberto e corrija o cadastro ou a planilha com segurança.

## 7. Resolver OK pendente

Se a automação avisar que não conseguiu reagir:

1. Abra a lista `OK PENDENTE`.
2. Use o atalho para abrir cada mensagem.
3. Aplique manualmente a reação 🆗.
4. Marque a pendência como resolvida.

## 8. Encerrar

1. Faça a conferência final da aba.
2. Confirme que não há linha aprovada aguardando importação.
3. Confirme que pendências não resolvidas estão registradas.
4. Envie a planilha ou o fechamento para Deise.
5. Marque a execução como `ENCERRADA`.

## 9. Se algo der errado

### A automação parou

Abra novamente e escolha `Retomar fechamento`. Confira o período antes de continuar.

### O WhatsApp desconectou

Reconecte sua conta. Retome a execução; não crie outra para o mesmo período.

### A planilha não abre

Feche outras janelas do Excel, confirme o arquivo correto e tente novamente. Não force a importação.

### A importação alterou algo inesperado

Pare a execução, não salve novas alterações manuais e use a opção de recuperação pelo backup criado antes da importação.

### Há uma informação duvidosa

Não adivinhe. Mantenha a linha pendente e confirme com William quando necessário.
