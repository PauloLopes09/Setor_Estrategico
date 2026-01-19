import requests
import pandas as pd
from datetime import datetime
import os
import numpy as np
import csv # Importante para configurações avançadas de CSV

# --- CONFIGURAÇÃO ---
PASTA_DADOS = "data"
NOME_ARQUIVO = "licitacoes_rn.csv"
CAMINHO_COMPLETO = os.path.join(PASTA_DADOS, NOME_ARQUIVO)

# Configurações do Portal Nacional (PNCP)
BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
ESTADO = "RN"
DATA_INICIO = "20260101"
DATA_FIM = datetime.now().strftime("%Y%m%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

# --- FUNÇÃO DE LIMPEZA FINANCEIRA ---
def limpar_dinheiro(valor_bruto):
    if valor_bruto is None: return 0.0
    if isinstance(valor_bruto, (int, float)): return float(valor_bruto)
    texto = str(valor_bruto).strip()
    if texto == "": return 0.0
    try:
        texto = texto.replace('R$', '').replace('$', '').strip()
        if ',' in texto:
            texto = texto.replace('.', '').replace(',', '.')
        return float(texto)
    except:
        return 0.0

# --- NOVA FUNÇÃO: VASSOURA DE TEXTO (CORRIGE O ILLEGAL QUOTING) ---
def limpar_texto_csv(texto):
    """
    Remove caracteres que quebram o CSV: ; " e quebras de linha
    """
    if texto is None: return ""
    txt = str(texto).strip()
    
    # 1. Remove quebras de linha (enter)
    txt = txt.replace('\n', ' ').replace('\r', '')
    
    # 2. Troca ponto e vírgula por vírgula (pois usamos ; como separador)
    txt = txt.replace(';', ',')
    
    # 3. Troca aspas duplas por simples (evita erro de quoting)
    txt = txt.replace('"', "'")
    
    return txt

# --- CÉREBRO: CLASSIFICAÇÃO AUDITOR ---
def classificar_auditor(objeto):
    texto = str(objeto).lower()
    natureza = "AQUISIÇÃO" 
    
    if any(x in texto for x in ['contratacao', 'prestacao', 'servico', 'manutencao', 'reparo', 'limpeza', 'locacao de mao', 'apoio', 'assessoria', 'consultoria', 'publicidade', 'gestao']):
        natureza = "SERVIÇOS"
    elif any(x in texto for x in ['obra', 'pavimentacao', 'construcao', 'reforma', 'ampliacao', 'drenagem', 'engenharia', 'edificacao', 'muro', 'tapa buraco']):
        natureza = "OBRAS"
    elif any(x in texto for x in ['locacao', 'aluguel', 'arrendamento']):
        if 'mao de obra' in texto or 'motorista' in texto: natureza = "SERVIÇOS"
        else: natureza = "LOCAÇÃO"

    scores = {
        'INFRAESTRUTURA URBANA': 0, 'EDIFICAÇÕES PÚBLICAS': 0, 'MATERIAIS DE CONSTRUÇÃO': 0,
        'LIMPEZA URBANA': 0, 'LIMPEZA E CONSERVAÇÃO PREDIAL': 0,
        'SAÚDE - MEDICAMENTOS': 0, 'SAÚDE - SERVIÇOS/EQUIP': 0,
        'EDUCAÇÃO - TRANSPORTE': 0, 'EDUCAÇÃO - GERAL': 0,
        'TI E TECNOLOGIA': 0, 'FROTA E COMBUSTÍVEL': 0, 'LOCAÇÃO DE VEÍCULOS/MÁQUINAS': 0,
        'SEGURANÇA E VIGILÂNCIA': 0, 'AGRICULTURA E MEIO AMBIENTE': 0,
        'ADMINISTRATIVO E EXPEDIENTE': 0, 'EVENTOS E CULTURA': 0,
        'OUTROS': 0.1
    }

    # (Lógica de pontuação mantida)
    if any(x in texto for x in ['pavimentacao', 'asfalto', 'drenagem']): scores['INFRAESTRUTURA URBANA'] += 20
    if any(x in texto for x in ['construcao', 'reforma', 'predio']): scores['EDIFICAÇÕES PÚBLICAS'] += 15
    if any(x in texto for x in ['medicamento', 'farmacia']): scores['SAÚDE - MEDICAMENTOS'] += 15
    if any(x in texto for x in ['transporte escolar']): scores['EDUCAÇÃO - TRANSPORTE'] += 20
    if any(x in texto for x in ['computador', 'notebook']): scores['TI E TECNOLOGIA'] += 10
    if any(x in texto for x in ['combustivel', 'diesel']): scores['FROTA E COMBUSTÍVEL'] += 10
    if any(x in texto for x in ['coleta de lixo']): scores['LIMPEZA URBANA'] += 20
    if any(x in texto for x in ['show', 'palco']): scores['EVENTOS E CULTURA'] += 15

    funcao = max(scores, key=scores.get)
    if scores[funcao] < 1: funcao = 'OUTROS'

    if 'caminhao de lixo' in texto: natureza, funcao = "SERVIÇOS", "LIMPEZA URBANA"
    if 'transporte escolar' in texto: natureza, funcao = "SERVIÇOS", "EDUCAÇÃO - TRANSPORTE"
    if 'pavimentacao' in texto: natureza, funcao = "OBRAS", "INFRAESTRUTURA URBANA"

    return natureza, funcao

# --- ROBÔ ---
def executar_robo():
    print("🤖 Iniciando Robô GitHub (Modo Limpeza de Texto)...")
    
    if not os.path.exists(PASTA_DADOS):
        os.makedirs(PASTA_DADOS)

    novos_dados = []
    modalidades = {"6": "Pregão", "5": "Concorrência", "8": "Dispensa"}
    
    for cod, nome in modalidades.items():
        print(f"   > Buscando {nome}...")
        pagina = 1
        while True:
            try:
                url = f"{BASE_URL}?dataInicial={DATA_INICIO}&dataFinal={DATA_FIM}&codigoModalidadeContratacao={cod}&uf={ESTADO}&pagina={pagina}"
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200: break
                itens = resp.json().get('data', [])
                if not itens: break 
                
                for item in itens:
                    # CLASSIFICA
                    nat, func = classificar_auditor(item.get('objetoCompra', ''))
                    valor_limpo = limpar_dinheiro(item.get('valorTotalEstimado', 0))
                    link = item.get('linkSistemaOrigem', 'N/A')
                    data_bruta = item.get('dataPublicacaoPncp', None)
                    
                    # LIMPA OS TEXTOS (AQUI ESTÁ A CORREÇÃO DO ERRO)
                    objeto_limpo = limpar_texto_csv(item.get('objetoCompra', 'Sem descrição'))
                    orgao_limpo = limpar_texto_csv(item.get('orgaoEntidade', {}).get('razaoSocial', 'N/A'))
                    cidade_limpa = limpar_texto_csv(item.get('unidadeOrgao', {}).get('municipioNome', 'N/A'))

                    novos_dados.append({
                        "ID_Unico": str(link),
                        "Data": data_bruta, 
                        "Modalidade": nome,
                        "Cidade": cidade_limpa,
                        "Órgão": orgao_limpo,
                        "Natureza": nat,
                        "Função": func,
                        "Categoria_Final": f"{nat} - {func}",
                        "Objeto": objeto_limpo,
                        "Valor": valor_limpo,
                        "Link": link
                    })
                pagina += 1
            except: break

    df_novo = pd.DataFrame(novos_dados)
    if df_novo.empty: return

    print("💾 Processando arquivo CSV...")
    
    # Carrega arquivo existente
    if os.path.exists(CAMINHO_COMPLETO):
        # engine='python' e on_bad_lines='skip' ajudam a ler arquivos que já estavam corrompidos
        try:
            df_antigo = pd.read_csv(CAMINHO_COMPLETO, sep=';', encoding='utf-8-sig', on_bad_lines='skip', engine='python')
            df_antigo['ID_Unico'] = df_antigo['ID_Unico'].astype(str)
            df_novo['ID_Unico'] = df_novo['ID_Unico'].astype(str)
            df_total = pd.concat([df_antigo, df_novo])
            df_total = df_total.drop_duplicates(subset=['ID_Unico'], keep='last')
        except:
            # Se o arquivo antigo estiver muito quebrado, substitui pelo novo
            df_total = df_novo
    else:
        df_total = df_novo

    # --- LIMPEZA FINAL ---
    df_total = df_total.fillna('')
    df_total = df_total.replace([np.inf, -np.inf], 0)
    
    # Tratamento de Data
    df_total['Data_Temp'] = pd.to_datetime(df_total['Data'], errors='coerce')
    df_total['Data'] = df_total['Data_Temp'].dt.strftime('%Y-%m-%d').fillna('')
    df_total['Data'] = df_total['Data'].replace(['nan', 'NaT', 'None'], '')
    df_total = df_total.drop(columns=['Data_Temp'])

    # SALVA O ARQUIVO "INDESTRUTÍVEL"
    # quoting=csv.QUOTE_MINIMAL garante que o pandas coloque aspas apenas se necessário
    df_total.to_csv(CAMINHO_COMPLETO, index=False, sep=';', encoding='utf-8-sig', quoting=csv.QUOTE_MINIMAL)
    print(f"✅ Arquivo salvo e sanitizado: {len(df_total)} linhas.")

if __name__ == "__main__":
    executar_robo()
