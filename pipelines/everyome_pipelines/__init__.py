"""Pipeline bundles for Everyome. Everyome finds them here and checks each against its pinned SHA-256."""
from pathlib import Path

BUNDLES = Path(__file__).resolve().parent / "bundles"
