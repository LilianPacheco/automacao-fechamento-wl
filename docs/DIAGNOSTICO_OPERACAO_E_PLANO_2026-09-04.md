# Diagnóstico da operação e plano de estabilização — Fechamento WL

Data: 04/09/2026. Natureza: auditoria e proposta, não implementação.

## 1. Conclusão executiva

O problema não é apenas reconhecer letras. A operação mistura coleta, navegação no WhatsApp, associação de legendas, interpretação, aprovação e gravação. Um erro de associação pode produzir um fechamento errado mesmo com OCR perfeito.

O objetivo continua adequado: funcionários enviam fotos e textos como já fazem; o sistema preserva as evidências, interpreta os documentos, apresenta somente dúvidas reais e escreve os dados aprovados na planilha existente. Não exige QR nas etiquetas, mudança de impressão ou digitação adicional pelos funcionários.

Não há evidência suficiente para considerar o produto pronto operacionalmente. Os testes documentados de componentes e de escrita em cópia não comprovam captura completa de uma quinzena real, precisão dos campos nem igualdade dos totais com o fechamento manual.

## 2. Base e limites da auditoria

Inspecionados: PRD, SRS/ETO, relatório de validação de 04/09, extensão, ponte Chrome, serviços de OCR/visão, construção/persistência da revisão, gravação Excel e registros locais de captura/revisão.

Referências locais: `docs/PRD_Fechamento_WL.md`, `docs/SRS_ETO_Fechamento_WL.md`, `docs/VALIDACAO_MVP_2026-09-04.md` e arquivos citados abaixo. Não foi realizada nesta auditoria uma nova captura completa ao vivo nem comparação experimental de modelos. Riscos encontrados por inspeção não significam que todas as ocorrências históricas tiveram a mesma causa.

O lote `local_20260816_20260831_451cf6bb15/revisao_temporaria.json`, em AppData/Roaming/WL Fechamento/Capturas, contém 180 registros: 88 CONFIRMAR, 1 PENDENTE, 83 PRONTO PARA REVISÃO e 8 CONFIRMADO. Portanto, há 89 pendências explícitas, mas os demais estados não demonstram que os campos estejam corretos. Esse lote não é diretamente comparável ao relato histórico de mais de 80% de validação nem ao lote de 169 imagens do relatório de testes.

## 3. Causas e riscos encontrados

| Etapa | Evidência no código | Consequência |
|---|---|---|
| Captura | `content_v185.js`, `wlCollectPeriodEvidence`: faz upload/captura de anexos dentro dos ciclos que percorrem o histórico. | Abrir galeria interrompe a navegação; referências da tela podem deixar de existir. Uma falha em álbum atrasa ou interrompe o restante. |
| Cobertura | Dependência de calendário, rolagem e datas observadas. | Não encontrar dia 16 não prova ausência de movimento. Encontrar dia 17 e dia 31 também não prova que nada foi pulado entre eles. |
| Recuperação | Retomada por posições e nomes `foto_N`, sem identidade autoritativa de cada membro de álbum. | A memória de posições não equivale a uma fila persistente e reconciliada. A alteração anterior não entregou a separação completa prometida. |
| Identidade | Há associações por prefixos/horários e deduplicação por hash de mídia. | Duas mensagens legítimas podem ser confundidas; bytes iguais não provam que se trata do mesmo lançamento. |
| OCR | `paddle_ocr_service.py`, `read_text`: reúne textos e média de confiança, descartando coordenadas na saída consumida pela interpretação. | Números perdem sua relação espacial com cabeçalhos como comprimento, volume e quantidade. |
| Recortes | `vision_service.py`, `FIELD_BANDS`: faixas proporcionais fixas; seleção da maior região candidata de etiqueta. | Layouts diferentes, romaneios e várias etiquetas na mesma imagem não seguem necessariamente essas posições. |
| Confiança | `decide_fields`: confiança da leitura e concordância de passes são usadas para aceitar campos; alguns campos aceitam um único suporte. | Confiança alta do OCR não comprova que o número pertence ao campo correto. Repetições do mesmo mecanismo podem repetir o mesmo erro. |
| Entradas omitidas | `review_service.py`, `build_advanced_review_drafts`: seleciona anexos de imagem. | O fluxo principal não transforma as mensagens textuais de Estaca nem as páginas PDF em lançamentos nessa etapa. |
| Quantidade | `_apply_message_quantity`: pode aplicar a quantidade da mensagem em vários registros derivados dela. | Uma quantidade total de legenda pode ser multiplicada indevidamente pelas fotos/linhas do álbum. |
| Contexto | Enriquecimento pode propagar obra por concordância de fotos do grupo; normalização ocorre também antes do contexto completo. | Um álbum misto pode contaminar obras; regras dependentes da obra podem ser avaliadas sem ela. |
| Revisão | Reprocessamento grava novos resultados; persistência utiliza chave mensagem + arquivo, insuficiente para várias linhas do mesmo documento. | Risco de perder correções e de colidir registros distintos de um romaneio. |
| Progresso | A última foto é anunciada antes de enriquecimento, consolidação e salvamento. | “180 de 180” parece conclusão, mas ainda há trabalho sem progresso específico. |
| Excel | `workbook_writer_service.py`: fallback usa fórmulas predefinidas; validação é principalmente estrutural. | Estrutura válida não comprova preservação da lógica da planilha nem resultados calculados corretos. |
| Reimportação | O escritor não reconcilia identidades de evidências já importadas no destino. | Executar novamente pode acrescentar os mesmos lançamentos. Agrupar o lote não resolve duplicidade entre execuções. |

Exemplo observado: um resultado OCR de romaneio apresenta sequências como “Metros”, “1,00”, “Motorista”, “32”, “Comprimento”, “8,00” em ordem textual desconectada da tabela. A foto pode ser legível para uma pessoa, mas o interpretador recebe uma lista que já perdeu a estrutura necessária. A solução é preservar posições e relações entre células, não apenas aumentar a imagem.

## 4. Lacunas entre PRD e decisões posteriores

O PRD já prevê boa parte da arquitetura necessária, mas não está totalmente implementado nem atualizado com as decisões posteriores:

- Retirar reação 🆗 como requisito de funcionamento: a usuária explicitamente a dispensou.
- Incorporar todos os formatos aprovados de Estaca. Nas expressões informadas, multiplicar os dois últimos números; em romaneio, usar os metros totais das linhas de Estaca. Não contar luvas como metros e não somar novamente um total já consolidado.
- Manter PH e PP como códigos distintos; nunca aplicar substituição global.
- Data do lançamento deve vir da mensagem, não da data impressa na etiqueta.
- Produto e tipo devem usar opções exatas da tabela; vigas acima de 25 m usam a faixa máxima, sem truncar o comprimento real.
- Resolver explicitamente a precedência entre “produto igual a tipo” e exceções anteriores como cobrança por METRO CÚBICO em determinada obra. Não apagar a exceção silenciosamente.
- Editar um campo não deve confirmar a peça; confirmação e aprovação são ações explícitas.
- Agrupamento legítimo de peças iguais no mesmo dia deve preservar quantidade e todas as evidências de origem.

Os limites e nomes das faixas devem vir da tabela oficial e de regras aprovadas, não de aproximação textual. Intervalos com aparentes lacunas precisam de regra explícita de arredondamento/comparação.

## 5. Arquitetura recomendada

```text
Grupo WhatsApp existente
        ↓
Coletor de mensagens e anexos, sem OCR
        ↓
Arquivo local de evidências + fila persistente
        ↓
Classificar: etiqueta / romaneio / texto Estaca / PDF
        ↓
Extrair campos com localização e origem
        ↓
Aplicar regras determinísticas da planilha
        ↓
Revisar somente campos incertos → aprovação explícita
        ↓
Backup → gravar na aba certa → recalcular → conferir → registrar importação
```

### Captura

Priorizar coleta incremental: guardar novas mensagens enquanto o coletor estiver conectado e recuperar lacunas após reconexão. A busca retrospectiva da quinzena passa a ser recuperação, não o único modo de funcionamento. Isso reduz dependência de abrir centenas de fotos no dia do fechamento; não garante recuperação de mídia que o WhatsApp já não disponibiliza.

Cada mensagem deve guardar identidade do grupo e da mensagem, remetente, horário, texto original, referências de resposta, relação de álbum quando disponível e anexos. Cada anexo deve ter identidade própria, hash, tamanho, situação e tentativas. Falha em uma foto não deve apagar as outras nem reiniciar toda a coleta.

Uma alternativa a testar é um adaptador orientado a mensagens, como whatsapp-web.js: a documentação expõe identificador, corpo, autor, horário e download de mídia. Isso é tecnicamente mais adequado à associação foto–legenda do que inferir tudo pela posição na tela. Porém, é uma integração não oficial, sujeita a mudanças e risco de bloqueio da conta; não deve ser instalada na conta de trabalho sem decisão informada. Tampouco garante histórico completo. Fontes: [Message](https://docs.wwebjs.dev/Message.html) e [aviso do projeto](https://github.com/wwebjs/whatsapp-web.js#disclaimer).

Decisão proposta: comparar esse adaptador e a extensão corrigida em um ensaio pequeno de histórico, álbum com legenda, reconexão e mensagem nova. Selecionar pelo resultado e pelo risco aceito, não substituir tudo com promessa de estabilidade não demonstrada. Se a integração não oficial for inaceitável, manter a extensão com fila durável e explicitar suas limitações; não fingir que a dependência do WhatsApp desapareceu.

### Interpretação

Separar os documentos antes de extrair campos. Etiquetas exigem pares rótulo/valor e coordenadas; romaneios exigem linhas e colunas; PDFs exigem leitura de todas as páginas; mensagens Estaca exigem parser textual, não OCR.

Preservar texto, caixa delimitadora, página/foto de origem e método para cada campo. Corrigir perspectiva/orientação e fazer recorte ampliado quando necessário. Comparar OCR com estrutura de layout e um modelo de visão documental numa amostra real. PaddleOCR possui recursos de extração documental além da saída de texto simples atualmente consumida: [projeto oficial](https://github.com/PaddlePaddle/PaddleOCR).

Não escolher um “melhor modelo” só pela propaganda. Usar 50–100 documentos representativos já corrigidos, separando exemplos de ajuste e avaliação. Medir acerto exato por campo: peça, obra, comprimento, volume, quantidade e data. Incluir layouts diferentes, PH/PP, várias etiquetas, romaneios, decimais e legendas.

Executar segunda leitura somente quando útil: dúvida, conflito ou campo crítico sem comprovação. Registrar a origem e a divergência. Confiança automática deve ser calibrada contra a amostra; não confundir a média de confiança das letras com a probabilidade de um lançamento correto. Validação geométrica serve para detectar inconsistências, nunca para inventar o volume da etiqueta.

Uso de modelo externo é hipótese sujeita a avaliação de custo e autorização para transmitir documentos. Nenhuma mídia foi enviada a um novo fornecedor nesta auditoria.

### Revisão e Excel

Manter resultado extraído separado da correção humana. Cada linha de romaneio ganha identidade própria. Reprocessar cria nova versão, não sobrescreve aprovação. Mostrar documento ao lado do campo duvidoso, com motivo específico.

Guardar o vínculo entre legenda e quantidade: por foto, mensagem, álbum ou resposta. Só aplicar automaticamente quando o alcance for comprovado; não replicar uma quantidade total em todas as fotos. Dúvida de alcance é uma pendência específica.

Na escrita: backup, identificação inequívoca da aba, preservação das fórmulas existentes, prévia das alterações e registro dos IDs importados. Repetir a mesma operação deve produzir zero linhas novas. Uma evidência corrigida após importação requer procedimento explícito de substituição, não nova soma silenciosa.

Recalcular com o Excel e conferir células e totais após gravar. A Microsoft disponibiliza `CalculateFullRebuild` para recálculo completo; isso deve integrar a verificação, não ser substituído por abrir o arquivo com fórmulas como texto. [Documentação Microsoft](https://learn.microsoft.com/en-us/office/vba/api/excel.application.calculatefullrebuild).

## 6. Plano priorizado e evidência de conclusão

| Ordem | Entrega | Como comprovar |
|---|---|---|
| P0 — referência | Congelar cópia do app e selecionar um lote real com gabarito; atualizar regras conflitantes do PRD. | Inventário esperado e resultados manuais conhecidos, sem alterar originais. |
| P0 — integridade | Identidades estáveis, persistência, isolamento por quinzena, preservação de correções e bloqueio de importação repetida. | Reiniciar, reprocessar e executar duas vezes sem perda de edição ou duplicação. |
| P1 — captura | Inventário separado do download, recuperação por anexo e teste de transporte. | Todas as mensagens e mídias disponíveis do lote auditado associadas corretamente às legendas; indisponíveis explicitadas. |
| P1 — interpretação | Incluir texto/PDF/romaneio, corrigir alcance de quantidade e preservar layout OCR. | Todos os tipos de entrada do lote geram resultados rastreáveis, sem números isolados atribuídos por aproximação. |
| P2 — precisão | Comparar extratores e calibrar aceitação por campo. | Relatório em amostra não usada no ajuste, com erros e pendências discriminados. |
| P2 — fechamento | Gravação transacional, recálculo e reconciliação com manual. | Linhas, quantidades, metros, volumes e valores conferidos em cópia da planilha. |
| P3 — operação | Um único app, versão/caminho visíveis, progresso por etapa e diagnóstico acessível. | Instalação/reabertura no computador da usuária e execução completa sem comandos técnicos. |

Must Have: integridade, cobertura auditável, todos os tipos de evidência, proveniência por campo, revisão persistente, fórmulas preservadas e não duplicação. Should Have: coleta incremental e recuperação automática. Could Have: otimização de custo/velocidade e refinamento visual. Fora: reações, QR nas etiquetas, digitação obrigatória pelos funcionários e automação de envio de mensagens.

## 7. Critérios de aceite propostos

- CA001: dado um lote auditado, ao coletar, todas as mensagens/mídias disponíveis são contabilizadas; faltas têm identidade e motivo. Não chamar ausência de captura de “sem movimento”.
- CA002: dado dia inicial sem mensagem, ao percorrer o período, aceitar a primeira mensagem posterior somente com evidência de cobertura, sem inventar mensagem no dia inicial.
- CA003: ao interromper e retomar, manter anexos concluídos e continuar pendentes sem reassociar legendas.
- CA004: ao trocar mês/quinzena, nenhuma revisão de outro período aparece como resultado atual.
- CA005: ao editar um campo, manter a situação pendente até confirmação explícita; ao reprocessar, preservar a correção.
- CA006: foto de várias linhas gera registros independentes, sem colidir na persistência.
- CA007: expressões Estaca usam os dois últimos números; romaneios usam metros de Estaca; quantidade de legenda não é multiplicada por número de fotos sem justificativa.
- CA008: PH e PP distintos, produtos/tipos válidos, comprimento real preservado em viga acima de 25 m e faixa máxima aplicada.
- CA009: importar duas vezes o mesmo conjunto não duplica linhas; peças repetidas legítimas permanecem contabilizadas.
- CA010: fechamento em cópia coincide com o manual por linha e total, respeitando arredondamento documentado e fórmulas da planilha.

Metas propostas, ainda não atingidas/comprovadas: zero perda ou duplicação no lote auditado; 100% dos campos utilizados com origem rastreável; precisão de pelo menos 99% nos campos aceitos automaticamente na amostra separada; reduzir pendências para 10–15% dos registros se a qualidade dos documentos permitir. Medir também minutos ativos de revisão por fechamento. Esses percentuais são critérios de avaliação, não promessa de desempenho. Nenhuma taxa de acerto justifica ocultar dúvidas reais.

## 8. Preparação para a banca de 09/09

Priorizar um fluxo vertical real e reproduzível: evidências conhecidas → análise → dúvidas localizadas → aprovação → escrita em cópia → conferência com manual. Mostrar separadamente captura ao vivo e eventual recuperação de histórico. Uma demonstração baseada em lote salvo deve ser identificada como tal, nunca apresentada como prova de captura ao vivo completa.

Não é responsável garantir, antes desse ensaio, que todo o histórico da quinzena será capturado automaticamente até a data. A decisão de expansão deve depender do teste, não de mais uma troca de versão ou de uma contagem de testes unitários.

Próximo passo recomendado: montar o lote de referência usando evidências e correções já existentes, reproduzir o problema de associação/extração em poucos documentos e testar a captura orientada a mensagens antes de uma reescrita ampla. Não pedir à usuária que valide novamente centenas de peças para suprir uma falha técnica.
