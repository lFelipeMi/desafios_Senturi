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
    
    for valor_resposta, eh_invertida in zip(respostas, invertidas):
        if eh_invertida:
            notas_processadas.append(100 - valor_resposta)
        else:
            notas_processadas.append(valor_resposta)
            
    media_simples = sum(notas_processadas) / len(notas_processadas)
    nota_final = media_simples
    
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

respostas_colaborador = [100, 100, 100, 100, 100]

mapa_perguntas_invertidas = [False, False, False, False, True]

nota, status = calcular_nota_macrodominio(respostas_colaborador, mapa_perguntas_invertidas)

print(f"Resultado Final do Domínio: {nota}")
print(f"Status no Dashboard: {status}")
