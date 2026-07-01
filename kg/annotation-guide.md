# KG Gold Annotation Guide (`kg-gold/1`)

Guia para anotar o gold set de entidades e relações usado pelo harness de
qualidade de KG (`eval/kg/score_kg.py`). Vale para o corpus de diários oficiais
municipais (jurídico/PI).

## Fonte autoritativa (depende da origem)

Corpus misto, com regra por fonte:

- **Escaneado** (`diarios-municipios-pi`, imagem): anotar **lendo a imagem
  renderizada da página** (200 dpi) — fiel ao escaneado. Não usar o text-layer
  sujo nem a transcrição do `pdf_vlm`. Manuscrito (assinaturas): só o legível.
- **Born-digital** (`dom-teresina`, texto nativo): anotar **lendo a camada de
  texto do PDF**, que é a fonte autoritativa (sem erro de OCR). Conferir contra
  a imagem só em caso de dúvida de layout (multi-coluna).

A origem de cada doc está em `sample.json` (`source`).

## Vocabulário controlado

Usar **apenas** os tipos de entidade e predicados de `eval/kg/ontology_ref.json`.
Se faltar um predicado claramente necessário, adicioná-lo a `ontology_ref.json`
(e anotar a mudança). Tipos principais: `Decreto`, `Edital`,
`ContratoAdministrativo`, `AditivoContratual`, `Inexigibilidade`, `Ratificacao`,
`DispensaLicitacao`, `LicitacaoModalidade`/`PregaoEletronico`/`TomadaPrecos`,
`Orgao`/`SecretariaMunicipal`, `MunicipioPI`, `Pessoa`, `Empresa`, `Valor`/
`ValorLicitacao`, `Objeto`, `Lei`, `CNPJ`, `Data`/`DataPublicacao`,
`NumeroProcesso`. Predicados: `temContratante`, `temContratada`, `temObjeto`,
`temValor`, `temFundamentoLegal`, `temModalidade`, `temVigencia`, `publicadoPor`,
`celebraContrato`, `decretadoPor`, `localizadoEm`, `temData`.

## Entidades

Para cada entidade realmente presente no documento, registrar:
- `canonical_id` — id **estável** (ex.: `e1`, `e2`...). **Reusar o mesmo id em
  documentos diferentes** quando for a mesma entidade do mundo real (ex.:
  "Prefeitura Municipal de Picos" recebe o mesmo id em todos os docs).
- `canonical_name` — forma canônica/display (a mais completa e correta).
- `type` — um tipo do vocabulário.
- `mentions` — formas de superfície **como aparecem na página** (incluir
  variações: maiúsculas, abreviações, com/sem acento). O `canonical_name` não
  precisa estar em `mentions`, mas pode estar.

Regras:
- Anotar entidades de conteúdo (órgãos, empresas, pessoas, valores, objetos,
  números de contrato/processo, leis, datas relevantes do ato). **Não** anotar
  boilerplate do cabeçalho do diário (ex.: "Verba Volant, Scripta Manent",
  numeração de edição) a menos que seja o próprio ato.
- Valores monetários: `type=Valor`, `canonical_name` = o valor por extenso +
  numérico como aparece (ex.: "R$ 2.188.232,04").
- CNPJ: `type=CNPJ`, valor verbatim.

## Relações

Para cada relação claramente afirmada pelo documento, registrar a tripla
`{subject_canonical_id, predicate, object_canonical_id}` usando ids já definidos
em entidades. Exemplos típicos de um extrato de contrato:
- contratante → `temContratante` → órgão
- contratada → `temContratada` → empresa
- contrato → `temObjeto` → objeto
- contrato → `temValor` → valor
- contrato → `temFundamentoLegal` → lei
- ato → `temModalidade` → modalidade de licitação

Só anotar relações **explícitas** no texto. Não inferir relações que o documento
não afirma.

## Canonicalização cross-doc

Antes de criar um novo `canonical_id`, verificar se a entidade já recebeu id em
outro doc do sample. Mesma entidade → mesmo id, unindo as `mentions`. Isso é o
que permite medir over/under-merge da resolução do sistema. O arquivo
`gold/canonical.json` é gerado a partir das anotações por doc (une surface forms
e doc_ids por `canonical_id`).

## Casos de borda

- **Homônimos** (mesmo nome, entidades distintas): ids diferentes; anotar no
  datasheet.
- **OCR ruído / texto ilegível**: usar a imagem como árbitro; omitir o ilegível.
- **Abreviações** (ex.: "PMP" para "Prefeitura Municipal de Picos"): adicionar
  como `mention` da entidade canônica.
- **Múltiplos atos na mesma página**: anotar todos; cada um é uma entidade de ato
  com suas relações.

## Protocolo

Anotador: agente (LLM) lendo as imagens. Adjudicador: usuário (especialista de
domínio) revisa **todos** os docs. O gold só é final após a adjudicação. A taxa
de alteração na adjudicação é registrada no `datasheet.md`.
