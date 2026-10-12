# -*- coding: utf-8 -*-
import io,os,zipfile,shutil,glob,copy,json
from lxml import etree
HP='http://www.hancom.co.kr/hwpml/2011/paragraph'
def L(e): return etree.QName(e).localname
def q(tag): return '{%s}%s'%(HP,tag)
SRC='renum.hwpx'   # already renumbered
BASE='toc'
if os.path.exists(BASE): shutil.rmtree(BASE)
os.makedirs(BASE)
with zipfile.ZipFile(SRC) as z: z.extractall(BASE)
FP=max(glob.glob(BASE+'/Contents/section*.xml'),key=lambda f:os.path.getsize(f))
t=etree.parse(FP); sec=[e for e in t.iter() if L(e)=='sec'][0]
def pt(p): return ''.join((e.text or '') for run in p.findall('{*}run') for e in run if L(e)=='t')
kids=[p for p in sec if L(p)=='p']
records=json.load(io.open('renum_records.json',encoding='utf-8'))

# templates
wrapper_p=None
for p in kids:
    tb=p.find('.//'+q('tbl'))
    if tb is not None:
        st=''.join((e.text or '') for e in tb.iter() if L(e)=='t')
        if '국가' in st and '논문수' in st and '점유율' in st: wrapper_p=p; break
t4tbl=wrapper_p.find('.//'+q('tbl'))
tr0=t4tbl.findall(q('tr'))[0]; tr1=t4tbl.findall(q('tr'))[1]
data_tc_tpl=copy.deepcopy(tr1.findall(q('tc'))[0])
# heading templates
maj_tpl=None; sub_tpl=None
for p in kids:
    tx=pt(p).strip()
    if maj_tpl is None and tx.startswith('나') and p.get('paraPrIDRef')=='17': maj_tpl=copy.deepcopy(p)
    if sub_tpl is None and p.get('paraPrIDRef')=='20' and tx.startswith('1)'): sub_tpl=copy.deepcopy(p)
assert maj_tpl is not None and sub_tpl is not None

maxid=0; maxz=0
for e in sec.iter():
    v=e.get('id');  maxid=max(maxid,int(v)) if v and v.isdigit() else maxid
    z=e.get('zOrder'); maxz=max(maxz,int(z)) if z and z.lstrip('-').isdigit() else maxz
idc=[maxid+3000]; zc=[maxz+10]
def newid(): idc[0]+=1; return str(idc[0])
def newz(): zc[0]+=1; return str(zc[0])
C_NO=8500; C_TI=32000; C_PG=7758; TOTW=C_NO+C_TI+C_PG
def set_run_text(container,text):
    runs=container.findall('.//'+q('run'));
    if not runs: return
    r0=runs[0]; ts=[x for x in r0 if L(x)=='t']
    if ts:
        ts[0].text=text
        for x in ts[1:]: x.text=''
    else: etree.SubElement(r0,q('t')).text=text
    for rx in runs[1:]:
        for x in rx:
            if L(x)=='t': x.text=''
def mk_tc(text,colAddr,rowAddr,bf,charPr,paraPr,width,height,header):
    tc=copy.deepcopy(data_tc_tpl)
    tc.set('borderFillIDRef',bf); tc.set('header',header)
    sub=tc.find(q('subList')); ps=sub.findall(q('p')); p0=ps[0]
    for e in ps[1:]: sub.remove(e)
    p0.set('paraPrIDRef',paraPr)
    set_run_text(p0,text)
    for lsa in p0.findall('.//'+q('linesegarray')): lsa.getparent().remove(lsa)
    tc.find(q('cellAddr')).set('colAddr',str(colAddr)); tc.find(q('cellAddr')).set('rowAddr',str(rowAddr))
    cs=tc.find(q('cellSpan')); cs.set('colSpan','1'); cs.set('rowSpan','1')
    sz=tc.find(q('cellSz')); sz.set('width',str(width)); sz.set('height',str(height))
    cm=tc.find(q('cellMargin'))
    if cm is not None: cm.set('top','30'); cm.set('bottom','30')
    return tc
def build_tbl(rows, caption_text):
    nt=copy.deepcopy(t4tbl)
    nt.set('id',newid()); nt.set('zOrder',newz())
    nt.set('numberingType','NONE'); nt.set('borderFillIDRef','3'); nt.set('colCnt','3'); nt.set('noAdjust','0')
    for tr in nt.findall(q('tr')): nt.remove(tr)
    cap=nt.find(q('caption'))
    if cap is not None:
        set_run_text(cap, caption_text)
        for lsa in cap.findall('.//'+q('linesegarray')): lsa.getparent().remove(lsa)
    nt.set('rowCnt',str(1+len(rows)))
    RH=800
    sz=nt.find(q('sz'))
    if sz is not None: sz.set('width',str(TOTW)); sz.set('height',str(RH*(len(rows)+1)))
    trh=copy.deepcopy(tr0)
    for tc in trh.findall(q('tc')): trh.remove(tc)
    trh.append(mk_tc('번호',0,0,'16','37','21',C_NO,RH,'1'))
    trh.append(mk_tc('제목',1,0,'16','37','21',C_TI,RH,'1'))
    trh.append(mk_tc('페이지',2,0,'16','37','21',C_PG,RH,'1'))
    nt.append(trh)
    r=1
    for lab,title,pg in rows:
        tr=copy.deepcopy(tr1)
        for tc in tr.findall(q('tc')): tr.remove(tc)
        tr.append(mk_tc(lab,0,r,'17','38','21',C_NO,RH,'0'))
        tr.append(mk_tc(title,1,r,'17','38','14',C_TI,RH,'0'))
        tr.append(mk_tc(pg,2,r,'17','38','21',C_PG,RH,'0'))
        nt.append(tr); r+=1
    return nt
def make_tbl_para(nt):
    wp=copy.deepcopy(wrapper_p)
    old=wp.find('.//'+q('tbl')); old.getparent().replace(old,nt)
    for lsa in wp.findall('.//'+q('linesegarray')): lsa.getparent().remove(lsa)
    return wp
def make_heading(tpl,text,pb=False):
    hp=copy.deepcopy(tpl); set_run_text(hp,text)
    if pb: hp.set('pageBreak','1')
    for lsa in hp.findall('.//'+q('linesegarray')): lsa.getparent().remove(lsa)
    return hp

tbl_rows=[[r[1],r[2],'-'] for r in records if r[0]=='표']
fig_rows=[[r[1],r[2],'-'] for r in records if r[0]=='그림']
tblpara=make_tbl_para(build_tbl(tbl_rows,'〈표 목차〉'))
tblpara.set('pageBreak','1')
figpara=make_tbl_para(build_tbl(fig_rows,'〈그림 목차〉'))
figpara.set('pageBreak','1')
block=[tblpara,figpara]

# Append to the END of section0 (the 참고목차 front-matter section), so the TOC
# renders right after the reference-TOC and before the body section1.
S0=BASE+'/Contents/section0.xml'
t0=etree.parse(S0); sec0=[e for e in t0.iter() if L(e)=='sec'][0]
for e in block: sec0.append(e)
for lsa in list(t0.iter(q('linesegarray'))): lsa.getparent().remove(lsa)
t0.write(S0,xml_declaration=True,encoding='UTF-8',standalone=True)
# section1 (FP) is left as the already-renumbered content (no changes here)
out='toc.hwpx'
if os.path.exists(out): os.remove(out)
zf=zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED)
zf.writestr(zipfile.ZipInfo('mimetype'),open(BASE+'/mimetype','rb').read(),zipfile.ZIP_STORED)
for root,_,files in os.walk(BASE):
    for f in files:
        full=os.path.join(root,f); rel=os.path.relpath(full,BASE).replace(os.sep,'/')
        if rel!='mimetype': zf.write(full,rel,zipfile.ZIP_DEFLATED)
zf.close()
print('표 rows',len(tbl_rows),'그림 rows',len(fig_rows),'| packed',os.path.getsize(out))
