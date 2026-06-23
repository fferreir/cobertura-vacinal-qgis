import sys
import os
import numpy as np

# --- CONFIGURAÇÃO DOS CAMINHOS DO QGIS ---
qgis_python_path = "/usr/share/qgis/python"
if qgis_python_path not in sys.path:
    sys.path.append(qgis_python_path)
    sys.path.append(f"{qgis_python_path}/plugins")
# -----------------------------------------------------------------

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["GDAL_PAM_ENABLED"] = "NO"

# 1. Importações do QGIS
from qgis.core import (
    QgsVectorLayer,
    QgsPrintLayout,
    QgsApplication,
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
    QgsTextFormat,
)
from qgis.PyQt import QtGui, QtCore


def main():
    qgs_prefix_path = "/usr"

    QgsApplication.setPrefixPath(qgs_prefix_path, True)
    qgs = QgsApplication([], False)
    qgs.initQgis()

    def cria_simbologia(cores_faixas, myLayer, myTargetField):
        myRangeList = []

        # --- CÁLCULO DAS ETIQUETAS COM CONTAGEM ---
        # 1. Obter todos os valores da vacina atual ignorando valores nulos/inválidos se necessário
        valores = []
        for feature in myLayer.getFeatures():
            val = feature[myTargetField]
            if val is not None and val != NULL: # Garante compatibilidade com tipos do QGIS
                try:
                    valores.append(float(val))
                except (ValueError, TypeError):
                    continue

        total_municipios = len(valores)
        # -------------------------------------------------

        for categoria in cores_faixas:
            myMin = cores_faixas[categoria]["min"]
            myMax = cores_faixas[categoria]["max"]
            myLabelOrig = cores_faixas[categoria]["etiqueta"]

            # --- CONTAGEM POR FAIXA ---
            if myMin == -9999 and myMax == -9999:
                # Caso especial para "Sem informação" (valores menores que 0 ou específicos)
                n_municipios = sum(1 for v in valores if v < 0)
            elif myMax == np.inf:
                n_municipios = sum(1 for v in valores if v >= myMin)
            else:
                n_municipios = sum(1 for v in valores if myMin <= v <= myMax)

            # Nova etiqueta formatada: "Etiqueta (X/Total)"
            myLabel = f"{myLabelOrig} ({n_municipios})"
            #myLabel = f"{myLabelOrig} ({n_municipios}/{total_municipios})"
            # -------------------------------------------------

            myColour = QtGui.QColor(cores_faixas[categoria]["cor"])
            mySymbol = QgsSymbol.defaultSymbol(myLayer.geometryType())
            mySymbol.setColor(myColour)
            mySymbol.setOpacity(1)

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
    path = "/home/fernando/Downloads/Mapas/"
    arquivo_dados = f"municipios_coberturas_{ano}.csv"
    separador = ","
    epsg = 4674  # SIRGAS 2000
    geometria = "geometry"
    layer_name = "Coberturas Vacinais"

    # Adiciona camada
    uri = f"file://{path+arquivo_dados}?delimiter={separador}&crs=epsg:{epsg}&wktField={geometria}"

    # Importar NULL do QGIS para tratamento de dados vazios
    from qgis.core import NULL

    cobertura = QgsVectorLayer(uri, layer_name, "delimitedtext")

    if not cobertura.isValid():
        print("Falha ao carregar a camada! Verifique o caminho do arquivo CSV.")
        sys.exit(1)

    vacinas = []
    for field in cobertura.fields():
        nome_coluna = field.name()
        if nome_coluna.startswith(('CD_', 'NM_', 'SIGLA_', 'field_', 'geometry')):
            continue
        if field.isNumeric():
            vacinas.append(nome_coluna)

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
        cobertura.triggerRepaint()

        # Layout Setup
        manager = project.layoutManager()
        layoutName = "Mapa de coberturas"

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

        # Criar Mapa
        map_item = QgsLayoutItemMap(layout)
        map_item.attemptMove(QgsLayoutPoint(5, 5, QgsUnitTypes.LayoutMillimeters))
        map_item.attemptResize(QgsLayoutSize(210, 210, QgsUnitTypes.LayoutMillimeters))
        map_item.setLayers([cobertura])
        map_item.zoomToExtent(cobertura.extent())
        layout.addLayoutItem(map_item)

        # Criar Título
        title = QgsLayoutItemLabel(layout)
        title.setText(f'{vacina} - {ano}')

        font = QtGui.QFont("Arial", 16)
        font.setBold(True)
        text_format = QgsTextFormat()
        text_format.setFont(font)
        text_format.setSize(16)
        title.setTextFormat(text_format)

        title.setHAlign(QtCore.Qt.AlignCenter)
        title.setVAlign(QtCore.Qt.AlignVCenter)

        largura_pagina = page.pageSize().width()
        title.attemptResize(QgsLayoutSize(largura_pagina, 20, QgsUnitTypes.LayoutMillimeters))
        title.attemptMove(QgsLayoutPoint(0, 2, QgsUnitTypes.LayoutMillimeters))
        layout.addLayoutItem(title)

        # Criar Legenda
        legend = QgsLayoutItemLegend(layout)
        legend.setLinkedMap(map_item)
        layout.addLayoutItem(legend)
        legend.setFrameEnabled(False)
        legend.setFrameStrokeWidth(QgsLayoutMeasurement(0.3))
        legend.setTitle('')
        legend.setBackgroundEnabled(False)
        legend.setAutoUpdateModel(False)

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

        os.makedirs(path + "images/", exist_ok=True)
        file_name = path + f"images/{ano}_{vacina.replace('/', ' ')}.png"

        if os.path.exists(file_name):
            os.remove(file_name)
        result = exporter.exportToImage(file_name, image_settings)

        if result != QgsLayoutExporter.Success:
            print(f"Erro ao exportar: {vacina}")

    qgs.exitQgis()
    print("Processo concluído.")

if __name__ == "__main__":
    main()
