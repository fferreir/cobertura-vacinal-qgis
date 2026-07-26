import os
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def baixar_cobertura_vacinal(ano_desejado, diretorio_download):
    """
    Realiza o download dos dados de cobertura vacinal por município para o ano especificado
    diretamente do painel Datasus/Qlik do Ministério da Saúde via Selenium.
    """
    ano_desejado = str(ano_desejado).strip()
    os.makedirs(diretorio_download, exist_ok=True)
    
    caminho_arquivo_final = os.path.join(diretorio_download, f"coberturas_{ano_desejado}.xlsx")
    if os.path.exists(caminho_arquivo_final):
        try:
            os.remove(caminho_arquivo_final)
        except Exception:
            pass
            
    arquivos_antes = set(os.listdir(diretorio_download))
    
    chrome_options = Options()
    prefs = {
        "download.default_directory": diretorio_download,
        "download.prompt_for_download": False,
        "directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    print("Inicializando o navegador...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    wait = WebDriverWait(driver, 40)  # Aumentado para 40s devido à latência da RNDS
    
    caminho_arquivo_final = os.path.join(diretorio_download, f"coberturas_{ano_desejado}.xlsx")
    
    try:
        url = "https://infoms.saude.gov.br/extensions/SEIDIGI_DEMAS_VACINACAO_CALENDARIO_NACIONAL_COBERTURA_RESIDENCIA/SEIDIGI_DEMAS_VACINACAO_CALENDARIO_NACIONAL_COBERTURA_RESIDENCIA.html"
        print("Acessando o painel SEIDIGI/Datasus...")
        driver.get(url)
        
        # Aguarda o motor do painel carregar os dados
        print("Aguardando o motor do painel carregar os dados...")
        time.sleep(20) 
        
        # 3. Interagir com os Filtros (Sem limpar filtros)
        print(f"Configurando filtro para o ano: {ano_desejado}...")
        
        # 3.1. Selecionar o ano desejado no elemento select
        print(f"Aplicando o ano: {ano_desejado}")
        driver.execute_script("""
            var ano = arguments[0];
            var selects = document.querySelectorAll('select');
            for (var s of selects) {
                var optionTexts = Array.from(s.options).map(function(o) { return o.text.trim(); });
                if (optionTexts.includes('Ano') || optionTexts.includes(ano) || optionTexts.includes('2026') || optionTexts.includes('2025') || optionTexts.includes('2024') || optionTexts.includes('2023')) {
                    for (var i = 0; i < s.options.length; i++) {
                        if (s.options[i].text.trim() === ano || s.options[i].value.trim() === ano) {
                            s.selectedIndex = i;
                            break;
                        }
                    }
                    s.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
                    s.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                    break;
                }
            }
        """, ano_desejado)
        
        time.sleep(5) 
        
        # 3.5. Selecionar a Aba "Dados" (aba2-tab)
        print("Alternando para a aba 'Dados' (aba2-tab)...")
        try:
            aba_dados = wait.until(EC.presence_of_element_located((By.ID, "aba2-tab")))
            driver.execute_script("arguments[0].click();", aba_dados)
            print("Aba 'Dados' selecionada. Aguardando 10s para renderizar a tabela...")
            time.sleep(10)
        except Exception as e_aba:
            print(f"[!] Aviso ao tentar selecionar a aba 'Dados': {e_aba}")
        
        # 4. Acionar a exportação da tabela principal (ID: exportar-dados-QV1-10) ao lado de Baixar Dados (Numerador)
        print("Acionando a extração dos dados da tabela principal (exportar-dados-QV1-10)...")
        xpath_botao = "//*[@id='exportar-dados-QV1-10']"
        
        botao_baixar = None
        try:
            botao_baixar = wait.until(EC.presence_of_element_located((By.XPATH, xpath_botao)))
        except Exception:
            # Se não encontrou no contexto principal, tenta alternar entre os iframes
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                driver.switch_to.frame(frame)
                try:
                    botao_baixar = driver.find_element(By.XPATH, xpath_botao)
                    if botao_baixar:
                        print("Botão de exportação localizado dentro de um iframe.")
                        break
                except Exception:
                    driver.switch_to.default_content()

        if not botao_baixar:
            raise Exception("Não foi possível localizar o botão de download com o ID 'exportar-dados-QV1-10'.")

        # Tenta rolar até o elemento e clicar de múltiplas formas
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_baixar)
        time.sleep(1)
        
        try:
            botao_baixar.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", botao_baixar)
            except Exception:
                driver.execute_script("var evt = document.createEvent('MouseEvents'); evt.initEvent('click', true, true); arguments[0].dispatchEvent(evt);", botao_baixar)
        
        # 5. Aguardar o download
        print("Aguardando a conclusão do download...")
        tempo_limite = 90
        inicio = time.time()
        arquivo_baixado = None
        
        while time.time() - inicio < tempo_limite:
            time.sleep(2)
            crdownloads = [f for f in os.listdir(diretorio_download) if f.endswith(('.crdownload', '.tmp', '.part'))]
            if crdownloads:
                continue
                
            arquivos_atuais = set(os.listdir(diretorio_download))
            novos_arquivos = arquivos_atuais - arquivos_antes
            arquivos_validos = [f for f in novos_arquivos if not f.endswith(('.crdownload', '.tmp', '.part'))]
            
            if arquivos_validos:
                candidato = os.path.join(diretorio_download, arquivos_validos[0])
                try:
                    t1 = os.path.getsize(candidato)
                    if t1 > 0:
                        time.sleep(3)
                        t2 = os.path.getsize(candidato)
                        if t1 == t2:
                            arquivo_baixado = candidato
                            break
                except Exception:
                    pass
                
        if arquivo_baixado and os.path.exists(arquivo_baixado):
            if os.path.exists(caminho_arquivo_final) and os.path.abspath(arquivo_baixado) != os.path.abspath(caminho_arquivo_final):
                os.remove(caminho_arquivo_final)
            if os.path.abspath(arquivo_baixado) != os.path.abspath(caminho_arquivo_final):
                os.rename(arquivo_baixado, caminho_arquivo_final)
            print(f"Processo finalizado com sucesso. Arquivo salvo em: {caminho_arquivo_final}")
            return caminho_arquivo_final
        else:
            if os.path.exists(caminho_arquivo_final):
                print(f"Arquivo encontrado em: {caminho_arquivo_final}")
                return caminho_arquivo_final
            print(f"Processo finalizado. Verifique o diretório: {diretorio_download}")
            return caminho_arquivo_final
        
    except Exception as e:
        caminho_print = os.path.join(os.getcwd(), "debug_erro_datasus.png")
        driver.save_screenshot(caminho_print)
        print(f"\n[!] Falha durante a execução: {type(e).__name__}: {e}")
        print(f"Screenshot salvo em '{caminho_print}' para depuração do layout.")
        raise e
    finally:
        driver.quit()

if __name__ == "__main__":
    pasta_destino = os.path.abspath(os.path.join(os.getcwd(), "data"))
    os.makedirs(pasta_destino, exist_ok=True)
    baixar_cobertura_vacinal('2023', pasta_destino)
