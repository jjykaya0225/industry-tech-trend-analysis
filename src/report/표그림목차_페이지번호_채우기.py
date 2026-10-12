# -*- coding: utf-8 -*-
import io,os,zipfile,glob,re,json
import fitz
from lxml import etree
HP='http://www.hancom.co.kr/hwpml/2011/paragraph'
def L(e): return etree.QName(e).localname
def q(tag): return '{%s}%s'%(HP,tag)
BASE='toc'   # extraction that has the TOC (section0 modified)
# 1) read pages from toc.pdf (layout WITH toc). body starts after toc pages.
d=fitz.open('toc.pdf')
NP=d.page_count
page_txt=[d[i].get_text() for i in range(NP)]
# find toc pages (contain '표 목차'/'그림 목차' caption) to exclude
toc_pages=set()
for i,tx in enumerate(page_txt):
    if '표 목차' in tx or '그림 목차' in tx: toc_pages.add(i)
BODY_START=max(toc_pages)+1 if toc_pages else 0
def find_page(label):
    # label like '표 Ⅱ-1' or '그림 Ⅱ-1'; match with non-digit boundary; search body pages
    pat=re.compile(re.escape(label)+r'(?!\d)')
    for i in range(BODY_START, NP):
        if pat.search(page_txt[i]): return i+1
    # fallback: search all pages after toc
    for i in range(NP):
        if i in toc_pages: continue
        if pat.search(page_txt[i]): return i+1
    return None
records=json.load(io.open('renum_records.json',encoding='utf-8'))
pagemap={}
for typ,lab,title in records:
    pagemap[lab]=find_page(lab)
missing=[k for k,v in pagemap.items() if v is None]
print('body_start page',BODY_START+1,'| mapped',sum(1 for v in pagemap.values() if v),'| missing',missing[:5],len(missing))

# 2) fill 페이지 cells in section0.xml toc tables
S0=BASE+'/Contents/section0.xml'
t0=etree.parse(S0); sec0=[e for e in t0.iter() if L(e)=='sec'][0]
def celltext(tc): return ' '.join(''.join((x.text or '') for x in p.iter() if L(x)=='t') for p in tc.iter(q('p'))).strip()
def set_cell(tc,text):
    runs=tc.findall('.//'+q('run')); r0=runs[0]
    ts=[x for x in r0 if L(x)=='t']
    if ts:
        ts[0].text=text
        for x in ts[1:]: x.text=''
    else: etree.SubElement(r0,q('t')).text=text
    for lsa in tc.findall('.//'+q('linesegarray')): lsa.getparent().remove(lsa)
filled=0
for tb in sec0.iter(q('tbl')):
    captxt=''.join((x.text or '') for x in (tb.find(q('caption')).iter() if tb.find(q('caption')) is not None else []) if L(x)=='t')
    if '목차' not in captxt: continue
    trs=tb.findall(q('tr'))
    for tr in trs[1:]:
        tcs=tr.findall(q('tc'))
        lab=celltext(tcs[0])
        pg=pagemap.get(lab)
        if pg is not None:
            set_cell(tcs[2], str(pg)); filled+=1
for lsa in list(t0.iter(q('linesegarray'))): lsa.getparent().remove(lsa)
t0.write(S0,xml_declaration=True,encoding='UTF-8',standalone=True)
out='toc_filled.hwpx'
if os.path.exists(out): os.remove(out)
zf=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED)
zf.writestr(zipfile.ZipInfo('mimetype'),open(BASE+'/mimetype','rb').read(),zipfile.ZIP_STORED)
for root,_,files in os.walk(BASE):
    for f in files:
        full=os.path.join(root,f); rel=os.path.relpath(full,BASE).replace(os.sep,'/')
        if rel!='mimetype': zf.write(full,rel,zipfile.ZIP_DEFLATED)
zf.close()
print('filled cells',filled,'| packed',os.path.getsize(out))
