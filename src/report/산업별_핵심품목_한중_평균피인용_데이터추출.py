# -*- coding: utf-8 -*-
import io,os,zipfile,shutil,glob,json,re
from lxml import etree
def L(e): return etree.QName(e).localname
q=lambda tag:'{http://www.hancom.co.kr/hwpml/2011/paragraph}'+tag
def subtext(e): return ''.join((x.text or '') for x in e.iter() if L(x)=='t')
def celltext(tc): return ' '.join(''.join((x.text or '') for x in p.iter() if L(x)=='t') for p in tc.iter(q('p'))).strip()
def pt(p): return ''.join((x.text or '') for run in p.findall('{*}run') for x in run if L(x)=='t')
def tonum(s):
    s=(s or '').replace(',','').strip()
    try: return float(s)
    except: return 0.0
def load(src):
    tmp='xd_%d'%abs(hash(src))
    if os.path.exists(tmp): shutil.rmtree(tmp)
    os.makedirs(tmp)
    with zipfile.ZipFile(src) as z: z.extractall(tmp)
    FP=max(glob.glob(tmp+'/Contents/section*.xml'),key=os.path.getsize)
    t=etree.parse(FP); return [e for e in t.iter() if L(e)=='sec'][0]
def rows_of(tb):
    res={}
    for tr in tb.findall(q('tr')):
        tcs=tr.findall(q('tc'))
        if tcs: res[celltext(tcs[0])]=[celltext(x) for x in tcs[1:]]
    return res
def title_prev(kids,i):
    for j in range(i-1,-1,-1):
        tx=pt(kids[j]).strip()
        if tx: return tx
    return ''

def extract(src, mode):
    sec=load(src); kids=[p for p in sec if L(p)=='p']
    items=[]; kr={}; cn={}
    EXCL=['주요국별','로봇산업','전방산업','후방산업','이차전지산업','본산업','내부 가치사슬']
    # semi: title stored as preceding paragraph (1 table/para) -> iterate paragraphs
    # robot/batt: titles are <caption> (may pack several tables per paragraph) -> iterate all tbls
    if mode=='semi':
        tbls=[(p.find('.//'+q('tbl')), i) for i,p in enumerate(kids) if p.find('.//'+q('tbl')) is not None]
    else:
        tbls=[(tb,None) for tb in sec.iter(q('tbl'))]
    for tb,i in tbls:
        trs=tb.findall(q('tr'))
        if not trs: continue
        hdr=[celltext(x) for x in trs[0].findall(q('tc'))]
        if not any('2022' in h for h in hdr): continue
        r=rows_of(tb)
        if '한국' not in r or '중국' not in r: continue
        # title
        cap=tb.find(q('caption'))
        title=subtext(cap).strip() if cap is not None else (title_prev(kids,i) if i is not None else '')
        tail=title.split('>')[-1].strip()   # drop leading body text + <표 ..> tag
        if mode=='semi':
            if '논문 피인용 영향력' not in tail: continue
            name=tail.replace('논문 피인용 영향력','').strip().rstrip(',').strip()
        elif mode=='robot':
            if '평균 피인용' not in tail: continue
            name=tail.split('주요국별')[0].strip()
        elif mode=='batt':
            if '평균 피인용' not in tail: continue
            name=tail.split('국가별')[0].strip()
        BATT_EXCL=['이차전지산업','후방산업','전방산업','사용 후 배터리 순환이용']
        if not name or any(x in name for x in EXCL) or name in BATT_EXCL: continue
        if name in kr: continue  # dedup
        krv=[tonum(x) for x in r['한국'][:5]]
        cnv=[tonum(x) for x in r['중국'][:5]]
        if len(krv)<5 or len(cnv)<5: continue
        items.append(name); kr[name]=krv; cn[name]=cnv
    return {'items':items,'kr':kr,'cn':cn}

SRCS={
 '반도체':('C:/Users/remoteadmin/Desktop/CNL/CNL보고서_초안/반도체_최종(종합의견추가).hwpx','semi'),
 '로봇':('C:/Users/remoteadmin/Desktop/CNL/CNL보고서_초안/로봇산업_최종.hwpx','robot'),
 '이차전지':('C:/Users/remoteadmin/Desktop/CNL/CNL보고서_초안/이차전지_최종.hwpx','batt'),
}
summ=[]
for name,(src,mode) in SRCS.items():
    d=extract(src,mode)
    json.dump(d,io.open('data_%s.json'%name,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    summ.append('%s: %d 품목'%(name,len(d['items'])))
    summ.append('   items: '+' | '.join(d['items']))
    # sanity: first item 2022 values
    if d['items']:
        it=d['items'][0]
        summ.append('   %s 2022 한국=%s 중국=%s'%(it,d['kr'][it][0],d['cn'][it][0]))
io.open('extract_summary.txt','w',encoding='utf-8').write('\n'.join(summ))
print('\n'.join(summ))
