# CR-001 — Entrada textual de Estaca

**Data:** 26/07/2026  
**Solicitante e aprovadora:** Lilian  
**Estado:** aprovada para implementação no piloto

## 1. Nova fonte de entrada

Além de fotos de etiquetas e romaneios em PDF, o fechamento poderá receber uma mensagem de texto no formato:

`16x10=600`

## 2. Interpretação aprovada

| Parte | Uso |
|---|---|
| `16` — antes do `x` | Peça |
| `10` — entre `x` e `=` | Multiplicador |
| `600` — depois do `=` | Valor-base |
| `10 × 600` | Quantidade final = `6.000` |

Campos gerados:

- Tipo: `ESTACA`;
- Data: data da mensagem do WhatsApp;
- Obra: conforme contexto informado na mensagem ou tratado como pendência se ausente;
- Quantidade: `6.000`;
- Peça: `16`;
- Dimensões: vazio;
- Volume unitário: vazio;
- Tipo de carga: `PEÇAS ESTOQUE`.

## 3. Regras de segurança

- A automação multiplica o número entre `x` e `=` pelo número depois de `=`.
- O número antes do `x` nunca entra no cálculo; ele identifica a Peça.
- Não converter `600` para metros ou aplicar divisão por 100. No exemplo aprovado, a Quantidade é exatamente `6.000`.
- Dimensões e Volume unitário permanecem vazios; não devem ser inferidos a partir da Peça.
- Se uma das três partes estiver ausente ou ilegível, criar pendência e não calcular.
- A linha continua dependendo da data da mensagem e da aprovação de Lilian antes da importação.

## 4. Exemplo de teste obrigatório

Entrada: `16x10=600`  
Saída esperada: `ESTACA | Peça 16 | Quantidade 6.000 | Dimensões vazias | Volume unitário vazio`.
