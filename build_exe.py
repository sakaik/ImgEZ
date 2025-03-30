import os
import shutil
import subprocess
from datetime import datetime
import time

def create_version_info():
    """バージョン情報ファイルを作成"""
    version_file = 'version_info.txt'
    with open(version_file, 'w', encoding='utf-8') as f:
        f.write(f'VSVersionInfo(\n')
        f.write(f'  ffi=FixedFileInfo(\n')
        f.write(f'    filevers=(1, 0, 0, 0),\n')
        f.write(f'    prodvers=(1, 0, 0, 0),\n')
        f.write(f'    mask=0x3f,\n')
        f.write(f'    flags=0x0,\n')
        f.write(f'    OS=0x40004,\n')
        f.write(f'    fileType=0x1,\n')
        f.write(f'    subtype=0x0,\n')
        f.write(f'    date=(0, 0)\n')
        f.write(f'    ),\n')
        f.write(f'  kids=[\n')
        f.write(f'    StringFileInfo(\n')
        f.write(f'      [\n')
        f.write(f'      StringTable(\n')
        f.write(f'        u\'040904B0\',\n')
        f.write(f'        [StringStruct(u\'FileDescription\', u\'ImgEZ Image Trimming Tool\'),\n')
        f.write(f'         StringStruct(u\'FileVersion\', u\'1.0.0\'),\n')
        f.write(f'         StringStruct(u\'InternalName\', u\'ImgEZ\'),\n')
        f.write(f'         StringStruct(u\'LegalCopyright\', u\'Copyright (c) 2024\'),\n')
        f.write(f'         StringStruct(u\'OriginalFilename\', u\'ImgEZ.exe\'),\n')
        f.write(f'         StringStruct(u\'ProductName\', u\'ImgEZ\'),\n')
        f.write(f'         StringStruct(u\'ProductVersion\', u\'1.0.0\')])\n')
        f.write(f'      ]), \n')
        f.write(f'    VarFileInfo([VarStruct(u\'Translation\', [1033, 1200])])\n')
        f.write(f'  ]\n')
        f.write(f')')
    return version_file

def safe_remove(path, retries=3, delay=1.0):
    """安全にファイルやディレクトリを削除する"""
    for i in range(retries):
        try:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            return True
        except (PermissionError, OSError) as e:
            if i == retries - 1:  # 最後の試行
                print(f"警告: {path} の削除に失敗しました: {e}")
                return False
            time.sleep(delay)
    return False

def build_exe():
    """EXEファイルをビルド"""
    # releaseディレクトリを作成
    release_dir = 'release'
    if not os.path.exists(release_dir):
        os.makedirs(release_dir)

    # 既存の一時ファイルを削除
    print('既存の一時ファイルを削除中...')
    for path in ['build', 'dist', 'ImgEZ.spec', 'version_info.txt']:
        if os.path.exists(path):
            safe_remove(path)

    # バージョン情報ファイルを作成
    version_file = create_version_info()

    # PyInstallerのコマンドを構築
    cmd = [
        'pyinstaller',
        '--clean',
        '--windowed',
        '--onefile',
        '--icon=src/icons/ImgEZ_icon.ico',  # src/iconsディレクトリ内のアイコンファイルを使用
        f'--version-file={version_file}',
        '--name=ImgEZ',
        '--add-data=src/icons;icons',  # アイコンフォルダを含める
        'src/ImgEZ.py'
    ]

    # EXEファイルをビルド
    subprocess.run(cmd, check=True)

    # ビルドされたEXEファイルをreleaseディレクトリに移動
    exe_path = os.path.join('dist', 'ImgEZ.exe')
    if os.path.exists(exe_path):
        # シンプルな出力ファイル名
        release_filename = 'ImgEZ.exe'
        release_path = os.path.join(release_dir, release_filename)
        # 既存のファイルがある場合は削除
        if os.path.exists(release_path):
            safe_remove(release_path)
        shutil.move(exe_path, release_path)
        print(f'EXEファイルを作成しました: {release_path}')

    # 一時ファイルとディレクトリを削除
    print('一時ファイルを削除中...')
    if os.path.exists(version_file):
        safe_remove(version_file)
    if os.path.exists('build'):
        safe_remove('build')
    if os.path.exists('dist'):
        safe_remove('dist')
    if os.path.exists('ImgEZ.spec'):
        safe_remove('ImgEZ.spec')
    print('ビルド完了')

if __name__ == '__main__':
    build_exe() 