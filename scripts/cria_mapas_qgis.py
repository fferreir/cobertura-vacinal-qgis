from qgis.core import (
    QgsVectorLayer,
    QgsPrintLayout,
    QgsApplication,
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
)
from qgis.PyQt import QtGui
from qgis.utils import iface
import numpy as np


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
    myClassificationMethod = QgsApplication.classificationMethodRegistry().method(
        "EqualInterval"
    )
    myRenderer.setClassificationMethod(myClassificationMethod)
    myRenderer.setClassAttribute(myTargetField)
    return myRenderer


# Variáveis
ano = 2023
path = "/home/fernando/Documentos/github/cobertura-vacinal-qgis/"
arquivo_dados = f"data/municipios_coberturas_{ano}.csv"
separador = ","
epsg = 4674  # SIRGAS 2000
geometria = "geometry"
layer_name = "Coberturas Vacinais"

# Adiciona camada
uri = f"file://{path+arquivo_dados}?delimiter={separador}&crs=epsg:{epsg}&wktField={geometria}"
cobertura = QgsVectorLayer(uri, layer_name, "delimitedtext")
vacinas = [x for x in cobertura.fields().names() if x not in ["field_1", "CD_MUN", "NM_MUN", "SIGLA_UF"]]
QgsProject.instance().clear()
QgsProject.instance().addMapLayer(cobertura)

for vacina in vacinas:
    # Cores
    # Vermelho #e70304 (< 80%)
    # Laranja #fe941e (80 a 89.9%)
    # Amarelo #eee907 (90 a 94.9%)
    # Verde #15a222 (95 a 100%)
    # Azul #4e27e6 ( > 100%)

    ListaFaixas = []
    Opacidade = 1
    cores_faixas = {
        "vermelho": {
            "cor": "#e70304",
            "etiqueta": "< 80.0",
            "min": 0,
            "max": 0.799999
        },
        "laranja": {
            "cor": "#fe941e",
            "etiqueta": "80.0 a 89.9",
            "min": 0.80,
            "max": 0.899999,
        },
        "amarelo": {
            "cor": "#eee907",
            "etiqueta": "90.0 a 94.9",
            "min": 0.90,
            "max": 0.949999,
        },
        "verde": {
            "cor": "#15a222",
            "etiqueta": "95.0 a 100.0",
            "min": 0.95,
            "max": 1
        },
        "azul": {
            "cor": "#4e27e6",
            "etiqueta": "> 100.0",
            "min": 1.000001,
            "max": np.infty,
        },
        "branco": {
            "cor": "#ffffff",
            "etiqueta": "Sem informação",
            "min": -9999,
            "max": -9999,
        },
    }

    myRenderer = cria_simbologia(cores_faixas, cobertura, vacina)
    cobertura.setRenderer(myRenderer)

    # create Layout
    project = QgsProject.instance()
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

    # layout size
    page = layout.items()[1]
    page_size = QgsLayoutSize(220, 220, QgsUnitTypes.LayoutMillimeters)
    page.setPageSize(page_size)
    page.attemptResize(page_size)
    layout.renderContext().setDpi(300)

    # create map item in the layout
    map = QgsLayoutItemMap(layout)
    map.attemptMove(QgsLayoutPoint(5, 5, QgsUnitTypes.LayoutMillimeters))
    map.attemptResize(QgsLayoutSize(210, 210, QgsUnitTypes.LayoutMillimeters))
    layer = iface.activeLayer()
    map.zoomToExtent(iface.activeLayer().extent())
    layout.addLayoutItem(map)

    # create legend
    legend = QgsLayoutItemLegend(layout)
    layout.addLayoutItem(legend)
    legend.setId("Legend")
    layout.addLayoutItem(legend)
    legend.setFrameEnabled(False)
    legend.setFrameStrokeWidth(QgsLayoutMeasurement(0.3))
    legend.setTitle(f'{vacina} - {ano}')
    legend.setBackgroundEnabled(False)
    legend.setAutoUpdateModel(False)

    pages = layout.pageCollection()
    page = pages.page(0)
    page_width = page.pageSize().width()
    page_height = page.pageSize().height()

    legend.setReferencePoint(QgsLayoutItem.LowerLeft)
    # Pass map width & height values (subtract a small amount) for position of legend lower-right corner
    legend.attemptMove(
        QgsLayoutPoint(10, page_height - 10, QgsUnitTypes.LayoutMillimeters),
        useReferencePoint=True,
    )

    # Export layout to image
    exporter = QgsLayoutExporter(layout)
    image_settings = exporter.ImageExportSettings()
    image_settings.dpi = 300
    file_name = path + f"images/{ano}_{vacina.replace('/', ' ')}.png"
    exporter.exportToImage(file_name, image_settings)
