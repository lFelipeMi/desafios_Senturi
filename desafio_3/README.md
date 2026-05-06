Desafio 3: Arquitetura de Auditabilidade (RAG)
Cenário: Em conformidade com auditorias de ESG e segurança jurídica, a Senturi não pode exibir um risco no dashboard sem provar de onde ele veio.

Sua Tarefa: Explique a arquitetura e o fluxo de como você usaria a técnica de RAG (Retrieval-Augmented Generation) para garantir que o diagnóstico da IA seja baseado estritamente nos dados/relatos coletados, impedindo "alucinações", e permitindo que o usuário clique no insight e veja os textos que o fundamentam.

---

## O que é RAG e por que usá-lo aqui

RAG (Retrieval-Augmented Generation) é uma técnica onde, em vez de pedir para a IA gerar um diagnóstico "do zero" (o que causa alucinações), primeiro **buscamos** os relatos reais no banco e depois os **colocamos dentro do prompt** como material de consulta. A IA só pode gerar conclusões com base nesses relatos — como responder uma prova com consulta.

Isso resolve o problema de auditabilidade porque cada afirmação do diagnóstico vem acompanhada da citação do relato que a originou, e o gestor pode clicar e verificar.

---

## Fluxo Completo

```
1. Colaborador escreve relato aberto
                ↓
2. Sistema salva o relato no banco com seu embedding (vetor de significado)
                ↓
3. Dashboard solicita diagnóstico para um macrodomínio
                ↓
4. Sistema busca no banco os relatos mais relevantes para aquele domínio
                ↓
5. Relatos encontrados são inseridos no prompt da IA como contexto
                ↓
6. IA gera diagnóstico citando cada relato usado [RELATO-XXX]
                ↓
7. Sistema valida se as citações realmente existem
                ↓
8. Diagnóstico + fontes são salvos no log de auditoria e exibidos no dashboard
```

---

## Etapa 1 — Indexação dos Relatos (Embedding)

Cada relato do colaborador é transformado em um **embedding** — um vetor numérico que representa o significado do texto. Isso permite buscar relatos por similaridade de conteúdo, não apenas por palavras exatas.

```python
from openai import OpenAI

client = OpenAI()

def salvar_relato_indexado(relato_id: str, texto: str, metadata: dict):
    """
    Gera o embedding do relato e salva no banco junto com metadados
    rastreáveis (empresa, data, domínio classificado no Desafio 2).
    """
    embedding = client.embeddings.create(
        model="text-embedding-3-small",
        input=texto
    ).data[0].embedding
    
    db.execute("""
        INSERT INTO relatos_embeddings 
            (relato_id, texto_original, embedding, empresa_id, data_coleta, macrodominio)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        relato_id, texto, embedding,
        metadata["empresa_id"],
        metadata["data_coleta"],
        metadata["macrodominio"]
    ))
```

O banco utilizado é o PostgreSQL com a extensão **pgvector**, que permite fazer busca por similaridade de vetores direto no SQL, sem precisar de um banco separado.

---

## Etapa 2 — Busca dos Relatos Relevantes (Retrieval)

Quando o dashboard solicita um diagnóstico, o sistema busca os relatos mais relevantes usando similaridade vetorial:

```python
def buscar_relatos(pergunta: str, empresa_id: str, 
                   macrodominio: str, limite: int = 10) -> list[dict]:
    """
    Busca os relatos mais similares à pergunta por significado.
    O filtro de empresa_id isola os dados de cada empresa (multi-tenant).
    """
    embedding_pergunta = client.embeddings.create(
        model="text-embedding-3-small",
        input=pergunta
    ).data[0].embedding
    
    return db.execute("""
        SELECT relato_id, texto_original, data_coleta
        FROM relatos_embeddings
        WHERE empresa_id = %s AND macrodominio = %s
        ORDER BY embedding <=> %s
        LIMIT %s
    """, (empresa_id, macrodominio, embedding_pergunta, limite))
```

O operador `<=>` do pgvector calcula a distância entre vetores — relatos com significado mais próximo da pergunta aparecem primeiro.

---

## Etapa 3 — Geração do Diagnóstico com Citações (Augmented Generation)

Os relatos recuperados são inseridos no prompt com IDs identificáveis, e o modelo é instruído a citar cada fonte:

```python
PROMPT_SISTEMA = """
Você é um analista de risco ocupacional.
Gere um diagnóstico baseado EXCLUSIVAMENTE nos relatos abaixo.

REGRAS:
1. NÃO invente informações que não estejam nos relatos.
2. Cada afirmação DEVE citar a fonte no formato [RELATO-XXX].
3. Se não há relatos suficientes, diga "Evidência insuficiente".
4. Use trechos literais dos relatos entre aspas para fundamentar.

RELATOS DISPONÍVEIS:
{relatos_formatados}
""".strip()


def gerar_diagnostico(relatos: list[dict], macrodominio: str) -> dict:
    """Gera diagnóstico auditável com citações rastreáveis."""
    
    # Formata os relatos com IDs para a IA citar
    relatos_formatados = ""
    for r in relatos:
        relatos_formatados += (
            f"[RELATO-{r['relato_id']}] ({r['data_coleta']})\n"
            f"\"{r['texto_original']}\"\n\n"
        )
    
    # Chama a IA com Structured Output 
    resposta = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": PROMPT_SISTEMA.format(
                relatos_formatados=relatos_formatados
            )},
            {"role": "user", "content": f"Gere o diagnóstico para: {macrodominio}"}
        ],
        response_format=DiagnosticoAuditavel,
    )
    
    diagnostico = resposta.choices[0].message.parsed
    
    # Validação: confere se a IA não inventou citações que não existem
    ids_reais = {f"RELATO-{r['relato_id']}" for r in relatos}
    for citacao in diagnostico.citacoes:
        if citacao.fonte_id not in ids_reais:
            raise ValueError(f"Citação '{citacao.fonte_id}' não existe nos relatos.")
    
    return diagnostico
```

### Schema de Saída

```python
from pydantic import BaseModel, Field

class Citacao(BaseModel):
    """Referência a um relato usado como evidência."""
    fonte_id: str = Field(description="Ex: 'RELATO-142'")
    trecho_usado: str = Field(description="Trecho literal do relato citado")

class DiagnosticoAuditavel(BaseModel):
    """Diagnóstico com rastreabilidade completa."""
    macrodominio: str
    nivel_risco: str = Field(description="Crítico, Vulnerável, Moderado, Saudável ou Protetivo")
    texto_diagnostico: str = Field(
        description="Texto do diagnóstico com citações inline [RELATO-XXX]"
    )
    citacoes: list[Citacao] = Field(description="Fontes utilizadas no diagnóstico")
    evidencia_suficiente: bool = Field(
        description="False se não há relatos suficientes para concluir"
    )
```

---

## Etapa 4 — Log de Auditoria

Todo diagnóstico gerado é registrado em uma tabela **append-only** (sem permissão de UPDATE ou DELETE), garantindo que o histórico não pode ser adulterado:

```sql
CREATE TABLE audit_log_insights (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id        UUID NOT NULL,
    macrodominio      VARCHAR(100) NOT NULL,
    texto_diagnostico TEXT NOT NULL,
    nivel_risco       VARCHAR(20) NOT NULL,
    citacoes          JSONB NOT NULL,
    relatos_usados    JSONB NOT NULL,
    criado_em         TIMESTAMPTZ DEFAULT NOW(),
    modelo_ia         VARCHAR(50) NOT NULL
);

REVOKE UPDATE, DELETE ON audit_log_insights FROM app_user;
```

Isso permite que qualquer insight possa ser auditado depois: qual modelo gerou, quais relatos fundamentaram, em que data.

---

## Experiência do Gestor no Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  🔴 Saúde e Recuperação — CRÍTICO                               │
│                                                                 │
│  "Identificamos risco crítico de violência no ambiente de       │
│   trabalho. Colaboradores relatam ameaças [RELATO-142] e        │
│   agressão verbal [RELATO-87], além de violência física         │
│   presenciada [RELATO-201]."                                    │
│                                                                 │
│  📎 Fontes (clique para expandir)                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  RELATO-142 · 12/03/2025                                   │ │
│  │  "sofro ameaças constantes do meu supervisor direto"       │ │
│  │                                                            │ │
│  │  RELATO-87 · 28/02/2025                                    │ │
│  │  "meu supervisor grita comigo na frente de todos"          │ │
│  │                                                            │ │
│  │  RELATO-201 · 15/03/2025                                   │ │
│  │  "já presenciei colega ser empurrado pelo gerente"         │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

O gestor clica em qualquer `[RELATO-XXX]` e vê o trecho original que fundamenta aquela parte do diagnóstico.

---

## Camadas Anti-Alucinação

| Camada                     | Mecanismo                                                              |
|----------------------------|------------------------------------------------------------------------|
| **Prompt restritivo**      | Instrução "use APENAS os relatos abaixo" impede a IA de inventar dados |
| **Structured Output**      | Schema Pydantic obriga o campo `citacoes` em toda resposta             |
| **Validação pós-geração**  | Código verifica se cada `[RELATO-XXX]` citado realmente existe no banco|
| **Audit log imutável**     | Registro append-only preserva diagnóstico, fontes e modelo utilizados  |
