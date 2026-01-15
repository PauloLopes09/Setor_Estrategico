import requests
import pandas as pd
from datetime import datetime
import os
import numpy as np

# --- CONFIGURAÇÃO ---
# Caminho onde o arquivo ficará salvo no GitHub
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

# --- CÉREBRO: CLASSIFICAÇÃO AUDITOR (NATUREZA + FUNÇÃO) ---
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

    if any(x in texto for x in ['pavimentacao', 'asfalto', 'drenagem', 'saneamento', 'tapa buraco', 'paralelepipedo', 'urbanizacao']): scores['INFRAESTRUTURA URBANA'] += 20
    if any(x in texto for x in ['construcao', 'reforma', 'ubs', 'creche', 'escola', 'predio', 'muro', 'cobertura']): scores['EDIFICAÇÕES PÚBLICAS'] += 15
    if any(x in texto for x in ['cimento', 'tijolo', 'areia', 'material de construcao', 'eletrico', 'hidraulico']): scores['MATERIAIS DE CONSTRUÇÃO'] += 10
    if any(x in texto for x in ['coleta de lixo', 'residuos', 'entulho', 'varricao', 'aterro', 'bota fora']): scores['LIMPEZA URBANA'] += 20
    if any(x in texto for x in ['limpeza', 'higienizacao', 'zeladoria', 'dedetizacao', 'material de limpeza']): scores['LIMPEZA E CONSERVAÇÃO PREDIAL'] += 10
    if any(x in texto for x in ['medicamento', 'farmacia', 'injetavel', 'soro', 'comprimido']): scores['SAÚDE - MEDICAMENTOS'] += 15
    if any(x in texto for x in ['hospital', 'medico', 'exame', 'saude', 'enfermagem', 'laboratorial', 'raio-x', 'odontologico']): scores['SAÚDE - SERVIÇOS/EQUIP'] += 10
    if any(x in texto for x in ['transporte escolar', 'transporte de alunos', 'transporte universitario']): scores['EDUCAÇÃO - TRANSPORTE'] += 20
    if any(x in texto for x in ['merenda', 'didatico', 'kit escolar', 'fardamento', 'educacao', 'pedagogico']): scores['EDUCAÇÃO - GERAL'] += 10
    if any(x in texto for x in ['computador', 'notebook', 'software', 'toner', 'impressora', 'internet', 'site']): scores['TI E TECNOLOGIA'] += 10
    if any(x in texto for x in ['combustivel', 'gasolina', 'diesel', 'pneu', 'pecas', 'manutencao veicular']): scores['FROTA E COMBUSTÍVEL'] += 10
    if any(x in texto for x in ['locacao de veiculo', 'trator', 'retroescavadeira', 'maquinas pesadas', 'automovel']): scores['LOCAÇÃO DE VEÍCULOS/MÁQUINAS'] += 10
    if any(x in texto for x in ['vigilancia', 'seguranca', 'monitoramento', 'camera', 'cftv']): scores['SEGURANÇA E VIGILÂNCIA'] += 15
    if any(x in texto for x in ['papel', 'expediente', 'cafe', 'agua mineral', 'mobiliario', 'mesa', 'juridico', 'contabil']): scores['ADMINISTRATIVO E EXPEDIENTE'] += 10
    if any(x in texto for x in ['show', 'palco', 'som', 'evento', 'festividade', 'decoracao', 'banda']): scores['EVENTOS E CULTURA'] += 15
    if any(x in texto for x in ['adubo', 'sementes', 'corte de terra', 'agricola']): scores['AGRICULTURA E MEIO AMBIENTE'] += 15

    funcao = max(scores, key=scores.get)
    if scores[funcao] < 1: funcao = 'OUTROS'

    if 'caminhao de lixo' in texto or 'compactador' in texto: natureza, funcao = "SERVIÇOS", "LIMPEZA URBANA"
    if 'transporte escolar' in texto: natureza, funcao = "SERVIÇOS", "EDUCAÇÃO - TRANSPORTE"
    if 'pavimentacao' in texto: natureza, funcao = "OBRAS", "INFRAESTRUTURA URBANA"
    if 'licenca' in texto and 'software' in texto: natureza, funcao = "AQUISIÇÃO", "TI E TECNOLOGIA"
    if funcao == 'FROTA E COMBUSTÍVEL' and 'combustivel' in texto: natureza = "AQUISIÇÃO"

    return natureza, funcao

# --- ROBÔ ---
def executar_robo():
    print("🤖 Iniciando Robô GitHub (CSV Local)...")
    
    # 1. Cria a pasta 'data' se não existir
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
                    
                    novos_dados.append({
                        "ID_Unico": str(link),
                        "Data": item.get('dataPublicacaoPncp', '')[:10],
                        "Modalidade": nome,
                        "Cidade": item.get('unidadeOrgao', {}).get('municipioNome', 'N/A'),
                        "Órgão": item.get('orgaoEntidade', {}).get('razaoSocial', 'N/A'),
                        "Natureza": nat,
                        "Função": func,
                        "Categoria_Final": f"{nat} - {func}",
                        "Objeto": item.get('objetoCompra', 'Sem descrição'),
                        "Valor": valor_limpo,
                        "Link": link
                    })
                pagina += 1
            except: break

    df_novo = pd.DataFrame(novos_dados)
    if df_novo.empty:
        print("💤 Nenhum dado novo.")
        return

    # 2. Lógica de "Banco de Dados" CSV
    print("💾 Processando arquivo CSV...")
    
    if os.path.exists(CAMINHO_COMPLETO):
        # Lê o CSV que já existe no GitHub
        df_antigo = pd.read_csv(CAMINHO_COMPLETO, sep=';', encoding='utf-8-sig')
        df_antigo['ID_Unico'] = df_antigo['ID_Unico'].astype(str)
        df_novo['ID_Unico'] = df_novo['ID_Unico'].astype(str)
        
        # Junta e Remove Duplicatas
        df_total = pd.concat([df_antigo, df_novo])
        df_total = df_total.drop_duplicates(subset=['ID_Unico'], keep='last')
    else:
        df_total = df_novo

    # Limpeza Final
    df_total = df_total.fillna('')
    df_total = df_total.replace([np.inf, -np.inf], 0)

    # 3. Salva o arquivo CSV na pasta data/
    df_total.to_csv(CAMINHO_COMPLETO, index=False, sep=';', encoding='utf-8-sig')
    print(f"✅ Arquivo {NOME_ARQUIVO} atualizado com {len(df_total)} linhas.")

if __name__ == "__main__":
    executar_robo()
