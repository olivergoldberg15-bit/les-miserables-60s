"""License constrained CI downloads. No network requests happen on import."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request

MANIFEST = Path(__file__).with_name('assets.json')
PH = 'https://api.polyhaven.com'
GH = 'https://api.github.com/repos/microsoft/Microsoft-Rocketbox/contents/'
RAW = 'https://raw.githubusercontent.com/microsoft/Microsoft-Rocketbox/master/'


def request_json(url):
    print('[assets] GET', url, flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'lesmis-blender-film/1.0'})
    with urllib.request.urlopen(req, timeout=90) as response:
        return json.load(response)


def download(url, destination):
    destination = Path(destination)
    if destination.is_file() and destination.stat().st_size:
        return str(destination)
    print('[assets] DOWNLOAD', url, flush=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.part')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'lesmis-blender-film/1.0'})
        with urllib.request.urlopen(req, timeout=180) as response, temporary.open('wb') as out:
            import shutil
            shutil.copyfileobj(response, out)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return str(destination)


def list_clips(directory='Assets/Animations'):
    """List original repository clip URLs via the GitHub contents API."""
    entries = request_json(GH + urllib.parse.quote(directory, safe='/'))
    result = []
    for entry in entries:
        if entry['type'] == 'dir':
            result.extend(list_clips(entry['path']))
        elif entry['name'].lower().startswith('m_') and entry['name'].lower().endswith('.fbx'):
            result.append(entry)
    return result


def leaves(value, trail=()):
    if isinstance(value, dict):
        if 'url' in value:
            yield trail, value
        else:
            for key, child in value.items():
                yield from leaves(child, trail + (key,))


class Assets:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get('ASSET_DIR', 'build/assets')).resolve()
        self.manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        self.index_path = self.root / 'index.json'
        self.index = json.loads(self.index_path.read_text()) if self.index_path.exists() else {}

    def path(self, value):
        return str(self.root / value) if value else None

    def texture(self, key):
        return {k: self.path(v) for k, v in self.index['textures'][key].items()}

    def hdri(self, key):
        return self.path(self.index['hdris'][key])

    def model(self, key):
        return self.path(self.index.get('models', {}).get(key))

    def rocketbox(self, name):
        value = self.index['avatars'][self.manifest.get('avatar_aliases', {}).get(name, name)]
        return {k: self.path(v) for k, v in value.items()}

    def rocketbox_anim(self, clip):
        return self.path(self.index['clips'][clip])

    def font(self, key):
        return self.path(self.index['fonts'][key])

    def fetch(self, url, folder):
        filename = urllib.parse.unquote(urllib.parse.urlparse(url).path.rsplit('/', 1)[-1])
        relative = Path(folder) / filename
        download(url, self.root / relative)
        return relative.as_posix()

    def prepare(self, include_people=True):
        self.index = {k: {} for k in ('textures', 'hdris', 'models', 'avatars', 'clips', 'fonts')}
        self.index['resolved'] = {}
        for group, kind in (('textures', 'textures'), ('hdris', 'hdris'), ('models', 'models')):
            catalog = request_json(PH + '/assets?t=' + kind)
            for key, spec in self.manifest[group].items():
                if spec is None:
                    # Models are optional. Discover from the live catalog rather
                    # than inventing IDs; record null when no suitable model exists.
                    terms = self.manifest.get('model_search', {}).get(key, [key])
                    matches = sorted(asset_id for asset_id, info in catalog.items()
                                     if any(term.lower() in (asset_id + ' ' + info.get('name', '')).lower()
                                            for term in terms))
                    if not matches:
                        self.index[group][key] = None
                        continue
                    asset_id = matches[0]
                    spec = dict(id=asset_id, type='models', res='2k', license='CC0',
                                url='https://polyhaven.com/a/' + asset_id)
                asset_id = spec['id']
                if asset_id not in catalog:
                    raise ValueError(f'[assets] missing Poly Haven {kind} id {asset_id!r} for {key}')
                files = list(leaves(request_json(PH + '/files/' + asset_id)))
                self.index['resolved'][key] = spec
                def pick(channel, extensions):
                    candidates = [(trail, item) for trail, item in files
                                  if channel in trail and spec['res'] in trail
                                  and any(ext in trail for ext in extensions)]
                    if not candidates:
                        return None
                    trail, item = sorted(candidates, key=lambda x: '/'.join(x[0]))[0]
                    return self.fetch(item['url'], f'{group}/{asset_id}')
                if group == 'textures':
                    maps = {name: pick(channel, ('png', 'jpg', 'exr')) for name, channel in
                            [('albedo', 'diff'), ('normal', 'nor_gl'), ('roughness', 'rough'),
                             ('displacement', 'disp'), ('ao', 'ao')]}
                    for required in ('albedo', 'normal', 'roughness'):
                        if not maps[required]:
                            raise ValueError(f'[assets] {asset_id} lacks {required} at {spec["res"]}')
                    self.index[group][key] = maps
                else:
                    chosen = pick('hdri' if group == 'hdris' else 'blend', ('exr', 'hdr', 'blend'))
                    if group == 'models' and not chosen:
                        self.index[group][key] = None
                        continue
                    if not chosen:
                        raise ValueError(f'[assets] no downloadable file for {key}: {asset_id}')
                    if group == 'models':
                        # Fetch companion textures as well as the native model.
                        for trail, item in files:
                            if spec['res'] in trail and any(ext in trail for ext in ('jpg', 'png')):
                                self.fetch(item['url'], f'{group}/{asset_id}/textures')
                    self.index[group][key] = chosen
        if include_people:
            tree = request_json('https://api.github.com/repos/microsoft/Microsoft-Rocketbox/git/trees/master?recursive=1')
            if tree.get('truncated'):
                raise ValueError('[assets] Rocketbox tree truncated; cannot verify named assets')
            entries = tree['tree']
            for name, spec in self.manifest['avatars'].items():
                matches = [e['path'] for e in entries if e['path'].endswith('/Export/' + name + '.fbx')]
                if len(matches) != 1:
                    raise ValueError(f'[assets] named Rocketbox avatar {name} not uniquely available: {matches}')
                source = matches[0]
                base = source.rsplit('/Export/', 1)[0]
                fbx = self.fetch(RAW + urllib.parse.quote(source, safe='/'), 'avatars/' + name)
                for item in entries:
                    if item['type'] == 'blob' and item['path'].startswith(base + '/Textures/'):
                        relative = item['path'][len(base + '/Textures/'):]
                        destination = self.root / 'avatars' / name / 'Textures' / relative
                        download(RAW + urllib.parse.quote(item['path'], safe='/'), destination)
                self.index['avatars'][name] = {'fbx': fbx, 'textures': 'avatars/' + name + '/Textures'}
            clips = list_clips()
            for alias, candidates in self.manifest['clips'].items():
                match = next((item for name in candidates for item in clips if item['name'].lower() == name.lower()), None)
                if match is None:
                    raise ValueError(f'[assets] missing Rocketbox clip {alias}: {candidates}; use --list-clips')
                self.index['clips'][alias] = self.fetch(match['download_url'], 'clips')
        for key, spec in self.manifest['fonts'].items():
            self.index['fonts'][key] = self.fetch(spec['url'], 'fonts')
        self.index['manifest_sha256'] = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(self.index, indent=2), encoding='utf-8')
        return self


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--list-clips', action='store_true')
    parser.add_argument('--skip-people', action='store_true')
    args = parser.parse_args()
    if args.list_clips:
        print(json.dumps(list_clips(), indent=2))
    else:
        Assets().prepare(not args.skip_people)
