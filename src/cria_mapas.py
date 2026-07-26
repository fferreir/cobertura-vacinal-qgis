import os
import sys
import importlib
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib as mpl

def tentar_importar_qgis():
    """
    Tenta carregar dinamicamente os módulos do QGIS caso estejam disponíveis no sistema,
    evitando alertas de erro de importação estática na IDE.
    """
    qgis_paths = ["/usr/share/qgis/python", "/usr/lib/python3/dist-packages"]
    for path in qgis_paths:
        if os.path.exists(path) and path not in sys.path:
            sys.path.append(path)
            
    try:
        qgis_core = importlib.import_module("qgis.core")
        qgis_pyqt_gui = importlib.import_module("qgis.PyQt.QtGui")
        qgis_pyqt_core = importlib.import_module("qgis.PyQt.QtCore")
        return qgis_core, qgis_pyqt_gui, qgis_pyqt_core
    except Exception:
        return None, None, None

def gerar_mapas_qgis(caminho_csv, ano, diretorio_saida):
    """
    Gera os mapas utilizando a API nativa do QGIS (quando o ambiente QGIS está presente no sistema).
    """
    qgis_core, qgis_pyqt_gui, qgis_pyqt_core = tentar_importar_qgis()
    if not qgis_core:
        return False

    try:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ["GDAL_PAM_ENABLED"] = "NO"

        QgsApplication = qgis_core.QgsApplication
        QgsVectorLayer = qgis_core.QgsVectorLayer
        QgsProject = qgis_core.QgsProject
        QgsPrintLayout = qgis_core.QgsPrintLayout
        QgsLayoutSize = qgis_core.QgsLayoutSize
        QgsLayoutPoint = qgis_core.QgsLayoutPoint
        QgsLayoutItemMap = qgis_core.QgsLayoutItemMap
        QgsLayoutItemLabel = qgis_core.QgsLayoutItemLabel
        QgsTextFormat = qgis_core.QgsTextFormat
        QgsLayoutItemLegend = qgis_core.QgsLayoutItemLegend
        QgsLayoutMeasurement = qgis_core.QgsLayoutMeasurement
        QgsLayoutExporter = qgis_core.QgsLayoutExporter
        QgsSymbol = qgis_core.QgsSymbol
        QgsRendererRange = qgis_core.QgsRendererRange
        QgsGraduatedSymbolRenderer = qgis_core.QgsGraduatedSymbolRenderer
        QgsUnitTypes = qgis_core.QgsUnitTypes
        NULL = qgis_core.NULL

        QtGui = qgis_pyqt_gui
        QtCore = qgis_pyqt_core

        QgsApplication.setPrefixPath("/usr", True)
        qgs = QgsApplication([], False)
        qgs.initQgis()

        uri = f"file://{os.path.abspath(caminho_csv)}?delimiter=,&crs=epsg:4674&wktField=geometry"
        cobertura = QgsVectorLayer(uri, "Coberturas Vacinais", "delimitedtext")

        if not cobertura.isValid():
            qgs.exitQgis()
            return False

        vacinas = []
        for field in cobertura.fields():
            nome_coluna = field.name()
            if any(nome_coluna.startswith(p) for p in ['CD_', 'NM_', 'SIGLA_', 'field_', 'geometry', 'Unnamed', 'Doses', 'População', 'Data', 'AREA_']):
                continue
            if field.isNumeric():
                vacinas.append(nome_coluna)

        project = QgsProject.instance()
        project.clear()
        project.addMapLayer(cobertura)

        os.makedirs(diretorio_saida, exist_ok=True)
        total_features = cobertura.featureCount()

        for vacina in vacinas:
            cores_faixas = {
                "vermelho": {"cor": "#e70304", "etiqueta": "< 80.0", "min": 0, "max": 0.799999},
                "laranja": {"cor": "#fe941e", "etiqueta": "80.0 a 89.9", "min": 0.80, "max": 0.899999},
                "amarelo": {"cor": "#eee907", "etiqueta": "90.0 a 94.9", "min": 0.90, "max": 0.949999},
                "verde": {"cor": "#15a222", "etiqueta": "95.0 a 100.0", "min": 0.95, "max": 1},
                "azul": {"cor": "#4e27e6", "etiqueta": "> 100.0", "min": 1.000001, "max": np.inf},
                "branco": {"cor": "#ffffff", "etiqueta": "Sem informação", "min": -9999, "max": -9999},
            }

            valores = []
            for feature in cobertura.getFeatures():
                val = feature[vacina]
                if val is not None and val != NULL:
                    try:
                        valores.append(float(val))
                    except (ValueError, TypeError):
                        continue

            myRangeList = []
            for categoria, cfg in cores_faixas.items():
                myMin, myMax, myLabelOrig = cfg["min"], cfg["max"], cfg["etiqueta"]
                if myMin == -9999 and myMax == -9999:
                    n_validos = sum(1 for v in valores if v >= 0)
                    n_mun = total_features - n_validos
                elif myMax == np.inf:
                    n_mun = sum(1 for v in valores if v >= myMin)
                else:
                    n_mun = sum(1 for v in valores if myMin <= v <= myMax)

                myLabel = f"{myLabelOrig} ({n_mun})"
                myColour = QtGui.QColor(cfg["cor"])
                mySymbol = QgsSymbol.defaultSymbol(cobertura.geometryType())
                mySymbol.setColor(myColour)
                mySymbol.setOpacity(1)
                myBorderColour = QtGui.QColor("#838383")
                mySymbol.symbolLayer(0).setStrokeWidth(0.1)
                mySymbol.symbolLayer(0).setStrokeColor(myBorderColour)

                myRangeList.append(QgsRendererRange(myMin, myMax, mySymbol, myLabel))

            myRenderer = QgsGraduatedSymbolRenderer("", myRangeList)
            myClassificationMethod = QgsApplication.classificationMethodRegistry().method("EqualInterval")
            myRenderer.setClassificationMethod(myClassificationMethod)
            myRenderer.setClassAttribute(vacina)
            cobertura.setRenderer(myRenderer)
            cobertura.triggerRepaint()

            manager = project.layoutManager()
            layoutName = "Mapa de coberturas"
            for l in manager.printLayouts():
                if l.name() == layoutName:
                    manager.removeLayout(l)

            layout = QgsPrintLayout(project)
            layout.initializeDefaults()
            layout.setName(layoutName)
            manager.addLayout(layout)

            page = layout.pageCollection().page(0)
            page.setPageSize(QgsLayoutSize(220, 220, QgsUnitTypes.LayoutMillimeters))

            map_item = QgsLayoutItemMap(layout)
            map_item.attemptMove(QgsLayoutPoint(5, 5, QgsUnitTypes.LayoutMillimeters))
            map_item.attemptResize(QgsLayoutSize(210, 210, QgsUnitTypes.LayoutMillimeters))
            map_item.setLayers([cobertura])
            map_item.zoomToExtent(cobertura.extent())
            layout.addLayoutItem(map_item)

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
            title.attemptResize(QgsLayoutSize(page.pageSize().width(), 20, QgsUnitTypes.LayoutMillimeters))
            title.attemptMove(QgsLayoutPoint(0, 2, QgsUnitTypes.LayoutMillimeters))
            layout.addLayoutItem(title)

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

            exporter = QgsLayoutExporter(layout)
            image_settings = exporter.ImageExportSettings()
            image_settings.dpi = 300

            file_name = os.path.join(diretorio_saida, f"{ano}_{vacina.replace('/', ' ')}.png")
            if os.path.exists(file_name):
                os.remove(file_name)
            exporter.exportToImage(file_name, image_settings)

        qgs.exitQgis()
        print("Mapas QGIS gerados com sucesso!")
        return True
    except Exception as e:
        print(f"Executando fallback em Matplotlib ({e})...")
        return False

def gerar_mapas_matplotlib(caminho_csv, ano, diretorio_saida):
    """
    Gera mapas temáticos utilizando GeoPandas e Matplotlib.
    """
    print("Gerando mapas via GeoPandas/Matplotlib...")
    df = pd.read_csv(caminho_csv)
    df['geometry'] = gpd.GeoSeries.from_wkt(df['geometry'])
    gdf = gpd.GeoDataFrame(df, geometry='geometry')

    colunas_ignorar = ['Unnamed: 0', '', ' ', 'CD_MUN', 'NM_MUN', 'SIGLA_UF', 'geometry', 'UF Residência', 'UF']
    imunogenos = [
        c for c in gdf.columns
        if str(c).strip() not in colunas_ignorar and not any(str(c).startswith(p) for p in ['Doses', 'População', 'Data', 'CD_', 'NM_', 'SIGLA_', 'AREA_'])
    ]

    os.makedirs(diretorio_saida, exist_ok=True)
    gdf.replace({-9999: None}, inplace=True)

    bins = [.79999, 0.89999, 0.94999, 1]
    colours = ["#e70304", "#fe941e", "#eee907", "#15a222", "#4e27e6"]
    cmap = mpl.colors.ListedColormap(colours)

    for imunogeno in imunogenos:
        vals = gdf[imunogeno].dropna()
        if len(vals) == 0:
            continue
        print(f"Gerando mapa Matplotlib para: {imunogeno}")
        fig, ax = plt.subplots(figsize=(11, 11), subplot_kw=dict(aspect='equal'))
        
        vals = gdf[imunogeno].dropna()
        c1 = (vals < 0.8).sum()
        c2 = ((vals >= 0.8) & (vals < 0.9)).sum()
        c3 = ((vals >= 0.9) & (vals < 0.95)).sum()
        c4 = ((vals >= 0.95) & (vals <= 1.0)).sum()
        c5 = (vals > 1.0).sum()
        c_missing = gdf[imunogeno].isna().sum()

        labels = [
            f"< 80.0 ({c1})",
            f"80.0 a 89.9 ({c2})",
            f"90.0 a 94.9 ({c3})",
            f"95.0 a 100.0 ({c4})",
            f"> 100.0 ({c5})"
        ]

        ax.set_title(f"{imunogeno} - {ano}", fontsize=16, fontweight='bold', pad=15)

        gdf.plot(
            column=imunogeno,
            scheme='UserDefined',
            missing_kwds=dict(color='#FFFFFF', label=f'Sem informação ({c_missing})'),
            classification_kwds={'bins': bins, 'lowest': 0},
            cmap=cmap,
            legend_kwds={
                "title": "Coberturas Vacinais",
                "loc": "lower left",
                "bbox_to_anchor": (0.038, 0.05, 0., 0.),
                "title_fontsize": 14,
                "fontsize": 12,
                "frameon": False,
                "labels": labels,
                "alignment": "left",
                "markerscale": 1.5,
            },
            legend=True,
            ax=ax,
            edgecolor="#838383",
            linewidth=0.2
        )

        ax.set_axis_off()
        plt.tight_layout()
        caminho_figura = os.path.join(diretorio_saida, f"{ano}_{imunogeno.replace('/', ' ')}.png")
        fig.savefig(caminho_figura, dpi=300, pad_inches=0)
        plt.close(fig)

    print("Mapas gerados com sucesso!")

def gerar_mapas(ano, diretorio_dados, diretorio_saida):
    """
    Função principal que orquestra a geração dos mapas de cobertura vacinal.
    """
    caminho_csv = os.path.join(diretorio_dados, f"municipios_coberturas_{ano}.csv")
    if not os.path.exists(caminho_csv):
        raise FileNotFoundError(f"Arquivo CSV ajustado não encontrado: {caminho_csv}")

    sucesso = False
    try:
        sucesso = gerar_mapas_qgis(caminho_csv, ano, diretorio_saida)
    except Exception as e:
        print(f"Não foi possível utilizar o QGIS: {e}")

    if not sucesso:
        gerar_mapas_matplotlib(caminho_csv, ano, diretorio_saida)

if __name__ == "__main__":
    diretorio_data = os.path.abspath(os.path.join(os.getcwd(), "data"))
    diretorio_img = os.path.abspath(os.path.join(os.getcwd(), "images"))
    gerar_mapas("2023", diretorio_data, diretorio_img)
