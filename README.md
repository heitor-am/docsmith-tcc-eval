# DocSmith — Artefatos de Avaliação (§5 do TCC)

Este repositório reúne os artefatos que sustentam os experimentos
relatados na Seção 5 do TCC *"DocSmith: Plataforma Distribuída de
Processamento Inteligente de Documentos com Busca Semântica"*.

O objetivo é permitir que a banca inspecione as consultas, o gold set
de anotações, o script de avaliação, o mecanismo de composição da
ontologia e os resultados brutos, e reproduza os experimentos sobre
uma instância própria do DocSmith.

## Escopo

O experimento compara quatro abordagens de busca sobre um mesmo
corpus e mede o ganho da fase de Graph RAG por meio de consultas
que exigem contexto entre documentos:

| Abordagem     | Descrição                                                    |
|---------------|--------------------------------------------------------------|
| Vanilla       | recuperação híbrida (densa + esparsa por RRF)                |
| HyDE          | *Hypothetical Document Embeddings*: LLM gera doc hipotético  |
| Query Fusion  | LLM gera variantes da consulta e funde os *rankings* por RRF |
| Graph RAG     | expansão pós-recuperação por entidades canônicas             |

## Estrutura

```
queries/
  queries.json        # 37 consultas com gold binário (documentos + entidades)
  queries-hard.json   # reformulações difíceis (eixo de descasamento de vocabulário)

ontology/
  juridico-diarios.json  # extensão JSON Merge Patch da ontologia jurídica built-in
  apply.py               # aplica o patch sobre uma coleção DocSmith

kg/
  annotation-guide.md    # metodologia de anotação do gold set
  gold/
    datasheet.md         # datasheet do gold (20 páginas, 649 entidades, 546 relações)
    canonical.json       # mapa de entidades canônicas (para resolução cross-document)
    entities/            # 20 arquivos: entidades anotadas por documento
    relations/           # 22 arquivos: relações anotadas por documento

scripts/
  run_eval.py         # roda vanilla/hyde/query_fusion + Graph RAG
  metrics.py          # Recall@K, MRR@K, latência p50/p95

results/
  metrics.json              # métricas agregadas do run canônico do TCC
  context_per_query.jsonl   # breakdown query-a-query: recall_base, recall_graph, hits
```

## Como reproduzir

Pré-requisitos:

- Uma instância do DocSmith exposta em `http://localhost:8004` (ou onde
  a variável `DOCSMITH_API_BASE` apontar) com uma coleção já ingerida
  e seu grafo de conhecimento construído.
- Uma chave de API válida (`X-API-Key`).
- Python 3.11+ com `httpx`, `numpy` e `scipy`.

### 1. Aplicar a extensão da ontologia

```bash
export DOCSMITH_API_KEY=sk-...
export DOCSMITH_COLLECTION_ID=<uuid-da-coleção>
python ontology/apply.py
```

Isso adiciona as classes de domínio (número do edital, secretaria
municipal, município, data de publicação) sobre a ontologia jurídica
*built-in* da coleção.

### 2. Executar o experimento

```bash
python scripts/run_eval.py \
    --queries queries/queries.json \
    --k 10 \
    --seeds 3
```

O resultado é escrito em `results/<timestamp>-sec5/metrics.json` no
mesmo formato de `results/metrics.json`.

## Gold Set (Knowledge Graph)

O diretório `kg/gold/` contém o gold set descrito na Seção 5.2 do TCC:
20 páginas anotadas manualmente com 649 anotações de entidade
(566 entidades canônicas distintas; 47 recorrem em mais de um documento)
e 546 relações. Vocabulário: 28 classes de entidade e 12 predicados
derivados de `ontology/juridico-diarios.json`.

O arquivo `kg/gold/datasheet.md` documenta proveniência, composição,
processo de anotação, versionamento e limitações no espírito do
*Datasheets for Datasets*.

As entidades canônicas em `kg/gold/canonical.json` são a fonte da
resolução *cross-document* discutida no estudo de caso (§5.3): a
entidade `silvio_mendes_oliveira_filho`, por exemplo, aparece nos
três documentos do gold da consulta c05 e forma as pontes que a
expansão via grafo percorre.

## Métricas

- **Recall@5, MRR@10** para as três estratégias de primeiro estágio
  (Vanilla, HyDE, Query Fusion), sobre as 37 consultas.
- **Δ = recall_graph − recall_base** para a fase de Graph RAG, sobre
  as 17 consultas *multidoc*+*crossdoc* que exigem contexto entre
  documentos. Reportado com intervalo de confiança 95% por *bootstrap*
  e teste de Wilcoxon pareado.
- **Latência** p50/p95 em milissegundos.

O arquivo `results/context_per_query.jsonl` traz o desempenho
query-a-query para o subconjunto de 17 consultas do Graph RAG
(`recall_base`, `recall_graph`, `hit_base`, `hit_graph`), permitindo
auditar cada consulta individualmente.

## Corpus

O corpus é composto de diários oficiais de municípios do Piauí e do
Diário Oficial do Município de Teresina. Todos os documentos são
públicos por definição legal (Lei de Acesso à Informação, LGPD).
O corpus não é redistribuído aqui: os PDFs originais estão disponíveis
nos portais dos respectivos municípios, e o gold de relevância
(campos `expected_documents` e `relevant_entities` em `queries.json`)
usa o nome de arquivo original para identificação.

## Modelos

A inferência de ML é servida pelo Mandu (ETIPI — Empresa de Tecnologia
da Informação do Piauí) através de interface OpenAI-compatível. As
instâncias utilizadas foram:

- Embedding denso: `BAAI/bge-m3` (1024 dimensões, multilingual)
- Embedding esparso: `Qdrant/bm25`
- LLM (HyDE, Query Fusion, extração de metadados): `Qwen/Qwen3.6-35B-A3B`

A transcrição de páginas digitalizadas usou `google/gemini-2.5-flash`
via OpenRouter, pois o catálogo do Mandu não oferecia modelo de visão
à época do experimento.

## Citação

Se este material foi útil, cite o TCC:

```
Heitor Andrade Moura, Raimundo Santos Moura.
"DocSmith: Plataforma Distribuída de Processamento Inteligente de
Documentos com Busca Semântica". TCC, Universidade Federal do Piauí
(UFPI), 2026.
```

## Licença

MIT (veja `LICENSE`).
