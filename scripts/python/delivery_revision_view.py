"""Resolve an explicitly selected overlay without scanning immutable media."""
from pathlib import Path
import update_delivery_revision as updates


class View:
    def __init__(self, root, revision):
        self.root = root.resolve()
        updates.verify_binding(self.root)
        self.entries = {}
        for item in updates.chain(self.root, revision):
            for entry in item['changed_files']:
                self.entries.setdefault(entry['logical_path'].casefold(), entry)

    def path(self, logical):
        updates.safe(self.root, logical)
        entry = self.entries.get(logical.casefold())
        if entry is None:
            return updates.safe(self.root, logical)
        path = updates.safe(self.root, entry['physical_path'])
        if path.stat().st_size != entry['bytes'] or updates.sha(path) != entry['sha256']:
            raise ValueError('Revision file SHA/size mismatch')
        return path
