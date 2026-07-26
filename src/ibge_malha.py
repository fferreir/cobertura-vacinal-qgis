import os
import ftplib
import zipfile
import glob
import shutil
import re

def remover_malhas_antigas(diretorio_data, pasta_atual):
    """
    Deleta todas as pastas de malhas municipais do IBGE antigas/obsoletas no diretório data,
    mantendo apenas a pasta da malha mais recente (`pasta_atual`).
    """
    pasta_atual_abs = os.path.abspath(pasta_atual)
    for item in os.listdir(diretorio_data):
        caminho_item = os.path.join(diretorio_data, item)
        if os.path.isdir(caminho_item) and re.match(r'^BR_municipios_\d{4}$', item, re.IGNORECASE):
            if os.path.abspath(caminho_item) != pasta_atual_abs:
                print(f"Removendo pasta de malha municipal antiga: {item}")
                shutil.rmtree(caminho_item, ignore_errors=True)

def obter_malha_ibge_mais_recente(diretorio_data, remover_antigas=True):
    """
    Conecta ao servidor FTP oficial do IBGE (geoftp.ibge.gov.br), verifica qual é a versão
    mais recente da malha municipal disponível e realiza o download e extração caso ela
    ainda não esteja presente no diretório local.
    
    Remove automaticamente pastas de malhas municipais anteriores (ex: BR_Municipios_2022 ao baixar 2025/2026).
    """
    os.makedirs(diretorio_data, exist_ok=True)
    base_path = 'organizacao_do_territorio/malhas_territoriais/malhas_municipais'
    
    try:
        print("Consultando servidor FTP do IBGE para verificar malha municipal mais recente...")
        ftp = ftplib.FTP('geoftp.ibge.gov.br', timeout=15)
        ftp.login()
        ftp.cwd(base_path)
        
        items = []
        ftp.dir(items.append)
        
        anos_disponiveis = []
        for item in items:
            partes = item.split()
            nome_pasta = partes[-1]
            if nome_pasta.startswith('municipio_'):
                try:
                    ano = int(nome_pasta.replace('municipio_', ''))
                    anos_disponiveis.append((ano, nome_pasta))
                except ValueError:
                    pass
                    
        anos_disponiveis.sort(key=lambda x: x[0], reverse=True)
        
        for ano, pasta in anos_disponiveis:
            caminhos_possiveis = [
                f'{base_path}/{pasta}/Brasil/BR_Municipios_{ano}.zip',
                f'{base_path}/{pasta}/Brasil/BR/BR_Municipios_{ano}.zip',
                f'{base_path}/{pasta}/Brasil/br_municipios.zip'
            ]
            
            for cam in caminhos_possiveis:
                try:
                    dir_remoto, arq_remoto = os.path.split(cam)
                    ftp.cwd('/')
                    ftp.cwd(dir_remoto)
                    
                    pasta_destino = os.path.join(diretorio_data, f'BR_Municipios_{ano}')
                    shp_esperado = os.path.join(pasta_destino, f'BR_Municipios_{ano}.shp')
                    
                    if os.path.exists(shp_esperado):
                        print(f"Malha municipal mais recente do IBGE ({ano}) já está disponível localmente.")
                        if remover_antigas:
                            remover_malhas_antigas(diretorio_data, pasta_destino)
                        ftp.quit()
                        return shp_esperado
                        
                    print(f"Nova malha municipal do IBGE encontrada ({ano})! Baixando {arq_remoto}...")
                    zip_local = os.path.join(diretorio_data, arq_remoto)
                    
                    with open(zip_local, 'wb') as f:
                        ftp.retrbinary(f'RETR {arq_remoto}', f.write)
                        
                    print(f"Download concluído. Extraindo arquivos em {pasta_destino}...")
                    with zipfile.ZipFile(zip_local, 'r') as zip_ref:
                        zip_ref.extractall(pasta_destino)
                        
                    if os.path.exists(zip_local):
                        os.remove(zip_local)
                        
                    print(f"Malha municipal {ano} do IBGE instalada com sucesso!")
                    
                    if remover_antigas:
                        remover_malhas_antigas(diretorio_data, pasta_destino)
                                
                    ftp.quit()
                    return shp_esperado
                except Exception:
                    continue
                    
        ftp.quit()
    except Exception as e:
        print(f"Aviso: Não foi possível consultar a malha remota via FTP IBGE ({e}).")
        
    # Fallback: encontrar o shapefile local de maior ano disponível
    shapefiles_locais = glob.glob(os.path.join(diretorio_data, "BR_[Mm]unicipios_*", "BR_[Mm]unicipios_*.shp"))
    if shapefiles_locais:
        shapefiles_locais.sort(reverse=True)
        shp_local = shapefiles_locais[0]
        pasta_local = os.path.dirname(shp_local)
        if remover_antigas:
            remover_malhas_antigas(diretorio_data, pasta_local)
        print(f"Utilizando malha municipal local existente: {shp_local}")
        return shp_local
        
    raise FileNotFoundError("Nenhuma malha municipal foi encontrada localmente ou via FTP do IBGE.")

if __name__ == "__main__":
    diretorio = os.path.abspath(os.path.join(os.getcwd(), "data"))
    shp = obter_malha_ibge_mais_recente(diretorio)
    print("Shapefile retornado:", shp)
