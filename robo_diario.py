import requests
import pandas as pd
import time
from datetime import datetime
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURAÇÃO ---
# Nome EXATO da planilha que criaste no Google
NOME_PLANILHA_GOOGLE = "Base_Licitacoes_RN" 
NOME_ABA = "Dados"

# Configurações do Portal Nacional (PNCP)
BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
ESTADO = "RN"
DATA_INICIO = "20260101" # Ajuste conforme necessário
DATA_FIM = datetime.now().strftime("%Y%m%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

# --- CÉREBRO DE CLASSIFICAÇÃO 3.0 (Versão Especialista) ---
def definir_area(objeto):
    texto = str(objeto).lower()
    
    # Inicializa pontuação zerada para todas as categorias estratégicas
    scores = {
        # GRUPO 1: ENGENHARIA E INFRAESTRUTURA
        'Infraestrutura Urbana (Pavimentação/Drenagem)': 0,
        'Edificações (Construção e Reformas)': 0,
        'Serviços de Engenharia (Projetos/Fiscalização)': 0,
        'Materiais de Construção': 0,
        'Iluminação Pública': 0,

        # GRUPO 2: SAÚDE
        'Saúde - Medicamentos': 0,
        'Saúde - Equipamentos Hospitalares': 0,
        'Saúde - Serviços Médicos e Exames': 0,

        # GRUPO 3: EDUCAÇÃO
        'Educação - Transporte Escolar': 0,
        'Educação - Merenda e Alimentos': 0,
        'Educação - Material Didático e Uniformes': 0,

        # GRUPO 4: FACILITIES E SERVIÇOS GERAIS
        'Limpeza Urbana (Lixo e Varrição)': 0,
        'Limpeza Predial e Conservação': 0,
        'Vigilância e Segurança Patrimonial': 0,
        'Locação de Mão de Obra (Terceirização)': 0,

        # GRUPO 5: FROTA E LOGÍSTICA
        'Frota - Combustíveis': 0,
        'Frota - Aquisição de Veículos': 0,
        'Frota - Manutenção e Peças': 0,
        'Locação de Veículos e Máquinas': 0,

        # GRUPO 6: TECNOLOGIA E ESCRITÓRIO
        'TI - Equipamentos (Hardware)': 0,
        'TI - Software e Licenças': 0,
        'Material de Expediente e Mobiliário': 0,

        # GRUPO 7: ADMINISTRATIVO E OUTROS
        'Eventos, Palco e Festividades': 0,
        'Serviços Funerários': 0,
        'Publicidade e Comunicação': 0,
        'Consultoria e Assessoria Jurídica': 0,
        'Outros': 0.1 # Pontuação mínima para servir de padrão
    }

    # --- REGRAS DE PONTUAÇÃO (Algoritmo de Decisão) ---

    # 1. INFRAESTRUTURA E OBRAS
    if any(x in texto for x in ['pavimentacao', 'asfaltica', 'drenagem', 'terraplanagem', 'saneamento', 'calcamento', 'paralelepipedo', 'ponte', 'viaduto', 'urbanizacao', 'operacao tapa buraco']):
        scores['Infraestrutura Urbana (Pavimentação/Drenagem)'] += 20
    
    if any(x in texto for x in ['construcao de', 'edificacao', 'reforma de escola', 'ampliacao', 'conclusao de obra', 'ubs', 'creche', 'quadra', 'cobertura de', 'muro']):
        scores['Edificações (Construção e Reformas)'] += 15
        
    if any(x in texto for x in ['elaboracao de projeto', 'fiscalizacao de obra', 'servico de engenharia', 'topografia', 'georreferenciamento', 'laudo tecnico']):
        scores['Serviços de Engenharia (Projetos/Fiscalização)'] += 15

    if any(x in texto for x in ['iluminacao publica', 'lampada led', 'luminaria', 'poste', 'material eletrico', 'manutencao eletrica']):
        scores['Iluminação Pública'] += 10

    if any(x in texto for x in ['cimento', 'tijolo', 'areia', 'brita', 'argamassa', 'ferragens', 'madeira', 'telha', 'material de construcao', 'hidraulico']):
        scores['Materiais de Construção'] += 10

    # 2. LIMPEZA E RESÍDUOS
    if any(x in texto for x in ['coleta de lixo', 'residuos solidos', 'aterro sanitario', 'transbordo', 'entulho', 'podas', 'capina urbana']):
        scores['Limpeza Urbana (Lixo e Varrição)'] += 20
    
    if any(x in texto for x in ['servico de limpeza', 'higienizacao', 'material de limpeza', 'copeira', 'zeladoria', 'dedetizacao', 'limpeza de caixa d', 'higiene']):
        scores['Limpeza Predial e Conservação'] += 10

    # 3. SEGURANÇA E TERCEIRIZAÇÃO
    if any(x in texto for x in ['vigilancia', 'seguranca desarmada', 'monitoramento', 'cameras', 'cftv', 'guarda municipal', 'alarme']):
        scores['Vigilância e Segurança Patrimonial'] += 15
    
    if any(x in texto for x in ['locacao de mao de obra', 'recepcionista', 'porteiro', 'apoio administrativo', 'motorista', 'terceirizacao']):
        scores['Locação de Mão de Obra (Terceirização)'] += 10

    # 4. SAÚDE
    if any(x in texto for x in ['medicamento', 'farmacia', 'farmacologico', 'insumo hospitalar', 'material medico', 'penso']):
        scores['Saúde - Medicamentos'] += 10
    if any(x in texto for x in ['equipamento hospitalar', 'raio-x', 'odontologico', 'cadeira de rodas', 'maca']):
        scores['Saúde - Equipamentos Hospitalares'] += 10
    if any(x in texto for x in ['plantao medico', 'servico medico', 'exames', 'laboratorial', 'ultrassonografia', 'enfermagem', 'consultas']):
        scores['Saúde - Serviços Médicos e Exames'] += 10

    # 5. EDUCAÇÃO
    if any(x in texto for x in ['transporte escolar', 'transporte de alunos', 'transporte universitario']):
        scores['Educação - Transporte Escolar'] += 20 
    
    if any(x in texto for x in ['merenda', 'alimentacao escolar', 'nutricional', 'generos alimenticios', 'hortifruti']):
        scores['Educação - Merenda e Alimentos'] += 10
    
    if any(x in texto for x in ['material didatico', 'kit escolar', 'fardamento', 'uniforme', 'mochila', 'livro']):
        scores['Educação - Material Didático e Uniformes'] += 10

    # 6. FROTA
    if any(x in texto for x in ['combustivel', 'gasolina', 'diesel', 'etanol', 'abastecimento']):
        scores['Frota - Combustíveis'] += 15
    if any(x in texto for x in ['aquisicao de veiculo', 'ambulancia', 'caminhao', 'onibus', 'motocicleta']):
        scores['Frota - Aquisição de Veículos'] += 10
    if any(x in texto for x in ['pecas', 'pneus', 'lubrificante', 'manutencao veicular', 'oficina mecanica']):
        scores['Frota - Manutenção e Peças'] += 10
    if any(x in texto for x in ['locacao de veiculo', 'locacao de caminhao', 'maquinas pesadas', 'trator', 'retroescavadeira', 'motoniveladora']):
        scores['Locação de Veículos e Máquinas'] += 10

    # 7. TI e ESCRITÓRIO
    if any(x in texto for x in ['computador', 'notebook', 'servidor', 'nobreak', 'tablet']):
        scores['TI - Equipamentos (Hardware)'] += 10
    if any(x in texto for x in ['software', 'licenca', 'sistema', 'site', 'hospedagem', 'internet']):
        scores['TI - Software e Licenças'] += 10
    if any(x in texto for x in ['papel a4', 'expediente', 'caneta', 'toner', 'cartucho', 'mesa', 'cadeira', 'arquivo', 'mobiliario']):
        scores['Material de Expediente e Mobiliário'] += 10

    # 8. OUTROS ESPECÍFICOS
    if any(x in texto for x in ['show', 'palco', 'som', 'iluminacao', 'festividade', 'banda', 'evento']):
        scores['Eventos, Palco e Festividades'] += 10
    if any(x in texto for x in ['urna', 'ataude', 'translado', 'funerario']):
        scores['Serviços Funerários'] += 15
    if any(x in texto for x in ['publicidade', 'propaganda', 'divulgacao', 'diario oficial', 'radio', 'midia']):
        scores['Publicidade e Comunicação'] += 15
    if any(x in texto for x in ['consultoria', 'assessoria', 'juridica', 'contabil', 'treinamento']):
        scores['Consultoria e Assessoria Jurídica'] += 10

    # DESEMPATE MATEMÁTICO
    vencedor = max(scores, key=scores.get)
    if scores[vencedor] < 1:
        return 'Outros'
    else:
        return vencedor

# --- CONEXÃO GOOGLE SHEETS ---
def conectar_google():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # O arquivo credentials.json é criado pelo GitHub Actions
    return ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)

# --- ROBÔ ---
def executar_robo():
    print("🤖 Iniciando Robô Setor Estratégico (V3.0)...")
    novos_dados = []
    
    # IDs de modalidade PNCP: 6=Pregão, 5=Concorrência, 8=Dispensa
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
                if not itens: break # Fim das páginas
                
                for item in itens:
                    # Classificação Inteligente
                    area = definir_area(item.get('objetoCompra', ''))
                    
                    # Tratamento de Valores
                    val = item.get('valorTotalEstimado', 0)
                    try:
                        valor_final = float(val)
                    except:
                        valor_final = 0.0
                    
                    link = item.get('linkSistemaOrigem', 'N/A')
                    
                    novos_dados.append({
                        "ID_Unico": str(link),
                        "Data": item.get('dataPublicacaoPncp', '')[:10],
                        "Modalidade": nome,
                        "Cidade": item.get('unidadeOrgao', {}).get('municipioNome', 'N/A'),
                        "Órgão": item.get('orgaoEntidade', {}).get('razaoSocial', 'N/A'),
                        "Area": area,
                        "Objeto": item.get('objetoCompra', 'Sem descrição'),
                        "Valor": valor_final,
                        "Link": link
                    })
                
                pagina += 1
            except Exception as e:
                print(f"⚠️ Erro na página {pagina}: {e}")
                break

    df_novo = pd.DataFrame(novos_dados)
    
    if df_novo.empty:
        print("💤 Nenhum dado novo encontrado nesta execução.")
        return

    # Salva no Google Sheets
    print("☁️ Conectando ao Google Sheets...")
    try:
        creds = conectar_google()
        client = gspread.authorize(creds)
        sheet = client.open(NOME_PLANILHA_GOOGLE).worksheet(NOME_ABA)
        
        # 1. Recupera base antiga
        dados_antigos = sheet.get_all_records()
        df_antigo = pd.DataFrame(dados_antigos)
        
        # 2. Consolidação (Anti-Duplicidade)
        if not df_antigo.empty:
            df_novo['ID_Unico'] = df_novo['ID_Unico'].astype(str)
            df_antigo['ID_Unico'] = df_antigo['ID_Unico'].astype(str)
            
            df_total = pd.concat([df_antigo, df_novo])
            df_total = df_total.drop_duplicates(subset=['ID_Unico'], keep='last')
        else:
            df_total = df_novo

        # 3. Upload Seguro
        print(f"💾 Salvando {len(df_total)} registros na nuvem...")
        sheet.clear()
        
        # Método compatível com gspread atualizado
        sheet.update(
            range_name='A1', 
            values=[df_total.columns.values.tolist()] + df_total.values.tolist()
        )
        
        print(f"✅ SUCESSO! Base atualizada e categorizada.")
        
    except Exception as e:
        print(f"❌ Erro Crítico ao salvar no Google: {e}")

if __name__ == "__main__":
    executar_robo()
