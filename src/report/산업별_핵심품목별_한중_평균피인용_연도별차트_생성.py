# -*- coding: utf-8 -*-
import json,io,os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import numpy as np
fp='C:/Windows/Fonts/malgun.ttf'; fpb='C:/Windows/Fonts/malgunbd.ttf'
plt.rcParams['font.family']=fm.FontProperties(fname=fp).get_name()
plt.rcParams['axes.unicode_minus']=False
KR='#29ABD4'; CN='#1F4E79'
OUT='out_charts'; os.makedirs(OUT,exist_ok=True)
def wrap2(s):
    s=s.replace(', ','·')
    if len(s)<=5: return s
    # split near middle at a space if any
    if ' ' in s:
        parts=s.split(' ')
        # greedy two lines
        mid=len(s)//2; acc=0; out=[]
        line1=[]
        for w in parts:
            if acc and acc+len(w)>len(s)/2: break
            line1.append(w); acc+=len(w)+1
        line2=parts[len(line1):]
        return ' '.join(line1)+'\n'+' '.join(line2) if line2 else s
    return s[:len(s)//2]+'\n'+s[len(s)//2:]

def vertical(d, year, idx, path, title):
    items=d['items']; kr=[d['kr'][it][idx] for it in items]; cn=[d['cn'][it][idx] for it in items]
    x=np.arange(len(items)); w=0.4
    fig,ax=plt.subplots(figsize=(max(12,len(items)*0.6),6.0),dpi=120)
    b1=ax.bar(x-w/2,kr,w,label='한국',color=KR); b2=ax.bar(x+w/2,cn,w,label='중국',color=CN)
    ax.set_title(title,fontproperties=fm.FontProperties(fname=fpb,size=16))
    ax.set_ylabel('평균 피인용',fontproperties=fm.FontProperties(fname=fp,size=12))
    ax.set_xticks(x); ax.set_xticklabels([wrap2(it) for it in items],fontproperties=fm.FontProperties(fname=fp,size=9))
    ax.legend(prop=fm.FontProperties(fname=fp,size=11),loc='upper right')
    ax.grid(axis='y',color='#d9d9d9',lw=0.8); ax.set_axisbelow(True)
    for s in ['top','right']: ax.spines[s].set_visible(False)
    mx=max(kr+cn+[1])
    for bars in (b1,b2):
        for r in bars:
            h=r.get_height()
            if h>0: ax.text(r.get_x()+r.get_width()/2,h+mx*0.01,('%.1f'%h),ha='center',va='bottom',rotation=90,fontsize=7,color='#333')
    ax.margins(x=0.01); ax.set_ylim(0,mx*1.15)
    plt.tight_layout(); fig.savefig(path,dpi=120); plt.close(fig)

def horizontal(d, year, idx, path, title):
    items=d['items']; kr=[d['kr'][it][idx] for it in items]; cn=[d['cn'][it][idx] for it in items]
    y=np.arange(len(items))[::-1]; h=0.4
    fig,ax=plt.subplots(figsize=(11,max(6,len(items)*0.42)),dpi=120)
    ax.barh(y+h/2,kr,h,label='한국',color=KR); ax.barh(y-h/2,cn,h,label='중국',color=CN)
    ax.set_title(title,fontproperties=fm.FontProperties(fname=fpb,size=16))
    ax.set_xlabel('평균 피인용',fontproperties=fm.FontProperties(fname=fp,size=12))
    ax.set_yticks(y); ax.set_yticklabels([it.replace(', ','·') for it in items],fontproperties=fm.FontProperties(fname=fp,size=10))
    ax.legend(prop=fm.FontProperties(fname=fp,size=11),loc='lower right')
    ax.grid(axis='x',color='#d9d9d9',lw=0.8); ax.set_axisbelow(True)
    for s in ['top','right']: ax.spines[s].set_visible(False)
    ax.margins(y=0.01)
    plt.tight_layout(); fig.savefig(path,dpi=120); plt.close(fig)

TITLE='핵심 품목별 한국·중국 평균 피인용 (%d년)'
specs=[
 ('반도체','data_반도체.json','vertical',[2023,2024,2025,2026]),
 ('로봇','data_로봇.json','horizontal',[2023,2024,2025,2026]),
 ('이차전지','data_이차전지.json','horizontal',[2022,2023,2024,2025,2026]),
]
made=[]
for name,jf,kind,years in specs:
    d=json.load(io.open(jf,encoding='utf-8'))
    sub=os.path.join(OUT,name); os.makedirs(sub,exist_ok=True)
    for yr in years:
        idx=yr-2022
        path=os.path.join(sub,'%s_핵심품목별_한국중국_평균피인용_%d년.png'%(name,yr))
        (vertical if kind=='vertical' else horizontal)(d,yr,idx,path,TITLE%yr)
        made.append(path)
print('made %d charts'%len(made))
for m in made: print(' ',m)
