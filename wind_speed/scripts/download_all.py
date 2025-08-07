import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from download_utils import download_files_from_txt

if __name__ == '__main__':
    txt_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/subset_M2I3NVASM_5.12.4_20250612_172231_.txt'))
    save_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data'))
    download_files_from_txt(txt_path, save_dir) 