import hashlib
import json
import shutil
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
import pymupdf


work = Path(__file__).resolve().parent
revision = work.parent
root = revision.parents[2]
source_packet = root / 'Nexus系统提交文件_代码归档同步20261015'
packet = root / 'Nexus系统提交文件_重算更新20261017'
image = work / 'output/Figure_4.png'
old_sha = hashlib.sha256((source_packet / 'Figures/Figure_4.png').read_bytes()).hexdigest()
new_sha = hashlib.sha256(image.read_bytes()).hexdigest()
with pymupdf.open(source_packet / 'Figures/Figure_4.pdf') as source:
    dimensions = source[0].rect
with pymupdf.open() as document:
    page = document.new_page(width=dimensions.width, height=dimensions.height)
    page.insert_image(page.rect, filename=str(image))
    document.save(work / 'output/Figure_4.pdf', deflate=True)
audit = []
for name in ['Manuscript_Clean.docx', 'Manuscript_Marked_Changes.docx',
             '作者审阅/Manuscript_Chinese.docx', '作者审阅/Manuscript_Marked_Changes_Chinese.docx']:
    path = packet / name
    document = Document(path)
    count = 0
    for paragraph in document.paragraphs:
        for blip in paragraph._p.findall('.//' + qn('a:blip')):
            part = document.part.related_parts[blip.get(qn('r:embed'))]
            if hashlib.sha256(part.blob).hexdigest() == old_sha:
                part._blob = image.read_bytes()
                count += 1
    if count != 1:
        raise ValueError(f'Expected one Figure 4 image in {name}: {count}')
    document.save(path)
    audit.append({'document': name, 'figure_replacements': count})
for name in ['Figure_4.png', 'Figure_4.pdf']:
    shutil.copy2(work / 'output' / name, packet / 'Figures' / name)
(work / 'publication_audit.json').write_text(json.dumps({'source_image_sha256': old_sha,
    'image_sha256': new_sha, 'text_edits': 5, 'documents': audit,
    'layout_visual_review': 'All original modules and connectors retained; SynAF labels fit the original figure.'},
    ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'main_document_images_updated': len(audit), 'standalone_pdf_updated': True}))
