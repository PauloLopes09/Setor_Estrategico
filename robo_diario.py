import requests
import pandas as pd
from datetime import datetime
import os
import numpy as np
import csv 

# --- CONFIGURAÇÃO ---
PASTA_DADOS = "data"
NOME_ARQUIVO = "licitacoes_rn.csv"
CAMINHO_COMPLETO = os.path.join(PASTA_DADOS, NOME_ARQUIVO)

# Portal Nacional (PNCP)
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
    except: return 0.0

def limpar_texto_absoluto(texto):
    if texto is None: return ""
    txt = str(texto)
    txt = txt.replace('\n', ' ').replace('\r', ' ')
    txt = txt.replace(';', ',') 
    txt = txt.replace('"', '').replace("'", "")
    txt = txt.replace('\t', ' ')
    return " ".join(txt.split())

# --- CLASSIFICAÇÃO AUDITOR ---
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
    print("🤖 Iniciando Robô GitHub (Modo Auditoria: Nunca Excluir)...")
    
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
                resp = requests.get(url, headers=HEADERS, timeout=15)
                
                if resp.status_code != 200: break
                
                itens = resp.json().get('data', [])
                if not itens: break 
                
                for item in itens:
                    try:
                        nat, func = classificar_auditor(item.get('objetoCompra', ''))
                        valor_limpo = limpar_dinheiro(item.get('valorTotalEstimado', 0))
                        
                        link = item.get('linkSistemaOrigem', 'N/A')
                        data_bruta = item.get('dataPublicacaoPncp', None)
                        
                        novos_dados.append({
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
                    except: continue

                pagina += 1
            except: break

    df_novo = pd.DataFrame(novos_dados)
    
    if df_novo.empty: 
        print("💤 Nenhum dado novo encontrado.")
        # Mesmo se não achar nada novo, não faz nada com o arquivo velho.
        return

    print("💾 Processando arquivo CSV...")

    df_total = df_novo
    
    # Carrega base antiga
    if os.path.exists(CAMINHO_COMPLETO):
        try:
            df_antigo = pd.read_csv(CAMINHO_COMPLETO, sep=';', encoding='utf-8-sig', on_bad_lines='skip', engine='python')
            
            # Remove a coluna de auditoria antiga para recalcular (opcional, mas mantém limpo)
            if 'Status_Duplicidade' in df_antigo.columns:
                df_antigo = df_antigo.drop(columns=['Status_Duplicidade'])
                
            df_total = pd.concat([df_antigo, df_novo])
        except:
            df_total = df_novo

    # --- TRATAMENTO FINAL ---
    df_total = df_total.fillna('')
    df_total = df_total.replace([np.inf, -np.inf], 0)
    
    # Tratamento Data
    df_total['Data_Temp'] = pd.to_datetime(df_total['Data'], errors='coerce')
    df_total['Data'] = df_total['Data_Temp'].dt.strftime('%Y-%m-%d').fillna('')
    df_total['Data'] = df_total['Data'].replace(['nan', 'NaT', 'None'], '')
    
    # Ordena por Data para que os mais antigos fiquem primeiro
    df_total = df_total.sort_values(by=['Data_Temp'], ascending=True)
    df_total = df_total.drop(columns=['Data_Temp'])

    # --- MECANISMO DE AVISO DE DUPLICIDADE (SEM EXCLUIR) ---
    # Critério: Se Link, Objeto, Valor e Órgão forem iguais, é repetido.
    # keep='first' -> O primeiro que aparece é False (não duplicado), os próximos são True (duplicados)
    duplicatas = df_total.duplicated(subset=['Link', 'Objeto', 'Valor', 'Órgão'], keep='first')
    
    # Cria a coluna de Aviso
    df_total['Status_Duplicidade'] = np.where(duplicatas, 'REPETIDO', 'ORIGINAL')

    # Conta para o log
    qtd_repetidos = len(df_total[df_total['Status_Duplicidade'] == 'REPETIDO'])
    
    df_total.to_csv(CAMINHO_COMPLETO, index=False, sep=';', encoding='utf-8-sig', quoting=csv.QUOTE_NONE, escapechar='\\')
    
    print(f"✅ Arquivo salvo! Total: {len(df_total)} linhas.")
    print(f"⚠️ Atenção: {qtd_repetidos} registros foram marcados como REPETIDO (mas mantidos no arquivo).")

if __name__ == "__main__":
    executar_robo()
