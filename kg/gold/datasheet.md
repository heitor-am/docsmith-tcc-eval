# KG Gold Set — Datasheet (`kg-gold/1`)

Documentação de proveniência e validade do gold set de entidades/relações usado
pelo harness `eval/kg/score_kg.py`. Segue o espírito de *Datasheets for Datasets*.

## Resumo

- **20 páginas** de diário oficial municipal (PI), 1 página = 1 documento.
- **649 anotações de entidade** (566 entidades canônicas distintas; 47 recorrem
  em mais de um documento) e **546 relações**.
- Vocabulário: 28 classes de entidade + 12 predicados, derivados de
  `eval/ontology/juridico-diarios.json` (ver `eval/kg/ontology_ref.json`).

## Composição (corpus misto — para validar parsers)

| Fonte | Docs | Entidades | Relações | Origem |
|---|---|---|---|---|
| Escaneado | 10 | 269 | 171 | `diarios-municipios-pi` (interior PI, imagem) |
| Born-digital | 10 | 383 | 375 | `dom-teresina` (Prefeitura de Teresina, texto nativo) |

Estratificado por tipo de ato (decreto, edital, contrato, aditivo, dispensa,
inexigibilidade, ratificação, pregão, ata, portaria, lei, convênio, licitação).
Seleção em `eval/kg/sample.json` (determinística; páginas born-digital filtradas
por sinal de estrutura de ato para excluir caudas de tabela).

## Protocolo de anotação

- **Anotador:** agente (LLM, modelo da sessão), um subagente por página.
- **Fonte autoritativa por origem:** escaneado → imagem renderizada (200–340 dpi);
  born-digital → camada de texto nativa (sem erro de OCR a herdar).
- **Cobertura de página inteira:** todos os atos de todos os municípios presentes
  na página são anotados (o sistema extrai a página inteira → P/R justo).
- **Adjudicação:** nível de decisão (o usuário, especialista de domínio, aprovou
  as regras de reconciliação, as decisões de modelagem e o escopo; revisão item a
  item de 600+ entidades é inviável e foi explicitamente dispensada). Ver
  "Decisões".

## Decisões de modelagem (aprovadas)

1. **Sem predicado para vínculos que o sistema não extrai:** CNPJ→empresa e
   signatário→ato não têm predicado na ontologia; CNPJs e signatários ficam como
   entidades sem relação (não penaliza o sistema por algo que não lhe foi pedido).
2. **"Lei 14.131/2021"** é typo recorrente das gazetas → consolidado na canônica
   `Lei nº 14.133/2021`; formas de superfície preservadas verbatim em `mentions`.
3. **Mapeamentos de tipo** (vocabulário sem classe dedicada): Termo de Fomento →
   `Convenio`; Apostilamento → `AditivoContratual`; despacho de adjudicação/
   homologação e Termo de Autorização (MIP) → `Ratificacao`; Ata de Registro de
   Preços → `Ata`.
4. **Contratante** = órgão/secretaria (não o município) quando o ato o nomeia;
   o município é entidade separada ligada por `localizadoEm`.

## Reconciliação cross-doc (mapa canônico)

Entidades de mesma identidade real entre documentos foram fundidas para um único
`canonical_id` em duas passadas: (1ª) por (tipo, nome canônico normalizado) — 27
fusões; (2ª) por forma de superfície distintiva compartilhada de mesmo tipo — +19
fusões (resolve variantes de nome, ex.: SEMEC e "Ampla Saúde Ambiental"). Inclui
órgãos (ex.: Fundação Municipal de Saúde, 5→1), leis, CNPJs, empresas/pessoas
recorrentes, e atos referenciados em páginas-irmãs (Inexigibilidade 021/2025,
Dispensa 038/2025). Menções genéricas/anafóricas ("este decreto", "a lei"…) foram
removidas das `mentions` (não são formas identificadoras). **Datas e valores NÃO
foram fundidos** mesmo quando o texto coincide (datas/valores iguais em atos
distintos são tratados como entidades distintas por ato). Isso define o ground
truth de over/under-merge da resolução.

## Ameaças à validade

- **Anotador é um LLM** (não humano), com adjudicação humana em nível de decisão,
  não item a item — gold "agente-anotado, decisão-adjudicado", não dupla anotação
  humana independente; sem cálculo de IAA clássico.
- **Reconciliação por (tipo, nome normalizado)** pode, em tese, fundir homônimos;
  neste corpus os 28 candidatos detectados eram identidade genuína.
- **Born-digital** confia na camada de texto da fonte (assume-se fiel por ser
  nativa).
- **Cobertura de tipos rara:** alguns tipos (Resolucao, Convenio, Inexigibilidade)
  têm poucas instâncias → métricas por-tipo nesses são ruidosas.
- Páginas truncadas (atos que continuam na página seguinte) têm o ato anotado
  apenas com os campos visíveis na página amostrada.

## Versão

`schema_version: kg-gold/1`. Ontologia: `2.1-diarios-pi-kgeval`. Data: 2026-06-01.
Arquivos: `entities/<file_name>.json`, `relations/<file_name>.json`,
`canonical.json`, mais `../sample.json`, `../annotation-guide.md`,
`../ontology_ref.json`.
