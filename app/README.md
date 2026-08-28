# Aplicativo Fechamento WL

Primeira versão do aplicativo Windows para o fechamento quinzenal.

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

## O que ainda não faz

- não extrai o conteúdo das fotos ou PDFs;
- não importa linhas na planilha oficial.

Essas funções serão adicionadas por incrementos, sempre testadas primeiro em cópia segura.

O teste do WhatsApp é somente leitura: não reage nem envia mensagens. Antes de
iniciar, mantenha somente uma aba do WhatsApp Web aberta no perfil `AWL` e deixe
o grupo correto visível. Abas duplicadas podem disputar o resultado da leitura.

Na integração com a extensão, o perfil visível `AWL` corresponde internamente ao
diretório `Profile 2` do Chrome. O aplicativo não abre novas abas; se o WhatsApp
não estiver aberto, ele apenas apresentará um aviso.

## Executar no ambiente de desenvolvimento

Use `Executar_Fechamento_WL.bat` na raiz do projeto.

## Testes

```powershell
python -m unittest discover -s app/tests -v
```
