import requests
import pandas as pd
from datetime import datetime, timedelta
import os
import numpy as np
import csv 

# --- CONFIGURAÇÃO ---
PASTA_DADOS = "data"

# ARQUIVOS
NOME_ARQUIVO_COMPLETO = "licitacoes_rn_COMPLETO.csv"
CAMINHO_COMPLETO = os.path.join(PASTA_DADOS, NOME_ARQUIVO_COMPLETO)

NOME_ARQUIVO_VISUAL = "licitacoes_rn_VISUALIZACAO.csv"
CAMINHO_VISUAL = os.path.join(PASTA_DADOS, NOME_ARQUIVO_VISUAL)

# Configurações do Portal Nacional (PNCP)
BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
ESTADO = "RN"
DATA_INICIO = "20260101"
DATA_FIM = datetime.now().strftime("%Y%m%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

# --- FUNÇÕES DE LIMPEZA ---
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

def limpar_texto_absoluto(texto):
    """
    Limpa o texto, mas mantém compatibilidade com CSV padrão
    """
    if texto is None: return ""
    txt = str(texto)
    # Remove apenas quebras de linha que destroem o CSV
    txt = txt.replace('\n', ' ').replace('\r', ' ')
    # Remove tabs
    txt = txt.replace('\t', ' ')
    # Remove espaços duplos
    return " ".join(txt.split())

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
    print("🤖 Iniciando Robô GitHub (Modo CSV Padrão Seguro)...")
    
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
                    nat, func = classificar_auditor(item.get('objetoCompra', ''))
                    valor_limpo = limpar_dinheiro(item.get('valorTotalEstimado', 0))
                    link = item.get('linkSistemaOrigem', 'N/A')
                    data_bruta = item.get('dataPublicacaoPncp', None)
                    
                    novos_dados.append({
                        "ID_Unico": str(link),
                        "Data": data_bruta, 
                        "Modalidade": limpar_texto_absoluto(nome),
                        "Cidade": limpar_texto_absoluto(item.get('unidadeOrgao', {}).get('municipioNome', 'N/A')),
                        "Órgão": limpar_texto_absoluto(item.get('orgaoEntidade', {}).get('razaoSocial', 'N/A')),
                        "Natureza": nat,
                        "Função": func,
                        "Categoria_Final": f"{nat} - {func}",
                        "Objeto": limpar_texto_absoluto(item.get('objetoCompra', 'Sem descrição')),
                        "Valor": valor_limpo,
                        "Link": link
                    })
                pagina += 1
            except: break
    
    # --- CORREÇÃO DO ERRO AQUI EMBAIXO ---
    df_novo = pd.DataFrame(novos_dados)
    
    if df_novo.empty: 
        print("💤 Nenhum dado novo.")
        return

    print("💾 Processando Base Completa...")

    # --- 1. GERA O ARQUIVO COMPLETO ---
    df_total = df_novo
    if os.path.exists(CAMINHO_COMPLETO):
        try:
            # Tenta ler com configurações flexíveis
            df_antigo = pd.read_csv(CAMINHO_COMPLETO, sep=';', encoding='utf-8-sig', on_bad_lines='skip', engine='python')
            df_antigo['ID_Unico'] = df_antigo['ID_Unico'].astype(str)
            df_novo['ID_Unico'] = df_novo['ID_Unico'].astype(str)
            df_total = pd.concat([df_antigo, df_novo])
            df_total = df_total.drop_duplicates(subset=['ID_Unico'], keep='last')
        except:
            df_total = df_novo

    # Limpeza Final e Datas
    df_total = df_total.fillna('')
    df_total = df_total.replace([np.inf, -np.inf], 0)
    df_total['Data_Temp'] = pd.to_datetime(df_total['Data'], errors='coerce')
    df_total['Data'] = df_total['Data_Temp'].dt.strftime('%Y-%m-%d').fillna('')
    df_total['Data'] = df_total['Data'].replace(['nan', 'NaT', 'None'], '')
    
    # SALVA O COMPLETO (Com Quoting Padrão)
    df_total.drop(columns=['Data_Temp'], inplace=True, errors='ignore')
    df_total.to_csv(CAMINHO_COMPLETO, index=False, sep=';', encoding='utf-8-sig', quoting=csv.QUOTE_MINIMAL)
    print(f"✅ Histórico Completo Atualizado: {len(df_total)} linhas.")

    # --- 2. GERA O ARQUIVO VISUAL ---
    print("💎 Gerando arquivo Visual...")
    
    df_visual = df_total.copy()
    df_visual['Data_Filtro'] = pd.to_datetime(df_visual['Data'], errors='coerce')
    data_corte = datetime.now() - timedelta(days=30)
    df_visual = df_visual[df_visual['Data_Filtro'] >= data_corte]
    df_visual = df_visual.drop(columns=['Data_Filtro'])
    
    if len(df_visual) > 2000:
        df_visual = df_visual.tail(2000)

    # SALVA O VISUAL (Com Quoting Padrão)
    df_visual.to_csv(CAMINHO_VISUAL, index=False, sep=';', encoding='utf-8-sig', quoting=csv.QUOTE_MINIMAL)
    print(f"✅ Arquivo Visual Atualizado: {len(df_visual)} linhas.")

if __name__ == "__main__":
    executar_robo()
