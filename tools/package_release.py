"""Create the portable Windows ZIP and SHA256 manifest from a verified build."""

import hashlib
from pathlib import Path
import shutil
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.0'


def main():
    executable = ROOT/'讲解石生成器.exe'
    instructions = ROOT/'使用说明.txt'
    for path in (executable, instructions):
        if not path.is_file():
            raise SystemExit(f'Missing required release file: {path.name}')
    output = ROOT/'releases'/f'v{VERSION}'
    output.mkdir(parents=True, exist_ok=True)
    standalone = output/f'generate-Mr.chiang-v{VERSION}-windows-x64.exe'
    shutil.copy2(executable, standalone)
    archive = output/f'generate-Mr.chiang-v{VERSION}-windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        bundle.write(executable, executable.name)
        bundle.write(instructions, instructions.name)
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise SystemExit('ZIP verification failed.')
    lines = []
    for path in (standalone, archive):
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        lines.append(f'{digest}  {path.name}\n')
    manifest = output/'SHA256SUMS.txt'
    manifest.write_text(''.join(lines), encoding='utf-8')
    print(f'Portable ZIP: {archive}')
    print(f'Standalone executable: {standalone}')
    print(f'SHA256 manifest: {manifest}')


if __name__ == '__main__':
    main()
