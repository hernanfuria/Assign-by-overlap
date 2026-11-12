import os
from qgis.core import (
    QgsProject,
    Qgis,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsSpatialIndex,
    QgsCoordinateReferenceSystem,
    QgsWkbTypes
)
from qgis.gui import QgisInterface
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QPushButton,
    QGroupBox,
    QCheckBox,
    QMessageBox
)
from qgis.PyQt.QtCore import Qt

class NodeAssignerDialog(QDialog):
    """Ventana de configuración para seleccionar la capa de nodos y opciones de asignación."""
    def __init__(self, vector_layers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Asignador Automático de Nodos por Superposición")
        self.resize(500, 300)
        self.vector_layers = vector_layers
        
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Información de capas seleccionadas
        lbl_info = QLabel(f"Capas seleccionadas para procesar: {len(self.vector_layers)}")
        layout.addWidget(lbl_info)

        # Grupo de selección de Capa de Origen (Nodos)
        group_box = QGroupBox("Capa de Límites de Nodos (Polígonos)")
        group_layout = QVBoxLayout()

        self.combo_node_layer = QComboBox()
        # Llenar solo con capas poligonales disponibles en el proyecto
        all_layers = QgsProject.instance().mapLayers().values()
        self.polygon_layers = [l for l in all_layers if isinstance(l, QgsVectorLayer) and l.geometryType() == QgsWkbTypes.PolygonGeometry]
        
        for layer in self.polygon_layers:
            self.combo_node_layer.addItem(layer.name(), layer)

        self.combo_node_layer.currentIndexChanged.connect(self._update_fields_combo)
        
        # Campo de nombre de nodo
        self.combo_node_field = QComboBox()
        
        group_layout.addWidget(QLabel("Seleccionar Capa de Polígonos:"))
        group_layout.addWidget(self.combo_node_layer)
        group_layout.addWidget(QLabel("Seleccionar Campo con Nombre de Nodo:"))
        group_layout.addWidget(self.combo_node_field)
        group_box.setLayout(group_layout)
        layout.addWidget(group_box)

        # Inicializar campos de la primera capa si existe
        if self.polygon_layers:
            self._update_fields_combo(0)

        # Checkbox de sobrescritura
        self.chk_overwrite = QCheckBox("Sobrescribir valores si el campo ya existe")
        self.chk_overwrite.setChecked(True)
        layout.addWidget(self.chk_overwrite)

        # Botones de acción
        btn_layout = QHBoxLayout()
        btn_run = QPushButton("Ejecutar Asignación")
        btn_run.clicked.connect(self.accept)
        btn_abort = QPushButton("Cancelar")
        btn_abort.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_run)
        btn_layout.addWidget(btn_abort)
        layout.addLayout(btn_layout)

    def _update_fields_combo(self, index):
        """Actualiza el combo de campos cuando cambia la capa de nodos seleccionada."""
        self.combo_node_field.clear()
        if 0 <= index < len(self.polygon_layers):
            layer = self.polygon_layers[index]
            fields = [field.name() for field in layer.fields()]
            self.combo_node_field.addItems(fields)

    def get_configuration(self):
        """Retorna la configuración seleccionada por el usuario."""
        selected_layer_idx = self.combo_node_layer.currentIndex()
        node_layer = self.polygon_layers[selected_layer_idx] if selected_layer_idx >= 0 else None
        
        return {
            "node_layer": node_layer,
            "node_field": self.combo_node_field.currentText(),
            "overwrite": self.chk_overwrite.isChecked()
        }


class NodeAssignerProcessor:
    """Encapsula la lógica de procesamiento espacial y asignación de atributos."""
    def __init__(self, iface: QgisInterface):
        self.iface = iface
        self.CONTINUE = True

    def log_message(self, message: str, level=Qgis.Info):
        print(f"[NodeAssigner] {message}")
        if level in [Qgis.Warning, Qgis.Critical]:
            self.iface.messageBar().pushMessage("Error de Asignación", message, level=level, duration=7)
        elif level == Qgis.Success:
            self.iface.messageBar().pushMessage("Asignador de Nodos", message, level=level, duration=5)

    def run(self):
        # 1. Obtener capas seleccionadas en el panel de QGIS
        selected_layers = [l for l in self.iface.layerTreeView().selectedLayers() if isinstance(l, QgsVectorLayer)]
        
        if not selected_layers:
            self.log_message("Por favor, seleccione al menos una capa vectorial en el panel de QGIS.", Qgis.Critical)
            return

        # 2. Mostrar la ventana de configuración
        dialog = NodeAssignerDialog(selected_layers)
        if dialog.exec_() != QDialog.Accepted:
            self.log_message("Proceso cancelado por el usuario.", Qgis.Warning)
            return

        config = dialog.get_configuration()
        node_layer = config["node_layer"]
        node_field = config["node_field"]
        overwrite = config["overwrite"]

        if not node_layer or not node_field:
            self.log_message("Debe seleccionar una capa de nodos y un campo válidos.", Qgis.Critical)
            return

        # 3. Validar CRS
        node_crs = node_layer.crs()
        for layer in selected_layers:
            if layer.crs() != node_crs:
                self.log_message(f"La capa '{layer.name()}' no coincide en CRS con la capa de nodos. Abortando.", Qgis.Critical)
                return

        # 4. Construir Índice Espacial de la capa de nodos para máxima velocidad
        self.log_message("Construyendo índice espacial de nodos...", Qgis.Info)
        spatial_index = QgsSpatialIndex()
        node_features_map = {}
        
        for feat in node_layer.getFeatures():
            spatial_index.addFeature(feat)
            node_features_map[feat.id()] = feat

        # 5. Iterar sobre las capas seleccionadas para asignar el nodo
        field_name = node_field  # Usamos el mismo nombre de campo de los límites

        for layer in selected_layers:
            self.log_message(f"Procesando capa: {layer.name()}", Qgis.Info)
            
            # Verificar o crear el campo en la capa destino
            field_idx = layer.fields().indexOf(field_name)
            layer.startEditing()
            
            if field_idx == -1:
                from qgis.PyQt.QtCore import QVariant
                from qgis.core import QgsField
                layer.addAttribute(QgsField(field_name, QVariant.String))
                layer.updateFields()
                field_idx = layer.fields().indexOf(field_name)

            # Iterar sobre las entidades de la capa
            for feat in layer.getFeatures():
                geom = feat.geometry()
                if geom.isEmpty() or geom.isNull():
                    continue

                # Si no se debe sobrescribir y ya tiene valor válido, saltar
                current_val = feat.attribute(field_idx)
                if not overwrite and current_val and current_val != "SIN_NODO":
                    continue

                assigned_node = "SIN_NODO"
                
                # Determinar la geometría de evaluación según el tipo
                g_type = geom.type()
                if g_type == QgsWkbTypes.LineGeometry:
                    # Para líneas, calcular su punto medio como representante espacial
                    eval_geom = geom.interpolate(geom.length() / 2.0)
                    if eval_geom.isEmpty() or eval_geom.isNull():
                        eval_geom = geom
                else:
                    eval_geom = geom

                # Búsqueda espacial rápida usando el índice con eval_geom
                candidate_ids = spatial_index.intersects(eval_geom.boundingBox())
                
                if candidate_ids:
                    max_intersect_area = 0.0
                    best_node = None
                    
                    for fid in candidate_ids:
                        node_feat = node_features_map[fid]
                        node_geom = node_feat.geometry()
                        
                        if eval_geom.intersects(node_geom):
                            if g_type == QgsWkbTypes.PointGeometry or g_type == QgsWkbTypes.LineGeometry:
                                # Para puntos y líneas (mediante su punto medio), con la intersección basta
                                best_node = node_feat.attribute(node_field)
                                break
                            else:
                                # Para polígonos, evaluamos área de intersección
                                intersection = eval_geom.intersection(node_geom)
                                if not intersection.isEmpty():
                                    area = intersection.area()
                                    if area > max_intersect_area:
                                        max_intersect_area = area
                                        best_node = node_feat.attribute(node_field)

                    if best_node:
                        assigned_node = str(best_node)

                # Asignar el valor al atributo
                layer.changeAttributeValue(feat.id(), field_idx, assigned_node)

            # Guardar cambios de la capa
            layer.commitChanges()

        self.log_message("¡Asignación de nodos completada con éxito!", Qgis.Success)

# Ejecutar el script directamente en QGIS
processor = NodeAssignerProcessor(iface)
processor.run()