import os
import requests
from tqdm import tqdm

def download_files_from_txt(txt_path: str, save_dir: str):
    """
    批量下载txt文件中所有链接到指定文件夹。
    :param txt_path: 包含下载链接的txt文件路径
    :param save_dir: 下载文件保存的文件夹
    """
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    with open(txt_path, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and line.startswith('http')]
    session = requests.Session()
    for url in tqdm(urls, desc='Downloading files'):
        filename = url.split('LABEL=')[-1].split('&')[0] if 'LABEL=' in url else url.split('/')[-1]
        save_path = os.path.join(save_dir, filename)
        if os.path.exists(save_path):
            continue  # 已存在则跳过
        try:
            with session.get(url, stream=True, timeout=60, allow_redirects=True) as r:
                r.raise_for_status()
                with open(save_path, 'wb') as f_out:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f_out.write(chunk)
        except Exception as e:
            print(f"下载失败: {url}\n错误: {e}") 