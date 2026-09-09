"""Study-area loading, geometry validation, and metric preparation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


SUPPORTED_EXTENSIONS = {".gpkg", ".shp", ".geojson", ".json"}
DEFAULT_METRIC_CRS = "EPSG:25831"


class GeoDependencyError(RuntimeError):
    """Raised when the geospatial runtime is not installed."""


@dataclass(frozen=True)
class StudyArea:
    """Validated study-area geometry and core metrics."""

    name: str
    source_path: Path
    input_crs: str
    metric_crs: str
    feature_count: int
    area_ha: float
    perimeter_m: float
    bounds: tuple[float, float, float, float]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    data: Any | None = None


@dataclass(frozen=True)
class PreparedStudyArea:
    """Study area prepared inside an EcoRadar project."""

    project_name: str
    project_root: Path
    study_area: StudyArea
    processed_path: Path
    metadata_path: Path


def _load_geopandas():
    try:
        import geopandas as gpd  # type: ignore
    except ModuleNotFoundError as exc:
        raise GeoDependencyError(
            "GeoPackage/SHP loading requires geospatial dependencies. "
            "Install the project with GIS dependencies first, for example: "
            "`pip install -e .` in an environment that can install geopandas, "
            "shapely, pyproj and pyogrio."
        ) from exc
    return gpd


def load_study_area(
    path: str | Path,
    name: str | None = None,
    metric_crs: str = DEFAULT_METRIC_CRS,
    repair_geometry: bool = False,
    layer: str | None = None,
) -> StudyArea:
    """Load a GeoPackage, Shapefile, or GeoJSON study area and compute metrics.

    Metrics are calculated in `metric_crs`, which defaults to ETRS89 / UTM zone 31N
    for Catalonia.
    """

    source_path = Path(path).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    extension = source_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported study-area format '{extension}'. "
            f"Supported formats: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    gpd = _load_geopandas()
    gdf = gpd.read_file(source_path, layer=layer)

    if gdf.empty:
        raise ValueError("Study-area layer is empty")
    if "geometry" not in gdf:
        raise ValueError("Study-area layer has no geometry column")
    if gdf.crs is None:
        raise ValueError("Study-area layer has no CRS. Define it before loading.")

    warnings: list[str] = []
    null_geometry_count = int(gdf.geometry.isna().sum())
    if null_geometry_count:
        raise ValueError(f"Study-area layer has {null_geometry_count} null geometries")

    invalid_mask = ~gdf.geometry.is_valid
    invalid_count = int(invalid_mask.sum())
    if invalid_count:
        if not repair_geometry:
            raise ValueError(
                f"Study-area layer has {invalid_count} invalid geometries. "
                "Run with repair_geometry=True or fix the source layer."
            )
        gdf = gdf.copy()
        gdf.loc[invalid_mask, "geometry"] = gdf.loc[invalid_mask, "geometry"].make_valid()
        warnings.append(f"Repaired {invalid_count} invalid geometries")

    input_crs = str(gdf.crs)
    metric_gdf = gdf.to_crs(metric_crs)

    union_geometry = _union_geometries(metric_gdf)
    area_ha = float(union_geometry.area / 10000)
    perimeter_m = float(union_geometry.length)
    bounds = tuple(float(value) for value in union_geometry.bounds)

    return StudyArea(
        name=name or source_path.stem,
        source_path=source_path,
        input_crs=input_crs,
        metric_crs=metric_crs,
        feature_count=int(len(gdf)),
        area_ha=area_ha,
        perimeter_m=perimeter_m,
        bounds=bounds,
        warnings=tuple(warnings),
        data=gdf,
    )


def prepare_study_area_project(
    source_path: str | Path,
    project_name: str = "Alinya",
    projects_root: str | Path = "projectes",
    metric_crs: str = DEFAULT_METRIC_CRS,
    repair_geometry: bool = False,
    layer: str | None = None,
    overwrite: bool = False,
    source_organization: str | None = None,
    source_url: str | None = None,
    source_license: str | None = None,
    provenance_status: str = "pending_verification",
) -> PreparedStudyArea:
    """Load, validate, reproject, save and document a project study area."""

    study_area = load_study_area(
        source_path,
        name=project_name,
        metric_crs=metric_crs,
        repair_geometry=repair_geometry,
        layer=layer,
    )
    if study_area.data is None:
        raise ValueError("Study area was loaded without geospatial data")

    project_root = Path(projects_root).resolve() / project_name
    processed_dir = project_root / "processed"
    metadata_dir = project_root / "metadata"
    raw_dir = project_root / "raw"

    for directory in (processed_dir, metadata_dir, raw_dir):
        directory.mkdir(parents=True, exist_ok=True)

    processed_path = processed_dir / "study_area.gpkg"
    metadata_path = metadata_dir / "study_area_metadata.json"

    if processed_path.exists() and not overwrite:
        raise FileExistsError(
            f"Processed study area already exists: {processed_path}. "
            "Use overwrite=True only for intentional replacement."
        )
    if metadata_path.exists() and not overwrite:
        raise FileExistsError(
            f"Study-area metadata already exists: {metadata_path}. "
            "Use overwrite=True only for intentional replacement."
        )

    clean_gdf = study_area.data.to_crs(metric_crs).copy()
    clean_gdf.to_file(processed_path, layer="study_area", driver="GPKG")

    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    metadata = {
        "project_name": project_name,
        "created_at": created_at,
        "source_path": str(study_area.source_path),
        "source_layer": layer,
        "source_organization": source_organization,
        "source_url": source_url,
        "source_license": source_license,
        "provenance_status": provenance_status,
        "processed_path": str(processed_path),
        "original_crs": study_area.input_crs,
        "final_crs": study_area.metric_crs,
        "feature_count": study_area.feature_count,
        "surface_ha": study_area.area_ha,
        "perimeter_m": study_area.perimeter_m,
        "bounds": study_area.bounds,
        "detected_errors": list(study_area.warnings),
        "external_data_downloaded": False,
        "indicators_calculated": False,
        "reports_created": False,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    return PreparedStudyArea(
        project_name=project_name,
        project_root=project_root,
        study_area=study_area,
        processed_path=processed_path,
        metadata_path=metadata_path,
    )


def _union_geometries(gdf: Any) -> Any:
    geometry = gdf.geometry
    if hasattr(geometry, "union_all"):
        return geometry.union_all()
    return geometry.unary_union
