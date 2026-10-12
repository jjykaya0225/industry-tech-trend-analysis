# -*- coding: utf-8 -*-
import io,os,zipfile,shutil,glob,re,json
from lxml import etree
HP='http://www.hancom.co.kr/hwpml/2011/paragraph'
def L(e): return etree.QName(e).localname
def q(tag): return '{%s}%s'%(HP,tag)
SRC='allx.hwpx'
BASE='renum'
if os.path.exists(BASE): shutil.rmtree(BASE)
os.makedirs(BASE)
with zipfile.ZipFile(SRC) as z: z.extractall(BASE)
FP=max(glob.glob(BASE+'/Contents/section*.xml'),key=lambda f:os.path.getsize(f))
t=etree.parse(FP); sec=[e for e in t.iter() if L(e)=='sec'][0]
def pt(p): return ''.join((e.text or '') for run in p.findall('{*}run') for e in run if L(e)=='t')
def subtext(e): return ''.join((x.text or '') for x in e.iter() if L(x)=='t')
def set_run_text(container, text):
    runs=container.findall('.//'+q('run'))
    if not runs: return
    r0=runs[0]; ts=[x for x in r0 if L(x)=='t']
    if ts:
        ts[0].text=text
        for x in ts[1:]: x.text=''
    else: etree.SubElement(r0,q('t')).text=text
    for rx in runs[1:]:
        for x in rx:
            if L(x)=='t': x.text=''
def strip_tprefix(s):
    m=re.match(r'^\s*[〈<]\s*표[^〉>]*[〉>]\s*', s); return s[m.end():].strip() if m else s.strip()
def strip_fprefix(s):
    m=re.match(r'^\s*\[\s*그림[^\]]*\]\s*', s); return s[m.end():].strip() if m else s.strip()
ROMAN={'나':'Ⅱ','다':'Ⅲ'}
chapter=None; tcnt={}; fcnt={}; records=[]
for p in [x for x in sec if L(x)=='p']:
    tx=pt(p).strip()
    if tx.startswith('나'): chapter='나'
    elif tx.startswith('다'): chapter='다'
    elif tx.startswith('라'): chapter=None
    tb=p.find('.//'+q('tbl'))
    if tb is not None and tb.get('numberingType')=='TABLE' and chapter in ROMAN:
        cap=tb.find(q('caption'))
        if cap is None: continue
        title=strip_tprefix(subtext(cap))
        n=tcnt.get(chapter,0)+1; tcnt[chapter]=n
        lab='표 %s-%d'%(ROMAN[chapter],n)
        set_run_text(cap,'〈%s〉 %s'%(lab,title)); records.append(('표',lab,title))
    elif tx.startswith('[그림') and chapter in ROMAN:
        title=strip_fprefix(tx)
        n=fcnt.get(chapter,0)+1; fcnt[chapter]=n
        lab='그림 %s-%d'%(ROMAN[chapter],n)
        set_run_text(p,'[%s] %s'%(lab,title)); records.append(('그림',lab,title))
for lsa in list(t.iter(q('linesegarray'))): lsa.getparent().remove(lsa)
t.write(FP,xml_declaration=True,encoding='UTF-8',standalone=True)
io.open('renum_records.json','w',encoding='utf-8').write(json.dumps(records,ensure_ascii=False,indent=1))
out='renum.hwpx'
if os.path.exists(out): os.remove(out)
zf=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED)
zf.writestr(zipfile.ZipInfo('mimetype'),open(BASE+'/mimetype','rb').read(),zipfile.ZIP_STORED)
for root,_,files in os.walk(BASE):
    for f in files:
        full=os.path.join(root,f); rel=os.path.relpath(full,BASE).replace(os.sep,'/')
        if rel!='mimetype': zf.write(full,rel,zipfile.ZIP_DEFLATED)
zf.close()
print('tables',tcnt,'figs',fcnt,'records',len(records))
