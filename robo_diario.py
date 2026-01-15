import requests
import pandas as pd
import time
from datetime import datetime
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURAÇÃO ---
# Nome da planilha que criaste no Google
NOME_PLANILHA_GOOGLE = "Base_Licitacoes_RN" 
NOME_ABA = "Dados"

BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
ESTADO = "RN"
DATA_INICIO = "20260101"
DATA_FIM = datetime.now().strftime("%Y%m%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

# --- CÉREBRO DE CLASSIFICAÇÃO ---
def definir_area(objeto):
    texto = str(objeto).lower()
    scores = {'Saúde': 0, 'Tecnologia (TI)': 0, 'Obras e Engenharia': 0, 'Educação': 0, 'Veículos e Frota': 0, 'Limpeza e Zeladoria': 0, 'Alimentação': 0, 'Eventos': 0, 'Serviços Funerários': 0, 'Outros': 0.1}

    if any(x in texto for x in ['coleta de lixo', 'residuos solidos', 'dedetizacao', 'cacamba', 'entulho', 'podas']): scores['Limpeza e Zeladoria'] += 15 
    if any(x in texto for x in ['limpeza', 'higienizacao', 'conservacao', 'capina']): scores['Limpeza e Zeladoria'] += 6
    
    if any(x in texto for x in ['automovel', 'onibus', 'ambulancia', 'trator', 'retroescavadeira', 'caminhao']): scores['Veículos e Frota'] += 15
    if any(x in texto for x in ['veiculo', 'pneu', 'combustivel', 'pecas', 'frete']): scores['Veículos e Frota'] += 6
    if 'locacao' in texto: scores['Veículos e Frota'] += 1 

    if any(x in texto for x in ['pavimentacao', 'drenagem', 'terraplanagem', 'edificacao']): scores['Obras e Engenharia'] += 10
    if any(x in texto for x in ['reforma', 'construcao', 'muro', 'engenharia', 'material de construcao']): scores['Obras e Engenharia'] += 5
    if 'obra' in texto: scores['Obras e Engenharia'] += 2 

    if any(x in texto for x in ['medicamento', 'hospital', 'odontologico', 'enfermagem', 'caps', 'raio-x']): scores['Saúde'] += 10
    if any(x in texto for x in ['saude', 'medico', 'exame', 'ubs']): scores['Saúde'] += 5

    if any(x in texto for x in ['notebook', 'software', 'impressora', 'toner', 'cartucho']): scores['Tecnologia (TI)'] += 10
    if any(x in texto for x in ['computador', 'informatica', 'internet', 'sistema']): scores['Tecnologia (TI)'] += 5

    if any(x in texto for x in ['material didatico', 'merenda', 'transporte escolar']): scores['Educação'] += 10
    if any(x in texto for x in ['escola', 'aluno', 'professor', 'educacao']): scores['Educação'] += 5

    if any(x in texto for x in ['generos alimenticios', 'refeicao', 'agua mineral', 'coffee break']): scores['Alimentação'] += 10
    if any(x in texto for x in ['palco', 'som e iluminacao', 'show', 'festividade']): scores['Eventos'] += 10
    if any(x in texto for x in ['urna funeraria', 'ataude', 'translado de corpo']): scores['Serviços Funerários'] += 15

    vencedor = max(scores, key=scores.get)
    return 'Outros' if scores[vencedor] < 1 else vencedor

# --- CONEXÃO GOOGLE SHEETS ---
def conectar_google():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # O GitHub vai criar este arquivo automaticamente a partir do Secret
    return ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

# --- ROBÔ ---
def executar_robo():
    print("🤖 Iniciando Robô na Nuvem...")
    novos_dados = []
    
    # Busca dados no PNCP
    modalidades = {"6": "Pregão", "5": "Concorrência", "8": "Dispensa"}
    for cod, nome in modalidades.items():
        print(f"   > Buscando {nome}...")
        pagina = 1
        while True:
            try:
                url = f"{BASE_URL}?dataInicial={DATA_INICIO}&dataFinal={DATA_FIM}&codigoModalidadeContratacao={cod}&uf={ESTADO}&pagina={pagina}"
                resp = requests.get(url, headers=HEADERS, timeout=10)
                if resp.status_code != 200: break
                
                lista = resp.json().get('data', [])
                if not lista: break
                
                for item in lista:
                    link = item.get('linkSistemaOrigem', 'N/A')
                    area = definir_area(item.get('objetoCompra', ''))
                    
                    # Formata Valor para Padrão Americano (Float) para o Google Sheets entender
                    valor = item.get('valorTotalEstimado', 0)
                    
                    novos_dados.append({
                        "ID_Unico": link,
                        "Data": item.get('dataPublicacaoPncp', '')[:10],
                        "Modalidade": nome,
                        "Cidade": item.get('unidadeOrgao', {}).get('municipioNome', 'N/A'),
                        "Órgão": item.get('orgaoEntidade', {}).get('razaoSocial', 'N/A'),
                        "Area": area,
                        "Objeto": item.get('objetoCompra', 'Sem descrição'),
                        "Valor": valor,
                        "Link": link
                    })
                pagina += 1
            except: break

    df_novo = pd.DataFrame(novos_dados)
    if df_novo.empty:
        print("Nenhum dado encontrado.")
        return

    # Salva no Google Sheets
    print("☁️ Conectando ao Google Sheets...")
    creds = conectar_google()
    client = gspread.authorize(creds)
    sheet = client.open(NOME_PLANILHA_GOOGLE).worksheet(NOME_ABA)
    
    # Lógica de Atualização (Baixa o antigo, junta com o novo, remove duplicatas)
    dados_antigos = sheet.get_all_records()
    df_antigo = pd.DataFrame(dados_antigos)
    
    if not df_antigo.empty:
        # Garante que as colunas chaves sejam strings para comparação
        df_novo['ID_Unico'] = df_novo['ID_Unico'].astype(str)
        df_antigo['ID_Unico'] = df_antigo['ID_Unico'].astype(str)
        
        df_total = pd.concat([df_antigo, df_novo])
        df_total = df_total.drop_duplicates(subset=['ID_Unico'], keep='last')
    else:
        df_total = df_novo

    # Limpa e Reescreve
    sheet.clear()
    sheet.update([df_total.columns.values.tolist()] + df_total.values.tolist())
    print(f"✅ SUCESSO! {len(df_total)} licitações na nuvem.")

if __name__ == "__main__":
    executar_robo()
