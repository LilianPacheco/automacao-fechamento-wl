# Aplicativo Fechamento WL

Versão integrada do aplicativo Windows para o fechamento quinzenal.

## O que esta versão faz

- permite selecionar a planilha oficial;
- memoriza a localização validada;
- escolhe mês, ano e quinzena;
- calcula o intervalo correto;
- valida abas, cabeçalhos e tabela da planilha sem modificá-la;
- mostra avisos claros na tela;
- interpreta a entrada textual de Estaca, como `16x10=600`;
- contém o serviço de backup automático para a futura importação.
- usa a sessão já conectada do perfil `AWL` no Chrome;
- localiza o grupo `AWL x Expedição Prellog`;
- carrega o histórico até encontrar a data inicial da quinzena;
- informa fotos, PDFs, reações 🆗 e entradas de Estaca que estiverem visíveis.
- recupera uma leitura completa já salva da quinzena correta, sem misturar períodos;
- importa um ZIP exportado pelo WhatsApp ou uma pasta de fotos, sem controlar o navegador;
- reaproveita data, horário, remetente e quantidade do arquivo de conversa quando disponíveis;
- analisa as fotos com a Leitura Visual 2;
- mantém entradas editadas como pendentes até a confirmação explícita;
- permite filtrar pendentes, confirmados, aprovados e rejeitados;
- consolida somente os aprovados;
- grava na aba da quinzena selecionada após criar backup automático.

## Limite atual do piloto

A leitura visual é deliberadamente conservadora: quando um campo não pode ser
comprovado, somente esse registro fica pendente. A decisão final permanece com a
pessoa responsável antes da importação. A importação nunca inclui registros
pendentes, confirmados ou rejeitados: apenas os marcados como `APROVADO`.

O teste do WhatsApp é somente leitura: não reage nem envia mensagens. Antes de
iniciar, mantenha somente uma aba do WhatsApp Web aberta no perfil `AWL` e deixe
o grupo correto visível. Abas duplicadas podem disputar o resultado da leitura.

Na integração com a extensão, o perfil visível `AWL` corresponde internamente ao
diretório `Profile 2` do Chrome. O aplicativo não abre novas abas; se o WhatsApp
não estiver aberto, ele apenas apresentará um aviso.

O WhatsApp Web é opcional. Depois de validar a planilha e o período, use
`Importar fotos sem abrir o WhatsApp` para escolher um ZIP exportado pelo celular
ou uma pasta contendo apenas as evidências da quinzena. Fotos sem data
comprovável entram na revisão com a data pendente; o aplicativo não inventa a data.

## Executar no ambiente de desenvolvimento

Use `Executar_Fechamento_WL.bat` na raiz do projeto.

## Testes

```powershell
python -m unittest discover -s app/tests -v
```
