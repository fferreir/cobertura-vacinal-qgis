import sys
import os
import numpy as np

# --- CONFIGURAÇÃO DOS CAMINHOS DO QGIS (Adicione estas linhas) ---
# Caminho padrão do PyQGIS no Linux (ajuste se o seu for diferente)
qgis_python_path = "/usr/share/qgis/python"
if qgis_python_path not in sys.path:
    sys.path.append(qgis_python_path)
    sys.path.append(f"{qgis_python_path}/plugins")
# -----------------------------------------------------------------

# Desativa a criação de arquivos de metadados auxiliares (.aux.xml) do GDAL.
# Isso impede que o driver PNG tente fazer acessos de atualização não suportados.
os.environ["GDAL_PAM_ENABLED"] = "NO"

# 1. Importações do QGIS
from qgis.core import (
    QgsVectorLayer,
    QgsPrintLayout,
    QgsApplication, # Importante para standalone
    QgsLayoutItemLabel,
    QgsLayoutItemLegend,
    QgsLayoutItemMap,
    QgsLayoutExporter,
    QgsLayoutItem,
    QgsLayoutPoint,
    QgsLayoutSize,
    QgsLayoutMeasurement,
    QgsRendererRange,
    QgsGraduatedSymbolRenderer,
    QgsSymbol,
    QgsUnitTypes,
    QgsProject,
    QgsLayoutItemLabel, # Label para o título
    QgsTextFormat,
)
from qgis.PyQt import QtGui, QtCore


def main():
    # 2. Configuração Inicial do QGIS (Standalone)
    # Ajuste o caminho abaixo se seu QGIS não estiver instalado em /usr (comum em Linux)
    # No Windows, geralmente é algo como "C:/OSGeo4W/apps/qgis"
    qgs_prefix_path = "/usr"

    QgsApplication.setPrefixPath(qgs_prefix_path, True)
    qgs = QgsApplication([], False) # False = Sem interface gráfica (GUI)
    qgs.initQgis()


    def cria_simbologia(cores_faixas, myLayer, myTargetField):
        myRangeList = []
        for categoria in cores_faixas:
            myMin = cores_faixas[categoria]["min"]
            myMax = cores_faixas[categoria]["max"]
            myLabel = cores_faixas[categoria]["etiqueta"]
            myColour = QtGui.QColor(cores_faixas[categoria]["cor"])
            mySymbol = QgsSymbol.defaultSymbol(myLayer.geometryType())
            mySymbol.setColor(myColour)
            myOpacity = 1
            mySymbol.setOpacity(myOpacity)
            myBorderColour = QtGui.QColor("#838383")
            mySymbol.symbolLayer(0).setStrokeWidth(0.1)
            mySymbol.symbolLayer(0).setStrokeColor(myBorderColour)
            myRange = QgsRendererRange(myMin, myMax, mySymbol, myLabel)
            myRangeList.append(myRange)

        myRenderer = QgsGraduatedSymbolRenderer("", myRangeList)
        myClassificationMethod = QgsApplication.classificationMethodRegistry().method("EqualInterval")
        myRenderer.setClassificationMethod(myClassificationMethod)
        myRenderer.setClassAttribute(myTargetField)
        return myRenderer

    # Variáveis
    ano = 2025
    # Verifique se este caminho está correto no ambiente onde vai rodar
    path = "/home/fernando/Downloads/Mapas/"
    arquivo_dados = f"municipios_coberturas_{ano}.csv"
    separador = ","
    epsg = 4674  # SIRGAS 2000
    geometria = "geometry"
    layer_name = "Coberturas Vacinais"

    # Adiciona camada
    uri = f"file://{path+arquivo_dados}?delimiter={separador}&crs=epsg:{epsg}&wktField={geometria}"
    cobertura = QgsVectorLayer(uri, layer_name, "delimitedtext")

    if not cobertura.isValid():
        print("Falha ao carregar a camada! Verifique o caminho do arquivo CSV.")
        sys.exit(1)

    # Seleciona apenas colunas que são numéricas e ignora IDs/Nomes estruturais do IBGE
    vacinas = []
    for field in cobertura.fields():
        nome_coluna = field.name()
        # Ignora se começar com os prefixos administrativos padrões ou colunas de sistema
        if nome_coluna.startswith(('CD_', 'NM_', 'SIGLA_', 'field_', 'geometry')):
            continue
        # Se passar pelo filtro e for uma coluna numérica (int ou double), assume-se que é vacina
        if field.isNumeric():
            vacinas.append(nome_coluna)


    # Importante: No standalone, usamos uma instância nova do projeto, não a singleton da interface
    project = QgsProject.instance()
    project.clear()
    project.addMapLayer(cobertura)

    print(f"Processando {len(vacinas)} vacinas...")

    for vacina in vacinas:
        print(f"Gerando mapa para: {vacina}")

        cores_faixas = {
            "vermelho": {"cor": "#e70304", "etiqueta": "< 80.0", "min": 0, "max": 0.799999},
            "laranja": {"cor": "#fe941e", "etiqueta": "80.0 a 89.9", "min": 0.80, "max": 0.899999},
            "amarelo": {"cor": "#eee907", "etiqueta": "90.0 a 94.9", "min": 0.90, "max": 0.949999},
            "verde": {"cor": "#15a222", "etiqueta": "95.0 a 100.0", "min": 0.95, "max": 1},
            "azul": {"cor": "#4e27e6", "etiqueta": "> 100.0", "min": 1.000001, "max": np.inf},
            "branco": {"cor": "#ffffff", "etiqueta": "Sem informação", "min": -9999, "max": -9999},
        }

        myRenderer = cria_simbologia(cores_faixas, cobertura, vacina)
        cobertura.setRenderer(myRenderer)
        cobertura.triggerRepaint() # Força atualização visual da camada na memória

        # Layout Setup
        manager = project.layoutManager()
        layoutName = "Mapa de coberturas"

        # Remove layout anterior se existir (limpeza)
        layouts_list = manager.printLayouts()
        for layout in layouts_list:
            if layout.name() == layoutName:
                manager.removeLayout(layout)

        layout = QgsPrintLayout(project)
        layout.initializeDefaults()
        layout.setName(layoutName)
        manager.addLayout(layout)

        # Configurar página
        page = layout.pageCollection().page(0)
        page_size = QgsLayoutSize(220, 220, QgsUnitTypes.LayoutMillimeters)
        page.setPageSize(page_size)
        # Nota: layout.renderContext() pode não estar totalmente disponível sem setup extra,
        # mas definimos DPI na exportação.

        # Criar Mapa
        map_item = QgsLayoutItemMap(layout)
        map_item.attemptMove(QgsLayoutPoint(5, 5, QgsUnitTypes.LayoutMillimeters))
        map_item.attemptResize(QgsLayoutSize(210, 210, QgsUnitTypes.LayoutMillimeters))

        # Não usamos iface.activeLayer(). Usamos a variável 'cobertura' direta.
        map_item.setLayers([cobertura]) # Define explicitamente qual layer aparece no mapa
        map_item.zoomToExtent(cobertura.extent())
        layout.addLayoutItem(map_item)

        # 1. Criar Título do Gráfico (Novo)
        title = QgsLayoutItemLabel(layout)
        title.setText(f'{vacina} - {ano}')

        # Configuração da Fonte (Ajuste o tamanho e estilo como desejar)
        font = QtGui.QFont("Arial", 16)
        font.setBold(True)

        text_format = QgsTextFormat()
        text_format.setFont(font)
        text_format.setSize(16)

        title.setTextFormat(text_format)

        # Centralização
        title.setHAlign(QtCore.Qt.AlignCenter) # Alinhamento Horizontal
        title.setVAlign(QtCore.Qt.AlignVCenter) # Alinhamento Vertical

        # Define a largura igual à da página para facilitar a centralização
        # Posiciona no X=0 (início da página) e Y=5 (5mm do topo)
        largura_pagina = page.pageSize().width()
        title.attemptResize(QgsLayoutSize(largura_pagina, 20, QgsUnitTypes.LayoutMillimeters))
        title.attemptMove(QgsLayoutPoint(0, 5, QgsUnitTypes.LayoutMillimeters))

        layout.addLayoutItem(title)

        # Criar Legenda
        legend = QgsLayoutItemLegend(layout)
        legend.setLinkedMap(map_item) # Vincula ao mapa criado
        layout.addLayoutItem(legend)
        legend.setFrameEnabled(False)
        legend.setFrameStrokeWidth(QgsLayoutMeasurement(0.3))
        #legend.setTitle(f'{vacina} - {ano}')
        legend.setTitle('')
        legend.setBackgroundEnabled(False)
        legend.setAutoUpdateModel(False) # Importante manter falso para customizações manuais se houver

        page_height = page.pageSize().height()
        legend.setReferencePoint(QgsLayoutItem.LowerLeft)
        legend.attemptMove(
            QgsLayoutPoint(10, page_height - 20, QgsUnitTypes.LayoutMillimeters),
            useReferencePoint=True,
        )

        # Exportar
        exporter = QgsLayoutExporter(layout)
        image_settings = exporter.ImageExportSettings()
        image_settings.dpi = 300

        # Garante que a pasta de imagens existe
        os.makedirs(path + "images/", exist_ok=True)

        file_name = path + f"images/{ano}_{vacina.replace('/', ' ')}.png"

        if os.path.exists(file_name):
            os.remove(file_name)
        result = exporter.exportToImage(file_name, image_settings)

        if result != QgsLayoutExporter.Success:
            print(f"Erro ao exportar: {vacina}")

    # --- FIM DA LÓGICA ---

    # 3. Finalizar QGIS e limpar memória
    qgs.exitQgis()
    print("Processo concluído.")

if __name__ == "__main__":
    main()
