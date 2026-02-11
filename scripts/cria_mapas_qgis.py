import sys
import os
import numpy as np

# 1. Importações do QGIS
from qgis.core import (
    QgsVectorLayer,
    QgsPrintLayout,
    QgsApplication, # Importante para standalone
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
    ano = 2023
    # Verifique se este caminho está correto no ambiente onde vai rodar
    path = "/home/fernando/Documentos/github/cobertura-vacinal-qgis/"
    arquivo_dados = f"data/municipios_coberturas_{ano}.csv"
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

    vacinas = [x for x in cobertura.fields().names() if x not in ["field_1", "CD_MUN", "NM_MUN", "SIGLA_UF"]]

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
            "azul": {"cor": "#4e27e6", "etiqueta": "> 100.0", "min": 1.000001, "max": np.infty},
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

        # Criar Legenda
        legend = QgsLayoutItemLegend(layout)
        legend.setLinkedMap(map_item) # Vincula ao mapa criado
        layout.addLayoutItem(legend)
        legend.setFrameEnabled(False)
        legend.setFrameStrokeWidth(QgsLayoutMeasurement(0.3))
        legend.setTitle(f'{vacina} - {ano}')
        legend.setBackgroundEnabled(False)
        legend.setAutoUpdateModel(False) # Importante manter falso para customizações manuais se houver

        page_height = page.pageSize().height()
        legend.setReferencePoint(QgsLayoutItem.LowerLeft)
        legend.attemptMove(
            QgsLayoutPoint(10, page_height - 10, QgsUnitTypes.LayoutMillimeters),
            useReferencePoint=True,
        )

        # Exportar
        exporter = QgsLayoutExporter(layout)
        image_settings = exporter.ImageExportSettings()
        image_settings.dpi = 300

        # Garante que a pasta de imagens existe
        os.makedirs(path + "images/", exist_ok=True)

        file_name = path + f"images/{ano}_{vacina.replace('/', ' ')}.png"
        result = exporter.exportToImage(file_name, image_settings)

        if result != QgsLayoutExporter.Success:
            print(f"Erro ao exportar: {vacina}")

    # --- FIM DA LÓGICA ---

    # 3. Finalizar QGIS e limpar memória
    qgs.exitQgis()
    print("Processo concluído.")

if __name__ == "__main__":
    main()
