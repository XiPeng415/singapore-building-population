"""Retrieve missing fixed-year SingStat snapshots; existing source files are preserved."""
import hashlib
import json
from pathlib import Path
import zipfile
import requests
from project_paths import SOURCES

def main():
    manifest=json.loads((SOURCES/'manifest.json').read_text(encoding='utf-8'))
    for row in manifest:
        path=SOURCES/row['file']
        if not path.exists():
            response=requests.get(row['url'],timeout=45)
            response.raise_for_status()
            path.write_bytes(response.content)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=row['sha256']:
            raise ValueError(f'Source snapshot differs from bundled manifest: {path.name}')
        if path.suffix=='.zip':
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    entry=Path(name)
                    if name.endswith('/') or '__MACOSX' in name or entry.name.startswith('.'):
                        continue
                    assert not entry.is_absolute() and '..' not in entry.parts
                    target=SOURCES/entry.name
                    if not target.exists():target.write_bytes(z.read(name))
        print('SOURCE',path.name,'verified',flush=True)

if __name__=='__main__':main()
