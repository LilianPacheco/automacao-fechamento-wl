# Tratamento de Novos Erros — Fechamento WL

## 1. Na hora do fechamento

1. Não adivinhar nem forçar a importação.
2. Bloquear apenas a evidência ou linha afetada.
3. Continuar os itens independentes quando for seguro.
4. Mostrar a evidência e uma descrição simples do problema.
5. Lilian decide a correção imediata e consulta William quando necessário.
6. Registrar o que foi feito.

## 2. Depois do fechamento

Para cada erro novo, registrar:

- período e mensagem de origem;
- imagem, página ou linha afetada;
- comportamento esperado;
- comportamento ocorrido;
- solução manual usada;
- causa conhecida ou ainda desconhecida;
- decisão de Lilian.

## 3. Quando virar nova regra

O caso só entra oficialmente na automação depois de:

1. ser compreendido;
2. ter uma regra escrita sem ambiguidade;
3. receber aprovação de Lilian;
4. atualizar PRD, SRS/ETO ou Regras do Agente quando necessário;
5. ganhar um teste reproduzível;
6. passar pelo teste antes do próximo uso real.

## 4. Quando não virar regra

Manter como exceção isolada quando:

- a evidência de origem estiver simplesmente errada;
- o caso não se repetir e não houver regra segura;
- a correção depender de decisão humana;
- a mudança ampliar o escopo para outro grupo ou processo.

## 5. Proibições

- Não alterar regra silenciosamente durante um fechamento.
- Não usar um único caso duvidoso para generalizar.
- Não ocultar a divergência porque o valor final parece correto.
- Não declarar o erro resolvido sem testar a correção.
