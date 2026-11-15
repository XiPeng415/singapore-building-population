"""Package-relative paths shared by the standalone population workflow."""
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
CONFIG_PATH = PACKAGE / 'config' / 'paths.json'
CONFIG = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
BUILDINGS = PACKAGE / CONFIG['buildings']
BOUNDARY = PACKAGE / CONFIG['subzones']
MASK = PACKAGE / CONFIG['mainland_mask']
SOURCES = PACKAGE / CONFIG['population_sources']
REFERENCE = PACKAGE / CONFIG['reference_results']
FIGURES = PACKAGE / CONFIG['research_figures']
