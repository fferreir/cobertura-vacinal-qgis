# Cobertura Vacinal por Município (QGIS & Python)

Este projeto automatiza o download, o tratamento dos dados e a geração de mapas temáticos da cobertura vacinal municipal no Brasil a partir dos dados abertos do [Ministério da Saúde (Datasus/SEIDIGI)](https://infoms.saude.gov.br/extensions/SEIDIGI_DEMAS_VACINACAO_CALENDARIO_NACIONAL_COBERTURA_RESIDENCIA/SEIDIGI_DEMAS_VACINACAO_CALENDARIO_NACIONAL_COBERTURA_RESIDENCIA.html) e da malha territorial oficial do **IBGE**.

---

## 🛠️ Estrutura do Projeto

```text
cobertura-vacinal-qgis/
├── data/
│   └── BR_Municipios_2025/        # Malha municipal mais recente baixada do IBGE
├── images/                        # Diretório onde os mapas .png são salvos
├── src/
│   ├── __init__.py
│   ├── downloader.py              # Download via Selenium do painel Datasus
│   ├── ajusta_base.py             # Tratamento dos dados e junção espacial
│   ├── ibge_malha.py              # Download e atualização automática da malha do IBGE
│   └── cria_mapas.py              # Geração dos mapas cloropléticos temáticos
├── main.py                        # Script de execução principal
├── requirements.txt               # Lista de dependências Python
└── README.md
```

---

## 🚀 Como Utilizar

### 1. Requisitos e Instalação

Certifique-se de ter o Python 3.10+ instalado. Crie um ambiente virtual e instale as dependências:

```bash
# Criar e ativar o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar as dependências do projeto
pip install -r requirements.txt
```

### 2. Executar o Pipeline Completo

Para iniciar a execução, basta executar o script `main.py`:

```bash
python main.py
```

O script irá solicitar interativamente o ano desejado (exemplo: `2023`).

Também é possível passar o ano diretamente pela linha de comando:

```bash
python main.py --ano 2023
```

Caso você já possua o arquivo Excel `coberturas_2023.xlsx` dentro da pasta `data/` e queira pular o download via navegador, utilize o parâmetro `--pular-download`:

```bash
python main.py --ano 2023 --pular-download
```

---

## 📊 Fluxo de Processamento

1. **Download (`src/downloader.py`)**: Interage via Selenium/Chrome com o painel Datasus, seleciona o ano informado, alterna para a aba **Dados** e aciona o botão de exportação `<span class="bt-text">Baixar Dados</span>`.
2. **Atualização da Malha (`src/ibge_malha.py`)**: Conecta ao servidor FTP oficial do IBGE (`geoftp.ibge.gov.br`), verifica qual é o ano da malha municipal mais recente publicada e a baixa/extrai automaticamente se for diferente ou mais recente que a versão local.
3. **Ajuste da Base (`src/ajusta_base.py`)**: Limpa os totais gerais, trata dados omissos (`-9999`), extrai os códigos IBGE de 6 dígitos e realiza a junção espacial com a malha atualizada do IBGE.
4. **Geração de Mapas (`src/cria_mapas.py`)**: Gera mapas de alta resolução (300 DPI) para cada vacina disponível, categorizados em 6 faixas de cobertura (<80%, 80-89.9%, 90-94.9%, 95-100%, >100% e Sem informação) com contagem de municípios por faixa na legenda.
