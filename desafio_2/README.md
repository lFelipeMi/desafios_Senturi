Desafio 2: Agente Classificador e Extração JSON (IA)

Cenário: Precisamos que uma IA leia relatos abertos de colaboradores e os vincule a 1 dos nossos 8 Macrodomínios: 1. Exigências do Trabalho; 2. Organização do Trabalho; 3. Autonomia e Controle; 4. Suporte Social e Liderança; 5. Esforço e Recompensa; 6. Interface Trabalho-Vida; 7. Saúde e Recuperação; 8. Potencial Cognitivo e Segurança Psicológica.

---

## O Prompt de Sistema

```python
SYSTEM_PROMPT = """
Você é um especialista em Psicologia Organizacional e Saúde Ocupacional.
Sua função é analisar relatos abertos de colaboradores e classificá-los com
precisão em um dos 8 Macrodomínios de bem-estar no trabalho.

## Os 8 Macrodomínios

1. **Exigências do Trabalho** — Sobrecarga, pressão por metas, ritmo intenso,
   prazos impossíveis, volume excessivo de tarefas.

2. **Organização do Trabalho** — Clareza de funções, processos, fluxos,
   previsibilidade de horários, burocracia, qualidade do planejamento.

3. **Autonomia e Controle** — Liberdade para tomar decisões, participação
   nas escolhas, microgerenciamento, controle sobre o próprio trabalho.

4. **Suporte Social e Liderança** — Relacionamento com gestor e colegas,
   apoio emocional, feedback, reconhecimento interpessoal, conflitos.

5. **Esforço e Recompensa** — Percepção de justiça entre o esforço dedicado
   e a recompensa recebida (salário, promoção, reconhecimento, benefícios).

6. **Interface Trabalho-Vida** — Equilíbrio entre vida pessoal e profissional,
   invasão do trabalho em momentos de descanso, conciliação familiar.

7. **Saúde e Recuperação** — Sintomas físicos ou mentais relacionados ao
   trabalho, fadiga crônica, burnout, tempo de recuperação, violência.

8. **Potencial Cognitivo e Segurança Psicológica** — Aprendizado, crescimento,
   uso de habilidades, medo de julgamento, liberdade para errar e inovar.

## Instruções de Classificação

- Leia o relato completo antes de decidir.
- Escolha o macrodomínio que melhor captura o **tema central** do relato.
- Se o relato tocar em múltiplos domínios, escolha o que tiver maior evidência
  textual (reflita isso no `score_confianca`).
- `transcricao_chave` deve ser um trecho **literal** (cópia exata) do relato,
  nunca uma paráfrase. Máximo 200 caracteres.
- `score_confianca` reflete sua certeza: use valores baixos (< 50) quando o
  relato for ambíguo ou curto demais para uma classificação firme.
- `analise_sentimento` deve refletir o tom emocional **geral** do colaborador,
  não apenas a gravidade do problema descrito.

## Regras Absolutas

- NUNCA invente informações que não estejam no relato.
- NUNCA retorne texto fora do JSON.
- O campo `macrodoinio_sugerido` deve ser EXATAMENTE um dos 8 nomes listados acima.
""".strip()
```

**1. Definição de papel** — O modelo recebe uma persona clara ("especialista em Psicologia Organizacional"), o que melhora a precisão semântica da classificação.

**2. Descrição explícita dos 8 macrodomínios** — Cada domínio tem palavras-chave associadas. Isso guia o modelo a fazer correspondência semântica entre o relato e o domínio correto, sem depender do seu conhecimento implícito sobre nomenclaturas específicas da Senturi.

**3. Instruções de desambiguação** — Relatos reais frequentemente tocam em múltiplos domínios. As instruções ensinam o modelo a escolher o tema *central* e a refletir a incerteza no `score_confianca`.

**4. Regras absolutas** — Uma seção separada com proibições explícitas (não inventar, não parafrasear a transcrição, retornar apenas JSON) serve como "grade de segurança" que os modelos tendem a respeitar fortemente.

---

## Como Garantimos a Estrutura JSON no Banco de Dados

A garantia tem **3 camadas independentes**:

### Camada 1 — Structured Outputs (OpenAI API)
```python
client.beta.chat.completions.parse(
    response_format=ClassificacaoRelato,  # Schema Pydantic
    ...
)
```
A API usa o schema JSON derivado do modelo Pydantic para **restringir o espaço de tokens durante a geração** (constrained decoding). O modelo *literalmente não consegue* gerar um token que quebraria o schema. Isso é diferente do `json_mode` simples, que apenas instrui o modelo por texto.

Resultado: `completion.choices[0].message.parsed` já é um objeto [`ClassificacaoRelato`](#classificacaorelato) validado, não uma string.

### Camada 2 — Validação Pydantic Local
Mesmo que a API retorne um objeto parsed, fazemos uma checagem explícita de `None` (caso o modelo recuse a tarefa por política de conteúdo). O próprio Pydantic valida ranges (`ge=0, le=100` para score) e enums (`Sentimento`).

### Camada 3 — Serialização Segura
```python
dados_para_banco = resultado.model_dump()
```
Usamos `.model_dump()` do Pydantic para serializar, garantindo que apenas os campos definidos no schema sejam enviados ao banco — sem surpresas de campos extras ou tipos errados.

---

## Por que não `json_mode` simples?

|       Abordagem        |               Garante schema?             |     Valida tipos?    | Valida enums? |
|------------------------|-------------------------------------------|----------------------|---------------|
| `json_mode`            |(`response_format={"type": "json_object"}`)| ❌ Apenas JSON válido| ❌ Não        |
| **Structured Outputs** |(`response_format=ClassificacaoRelato`)    | ✅ Schema exato      | ✅ Sim        |

O `json_mode` simples garante apenas que o output é JSON parseável — mas o modelo ainda pode omitir campos, usar tipos errados, ou inventar campos novos. Com Structured Outputs + Pydantic, o schema é uma **verdade contratual** entre o prompt e o banco de dados.

---

## ClassificacaoRelato

```python
class ClassificacaoRelato(BaseModel):
    """Schema obrigatório de saída do agente classificador."""

    macrodoinio_sugerido: str = Field(
        description=(
            "Nome exato de um dos 8 macrodomínios: "
            "'Exigências do Trabalho', 'Organização do Trabalho', "
            "'Autonomia e Controle', 'Suporte Social e Liderança', "
            "'Esforço e Recompensa', 'Interface Trabalho-Vida', "
            "'Saúde e Recuperação' ou 'Potencial Cognitivo e Segurança Psicológica'."
        )
    )
    score_confianca: int = Field(
        ge=0, le=100,
        description="Confiança do modelo na classificação, de 0 a 100."
    )
    analise_sentimento: Sentimento = Field(
        description="Sentimento predominante do relato: Positivo, Neutro ou Negativo."
    )
    transcricao_chave: str = Field(
        description=(
            "Trecho literal do relato que mais justifica a classificação escolhida. "
            "Máximo de 200 caracteres."
        )
    )
```
