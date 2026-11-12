# Automatic Node Assigner by Overlap (PyQGIS)

Tool developed in Python using **PyQGIS** (for QGIS 3.34+) designed to automate the mass assignment of node attributes to vector layers (points, lines, and polygons) based on their spatial overlap or inclusion within node boundary polygons in telecommunications networks (FTTH).

---

## Main Features

- **Intuitive Graphical Interface (`NodeAssignerDialog`)**:
  - Automatic detection of all polygon vector layers loaded in the active QGIS project.
  - Dynamic population of available fields when selecting the node boundary layer.
  - Configurable option to overwrite or respect existing values (`SIN_NODO`).
- **Optimized Spatial Processing (`NodeAssignerProcessor`)**:
  - Pre-validation of the Coordinate Reference System (CRS) between selected layers and the node layer.
  - Use of spatial indices (`QgsSpatialIndex`) for optimal performance in large projects.
  - Adaptive handling according to geometry type:
    - **Points**: Evaluation by direct intersection.
    - **Lines**: Use of the midpoint (`interpolate`) as a spatial representative.
    - **Polygons**: Evaluation by maximum intersection area.
  - Automatic management of layer editing, field creation if they do not exist, and saving changes (`startEditing` / `commitChanges`).

---

## Code Structure

### 1. `NodeAssignerDialog`
Class inheriting from `QDialog` to manage user input parameters:
- Filters polygon layers using `QgsWkbTypes.PolygonGeometry`.
- Connects source layer selection with automatic field combo box update (`_update_fields_combo`).
- Returns a configuration dictionary via `get_configuration()`.

### 2. `NodeAssignerProcessor`
Class responsible for executing business logic and geospatial processing:
- Retrieves selected layers in the QGIS layer tree (`iface.layerTreeView().selectedLayers()`).
- Builds the spatial index of the node polygons.
- Iterates over geospatial features applying overlap rules and injecting the node value into the target field.

---

## System Requirements

- **QGIS**: Version 3.34 or higher.
- **Environment**: QGIS integrated Python console or processing script-based plugin.

---

## Usage

1. Select one or more vector layers (points, lines, or polygons) in the QGIS layer panel.
2. Run the `assign_by_overlap.py` script from the QGIS Python Editor.
3. In the dialog window:
   - Choose the polygon layer that defines the node boundaries or areas.
   - Select the field containing the node identifier/name.
   - Check or uncheck the overwrite option.
4. Click on **Run Assignment**.
