import requests
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np # Importante para tratar os erros numéricos

# --- CONFIGURAÇÃO ---
NOME_PLANILHA_GOOGLE = "Base_Licitacoes_RN" 
NOME_ABA = "Dados"

# Configurações do Portal Nacional (PNCP)
BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
ESTADO = "RN"
DATA_INICIO = "20260101"
DATA_FIM = datetime.now().strftime("%Y%m%d")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

# --- CÉREBRO: CLASSIFICAÇÃO "AUDITOR" (NATUREZA + FUNÇÃO) ---
def classificar_auditor(objeto):
    texto = str(objeto).lower()
    
    # --- ETAPA 1: DEFINIR A NATUREZA ---
    natureza = "AQUISIÇÃO" 
    
    if any(x in texto for x in ['contratacao', 'prestacao', 'servico', 'manutencao', 'reparo', 'limpeza', 'locacao de mao', 'apoio', 'assessoria', 'consultoria', 'publicidade', 'gestao']):
        natureza = "SERVIÇOS"
    elif any(x in texto for x in ['obra', 'pavimentacao', 'construcao', 'reforma', 'ampliacao', 'drenagem', 'engenharia', 'edificacao', 'muro', 'tapa buraco']):
        natureza = "OBRAS"
    elif any(x in texto for x in ['locacao', 'aluguel', 'arrendamento']):
        if 'mao de obra' in texto or 'motorista' in texto:
            natureza = "SERVIÇOS"
        else:
            natureza = "LOCAÇÃO"

    # --- ETAPA 2: DEFINIR A FUNÇÃO ---
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

    # Regras de Pontuação
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

    funcao = max(scores, key=scores.
