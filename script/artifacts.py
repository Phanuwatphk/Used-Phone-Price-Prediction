"""One metadata.json per output folder; datasets and original raw files stay separate."""
import hashlib
import json
from pathlib import Path

SECTIONS = {
    'summary.json':'summary', 'run_metadata.json':'provenance', 'validation.json':'validation',
    'output_hashes.json':'hashes', 'rules.json':'rules', 'config.json':'config',
    'selection.json':'selection', 'folds.json':'folds', 'split_summary.json':'split',
    'workflow_validation.json':'workflow_validation', 'report_refresh.json':'report_refresh',
    'tuning_review.json':'tuning_review', 'experiment_status.json':'experiment_status',
    'schema.json':'schema', 'policy.json':'policy', 'iphone_model_names.json':'model_catalog',
    'progress.json':'progress',
    'report.md':'report_text', 'summary.md':'summary_text',
}


def read_metadata(folder, section):
    folder = Path(folder)
    path = folder / 'metadata.json'
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        if section in data:
            return data[section]
    # Read old snapshots without rewriting the originals.
    name = next(name for name, key in SECTIONS.items() if key == section)
    text = (folder / name).read_text(encoding='utf-8')
    return text if name.endswith('.md') else json.loads(text)


def has_metadata(folder, section):
    try:
        read_metadata(folder, section)
        return True
    except (FileNotFoundError, KeyError):
        return False


def write_metadata(folder, section, value, *, newline=True):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'metadata.json'
    data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    data[section] = value
    formats = data.get('_formats', {})
    if newline:
        formats.pop(section, None)
    else:
        formats[section] = {'newline':False}
    if formats:
        data['_formats'] = formats
    else:
        data.pop('_formats', None)
    temporary = folder / 'metadata.tmp.json'
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def write_metadata_bytes(folder, section, content):
    """Keep historical serialization so original section checksums remain verifiable."""
    value = json.loads(content)
    newline = content.endswith(b'\n')
    expected = (json.dumps(value, ensure_ascii=False, indent=2) + ('\n' if newline else '')).encode()
    write_metadata(folder, section, value, newline=newline)
    if expected != content:
        path = Path(folder) / 'metadata.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data.setdefault('_formats', {})[section] = {'original': content.decode('utf-8')}
        temporary = path.with_name('metadata.tmp.json')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        temporary.replace(path)


def metadata_bytes(folder, section):
    folder = Path(folder)
    path = folder / 'metadata.json'
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
        if section in data:
            if section in ('report_text','summary_text'):
                return data[section].encode('utf-8')
            original = data.get('_formats', {}).get(section, {}).get('original')
            if original is not None:
                return original.encode('utf-8')
            newline = data.get('_formats', {}).get(section, {}).get('newline', True)
            return (json.dumps(data[section], ensure_ascii=False, indent=2) + ('\n' if newline else '')).encode()
    name = next(name for name, key in SECTIONS.items() if key == section)
    return (folder / name).read_bytes()


def metadata_sha(folder, section):
    return hashlib.sha256(metadata_bytes(folder, section)).hexdigest()


def collect_output_hashes(folder):
    folder = Path(folder)
    result = {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(folder.rglob('*')) if p.is_file()
              and p.name not in ('metadata.json','metadata.tmp.json','progress.json','output_hashes.json')}
    path = folder / 'metadata.json'
    if path.exists():
        for section in json.loads(path.read_text(encoding='utf-8')):
            if section not in ('hashes','progress','_formats'):
                result['metadata.json#' + section] = metadata_sha(folder, section)
    return result


def reference_bytes(reference):
    """Read a file or an explicit metadata.json#section reference."""
    name, separator, section = str(reference).partition('#')
    if not separator:
        return Path(name).read_bytes()
    if Path(name).name == 'metadata.json':
        return metadata_bytes(Path(name).parent, section)
    value = json.loads(Path(name).read_text(encoding='utf-8'))[section]
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def reference_json(reference):
    return json.loads(reference_bytes(reference))


def reference_sha(reference):
    return hashlib.sha256(reference_bytes(reference)).hexdigest()
