"""Display explicit commercial-use declarations from dataset manifests."""

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class CommercialUse:
    allowed: bool | None
    manifest: Path
    licence: str = ""
    note: str = ""

    @property
    def label(self):
        if self.allowed is False:
            return "NON-COMMERCIAL"
        if self.allowed is True:
            return "commercial: yes (catalog)"
        return "commercial: unknown"


def read_commercial_use(configuration):
    """Use the manifest beside the defining YAML, including required configs.

    Missing, malformed, or non-boolean declarations remain unknown. This displays
    catalog metadata; it does not infer permissions from a licence name.
    """
    manifest = Path(configuration).parent / "manifest.yaml"
    if not manifest.exists() and manifest.with_suffix(".yml").exists():
        manifest = manifest.with_suffix(".yml")
    try:
        document = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        return CommercialUse(None, manifest, note=str(error))
    if not isinstance(document, dict):
        return CommercialUse(None, manifest, note="Expected a manifest mapping.")
    licence = document.get("licence", document.get("license", {}))
    if not isinstance(licence, dict):
        return CommercialUse(None, manifest, note="No licence mapping.")
    value = licence.get("commercial_use")
    allowed = value if isinstance(value, bool) else None
    return CommercialUse(allowed, manifest, str(licence.get("name") or ""))
