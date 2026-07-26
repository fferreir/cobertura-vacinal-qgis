import os
import pandas as pd
import geopandas as gpd
import numpy as np

from src.ibge_malha import obter_malha_ibge_mais_recente

def carregar_e_normalizar_excel(arquivo_excel):
    """
    Carrega o arquivo Excel de coberturas vacinais detectando dinamicamente a linha de cabeçalho
    e a coluna que representa o município / código IBGE (compatível com diversos leiautes do Datasus/Qlik).
    """
    df_raw = pd.read_excel(arquivo_excel, header=None)
    
    # Busca a linha onde estão localizados os cabeçalhos de municípios/código IBGE
    linha_hdr = 0
    col_mun_idx = None
    for idx in range(min(15, len(df_raw))):
        row_vals = [str(x).lower() for x in df_raw.iloc[idx].tolist()]
        for c_idx, val in enumerate(row_vals):
            if any(term in val for term in ['município', 'municipio', 'cod mun', 'cd_mun', 'código ibge', 'codigo ibge']):
                linha_hdr = idx
                col_mun_idx = c_idx
                break
        if col_mun_idx is not None:
            break
            
    if linha_hdr == 0:
        coberturas = pd.read_excel(arquivo_excel, header=0)
    else:
        coberturas = pd.read_excel(arquivo_excel, header=linha_hdr)
        linha_vacinas = df_raw.iloc[0].tolist()
        linha_meses = df_raw.iloc[1].tolist() if len(df_raw) > 1 else []
        
        novas_colunas = list(coberturas.columns)
        vacina_atual = None
        
        for c_idx, col_name in enumerate(novas_colunas):
            if c_idx < len(linha_vacinas) and pd.notnull(linha_vacinas[c_idx]) and str(linha_vacinas[c_idx]).strip() not in ['nan', 'None', '', 'Imunobiológico']:
                vacina_atual = str(linha_vacinas[c_idx]).strip()
            
            col_str = str(col_name).strip()
            if 'cobertura vacinal' in col_str.lower():
                mes_str = ""
                if c_idx < len(linha_meses) and pd.notnull(linha_meses[c_idx]):
                    val_mes = str(linha_meses[c_idx]).split(' ')[0].strip()
                    if val_mes not in ['nan', 'None', '', 'Mês/Ano']:
                        mes_str = f" ({val_mes})"
                novas_colunas[c_idx] = f"{vacina_atual or 'Cobertura'}{mes_str}"
                
        coberturas.columns = novas_colunas
        
    # Localizar dinamicamente a coluna do município / código IBGE
    coluna_municipio = None
    for c in coberturas.columns:
        c_str = str(c).lower().strip()
        if any(term in c_str for term in ['município residência', 'município', 'municipio', 'cod mun', 'cd_mun', 'código ibge', 'codigo ibge']):
            coluna_municipio = c
            break
            
    if coluna_municipio is None:
        raise KeyError(
            f"Coluna de município/IBGE não encontrada no arquivo Excel. Colunas encontradas: {list(coberturas.columns)}"
        )
        
    def extrair_ibge_6(val):
        if pd.isna(val) or val is None:
            return None
        val_str = str(val).strip()
        if '-' in val_str:
            val_str = val_str.split('-')[0].strip()
        try:
            val_num = float(val_str)
            if np.isnan(val_num):
                return None
            val_str = str(int(val_num))
        except ValueError:
            pass
        if len(val_str) >= 6 and val_str.isdigit():
            return val_str[:6]
        return None

    coberturas['Código IBGE 6'] = coberturas[coluna_municipio].apply(extrair_ibge_6)
    coberturas = coberturas[coberturas['Código IBGE 6'].notna()].copy()
    coberturas.replace({'-': -9999}, inplace=True)
    
    return coberturas

import csv

def ajusta_base(ano, diretorio_dados):
    """
    Processa a base de dados em Excel baixada do Datasus (coberturas_{ano}.xlsx)
    filtrando estritamente APENAS as colunas de cobertura vacinal e realizando
    a junção espacial com a malha municipal do IBGE.
    """
    ano = str(ano).strip()
    arquivo_excel = os.path.join(diretorio_dados, f"coberturas_{ano}.xlsx")
    
    if not os.path.exists(arquivo_excel):
        raise FileNotFoundError(f"Arquivo Excel não encontrado: {arquivo_excel}")
        
    caminho_shp = obter_malha_ibge_mais_recente(diretorio_dados)

    print(f"Lendo dados de cobertura vacinal de: {arquivo_excel}")
    coberturas = carregar_e_normalizar_excel(arquivo_excel)
    
    # Filtrar estritamente apenas colunas que representam cobertura vacinal
    colunas_descarte = [
        'index', '', ' ', 'Data Extração', 'Região Ocorrência', 'Macrorregião Saúde',
        'Região de Saúde', 'Município Residência', 'Cod Mun Residência', 'Imunobiológico',
        'UF Residência', 'UF'
    ]
    
    colunas_vacinas = []
    for c in coberturas.columns:
        if c == 'Código IBGE 6':
            continue
        c_str = str(c).strip()
        if not c_str or c_str in colunas_descarte:
            continue
        if any(c_str.startswith(prefix) for prefix in ['Doses Aplicadas', 'População', 'Unnamed', 'CD_', 'NM_', 'SIGLA_']):
            continue
        colunas_vacinas.append(c)
        
    # Manter apenas Código IBGE 6 + colunas de cobertura vacinal
    coberturas = coberturas[['Código IBGE 6'] + colunas_vacinas].copy()
    coberturas = coberturas.loc[:, ~coberturas.columns.duplicated()].copy()

    print(f"Lendo shapefile espacial dos municípios: {caminho_shp}")
    municipios = gpd.read_file(caminho_shp, encoding='utf-8')
    municipios['CD_MUN_6'] = municipios['CD_MUN'].apply(lambda x: str(x)[0:6])
    
    # Selecionar apenas colunas geográficas essenciais da malha do IBGE para evitar poluição de colunas regionais
    colunas_ibge_base = ['CD_MUN', 'NM_MUN', 'SIGLA_UF', 'geometry', 'CD_MUN_6']
    colunas_ibge_existentes = [col for col in colunas_ibge_base if col in municipios.columns]
    municipios_base = municipios[colunas_ibge_existentes].copy()

    print("Realizando junção espacial das bases de cobertura vacinal...")
    municipios_cobertura = municipios_base.merge(coberturas, how='left', left_on='CD_MUN_6', right_on='Código IBGE 6')
    municipios_cobertura.drop(columns=['CD_MUN_6', 'Código IBGE 6'], inplace=True, errors='ignore')
    
    # Converter colunas de vacinas para numeric float
    colunas_nao_vacina = ['CD_MUN', 'NM_MUN', 'SIGLA_UF', 'geometry']
    colunas_imunobiologicos = [col for col in municipios_cobertura.columns if col not in colunas_nao_vacina]
    
    for vacina in colunas_imunobiologicos:
        municipios_cobertura[vacina] = pd.to_numeric(municipios_cobertura[vacina], errors='coerce')
        
    # Converter a coluna de geometria em WKT string para escrita e leitura perfeita em CSV
    if 'geometry' in municipios_cobertura.columns:
        municipios_cobertura['geometry'] = municipios_cobertura['geometry'].apply(lambda g: g.wkt if g is not None and hasattr(g, 'wkt') else str(g) if g is not None else "")

    caminho_csv = os.path.join(diretorio_dados, f"municipios_coberturas_{ano}.csv")
    print(f"Salvando base ajustada (apenas coberturas vacinais) em: {caminho_csv}")
    municipios_cobertura.to_csv(caminho_csv, index=False, encoding='utf-8', quoting=csv.QUOTE_MINIMAL)
    
    return caminho_csv

if __name__ == "__main__":
    diretorio_data = os.path.abspath(os.path.join(os.getcwd(), "data"))
    ajusta_base("2023", diretorio_data)
