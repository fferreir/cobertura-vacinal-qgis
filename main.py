#!/usr/bin/env python3
import os
import sys
import argparse

# Garantir inclusão do diretório raiz no PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.downloader import baixar_cobertura_vacinal
from src.ajusta_base import ajusta_base
from src.cria_mapas import gerar_mapas

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de download, tratamento e geração de mapas de cobertura vacinal por município."
    )
    parser.add_argument(
        "--ano",
        type=str,
        help="Ano desejado para consulta da cobertura vacinal (ex: 2023)"
    )
    parser.add_argument(
        "--pular-download",
        action="store_true",
        help="Pula a etapa de download caso o arquivo coberturas_{ano}.xlsx já exista no diretório data."
    )
    
    args = parser.parse_args()
    
    # Solicita o ano interativamente caso não tenha sido fornecido via argumento
    ano_desejado = args.ano
    if not ano_desejado:
        ano_desejado = input("Digite o ano a ser baixado (ex: 2023): ").strip()
        
    if not ano_desejado or not ano_desejado.isdigit():
        print("[!] Erro: É necessário informar um ano válido de 4 dígitos (ex: 2023).")
        sys.exit(1)
        
    diretorio_data = os.path.join(ROOT_DIR, "data")
    diretorio_images = os.path.join(ROOT_DIR, "images")
    
    os.makedirs(diretorio_data, exist_ok=True)
    os.makedirs(diretorio_images, exist_ok=True)
    
    print("\n=======================================================")
    print(f"   INICIANDO PIPELINE DE COBERTURA VACINAL - {ano_desejado}")
    print("=======================================================\n")
    
    # 1. Download dos dados do Datasus via Selenium
    arquivo_excel_esperado = os.path.join(diretorio_data, f"coberturas_{ano_desejado}.xlsx")
    if args.pular_download and os.path.exists(arquivo_excel_esperado):
        print(f"[ETAPA 1/3] Plando download: Arquivo {arquivo_excel_esperado} encontrado.")
    else:
        print("[ETAPA 1/3] Iniciando download automatizado no painel Datasus...")
        baixar_cobertura_vacinal(ano_desejado, diretorio_data)
        
    # 2. Ajuste da base de dados e fusão espacial
    print("\n[ETAPA 2/3] Processando e tratando a base de dados (AjustaBase)...")
    caminho_csv = ajusta_base(ano_desejado, diretorio_data)
    print(f"-> Base de dados processada com sucesso: {caminho_csv}")
    
    # 3. Geração dos mapas cloropléticos
    print("\n[ETAPA 3/3] Gerando mapas temáticos por vacina...")
    gerar_mapas(ano_desejado, diretorio_data, diretorio_images)
    
    print("\n=======================================================")
    print(f"   PIPELINE FINALIZADO COM SUCESSO PARA O ANO {ano_desejado}!")
    print(f"   Verifique os mapas gerados em: {diretorio_images}")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
