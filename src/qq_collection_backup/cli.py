from . import collection_export
from .app_common import main as run_app

def provider(folder):
    return [collection_export]
provider.names = ["collection.db"]

def main():
    run_app(provider, collection_only=True)
