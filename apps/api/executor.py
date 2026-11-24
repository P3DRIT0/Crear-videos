from .storage import BlobStore, canonical


class ManualBriefExecutor:
    """Adaptador WORK. Termina dentro de la petición que solicita la ficha."""
    name = "manual-sync"

    def __init__(self, blobs: BlobStore):
        self.blobs = blobs

    def execute(self, brand: dict, campaign: dict) -> str:
        snapshot = {"version": 1, "brand": brand, "campaign": campaign}
        return self.blobs.save(canonical(snapshot))
