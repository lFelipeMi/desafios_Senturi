Desafio 1: Lógica de Risco e o "Ponto Cego" Estatístico
Cenário: Em nosso sistema, perguntas têm valores de 0, 25, 50, 75 ou 100. Perguntas Invertidas são calculadas como (100 - Valor). No dashboard, a nota do macrodomínio obedece a seguinte escala: 0-39 (Crítico), 40-54 (Vulnerável), 55-69 (Moderado), 70-84 (Saudável) e 85-100 (Protetivo).

O Problema: No macrodomínio Saúde e Recuperação, a pergunta P35 (Violência no trabalho) é invertida. Se o colaborador responde "Sempre" (100), a nota da P35 fica 0 (Risco Crítico). Porém, se ele tirar 100 nas outras 4 perguntas do domínio, a média simples será 80. No dashboard, 80 é classificado como "Saudável". Ou seja, um evento de violência foi mascarado pela média.

Solução: Se uma resposta individual for 0, como o resultado final do domínio deve ter um teto de 39 pois ali existe um relado "realmente Crítico" que não deve ser diluido.

---

```python
def calcular_nota_macrodominio(respostas, invertidas=None):
    """
    Calcula a nota de um domínio, impedindo a diluição de riscos críticos.
    
    :param respostas: Lista com os valores respondidos (0, 25, 50, 75, 100)
    :param invertidas: Lista de booleanos [True, False, ...] indicando perguntas invertidas
    :return: Tupla com a (Nota Final, Classificação)
    """
    if invertidas is None:
        invertidas = [False] * len(respostas)
        
    notas_processadas = []
    
    # 1. Processa a inversão das notas (ex: 100 vira 0)
    for valor_resposta, eh_invertida in zip(respostas, invertidas):
        if eh_invertida:
            notas_processadas.append(100 - valor_resposta)
        else:
            notas_processadas.append(valor_resposta)
            
    # 2. Calcula a média aritmética simples inicial
    media_simples = sum(notas_processadas) / len(notas_processadas)
    nota_final = media_simples
    
    # 3. LÓGICA ANTI-DILUIÇÃO (O Ponto Cego)
    # Se existe algum "0" nas notas processadas, a nota do domínio
    # sofre um teto, não podendo passar de 39 (limite do Crítico)
    # e evitando diluição dos riscos críticos pela média.
    # Dessa forma o gestor consegue ter uma visão mais clara dos riscos.
    if 0 in notas_processadas:
        nota_final = min(media_simples, 39)
        
    if nota_final <= 39:
        classificacao = "Crítico"
    elif nota_final <= 54:
        classificacao = "Vulnerável"
    elif nota_final <= 69:
        classificacao = "Moderado"
    elif nota_final <= 84:
        classificacao = "Saudável"
    else:
        classificacao = "Protetivo"
        
    return nota_final, classificacao
```