# Prova de leitura do WhatsApp — 26/07/2026

## Objetivo

Comprovar, em modo somente leitura, que a automação consegue localizar o grupo
`AWL x Expedição Prellog` e carregar o histórico até a data inicial da segunda
quinzena de julho de 2026.

## Resultado

- WhatsApp Web autenticado: **comprovado**.
- Grupo correto localizado: **comprovado**.
- Data inicial procurada: **16/07/2026**.
- Data `16/07/2026` exibida no histórico do próprio grupo: **comprovado**.
- Mensagens posteriores de 17, 18, 19 e demais dias: **comprovadas**.
- Fotos e álbuns de fotos: **detectados**.
- PDF `Carga 115.pdf`: **detectado**.
- Reações 🆗 já existentes: **detectadas**.
- Mensagem textual `16×10=600`: **detectada**.
- Integração local Chrome/extensão versão `0.1.8`: **comprovada em 27/07/2026**.
- Tempo da comprovação final após eliminar abas duplicadas: **aproximadamente 8 segundos**.

## Como a prova foi feita

1. O WhatsApp abriu inicialmente nas mensagens mais recentes.
2. Nesse primeiro estado não havia prova de leitura desde 16/07.
3. A ação “carregar mensagens mais antigas do seu celular” foi executada.
4. Após duas etapas de carregamento, o marcador explícito `16/07/2026`
   apareceu no painel de mensagens do grupo.
5. Somente então o período foi considerado carregado.
6. Na validação do aplicativo em 27/07/2026, abas duplicadas do WhatsApp foram
   identificadas como fonte de resultados concorrentes. Mantendo uma única aba
   aberta no perfil `AWL`, o aplicativo confirmou o grupo e a data inicial.

## Regra implementada no piloto

O aplicativo não pode declarar que o período foi carregado apenas porque abriu o
grupo. Ele deve procurar o marcador da data inicial da quinzena escolhida. Se a
data não aparecer, o resultado será “histórico incompleto”.

## Segurança desta prova

- nenhuma reação foi adicionada;
- nenhuma mensagem foi enviada;
- nenhum arquivo foi baixado;
- nenhuma célula da planilha foi modificada.

## Validação automática — 28/07/2026

A versão `0.9.3` comprovou a navegação sem escolha manual da data:

- grupo `AWL x Expedição Prellog`: **localizado automaticamente**;
- calendário verdadeiro do WhatsApp: **identificado**;
- período iniciado em `16/07/2026`: **comprovado**;
- 13 datas tentadas automaticamente;
- evidências encontradas nos dias 16, 17, 18, 19, 20, 21, 22, 24, 26 e 27/07;
- 158 imagens brutas detectadas antes da remoção de miniaturas duplicadas;
- PDFs `Carga 29.pdf`, `Carga 115.pdf` e `Carga 130.pdf`: **detectados**;
- mensagem `16×10=600`: **detectada**;
- reações 🆗: **detectadas**;
- tempo total: **aproximadamente 57 segundos**;
- seleção manual da data inicial: **não necessária**;
- escrita na planilha: **nenhuma**.

A versão `0.9.4` acrescenta a remoção das miniaturas internas que também estavam
representadas pelo total do álbum. A próxima validação será feita junto com a
aquisição dos anexos, evitando uma atualização da extensão apenas para recontagem.
