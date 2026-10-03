import sys as _s, os as _o
_s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__)))
from neuro import is_neuro, is_neuro_strict
import json,urllib.request,urllib.parse,sys,datetime
Q='(rhabdoid[ti] OR "atypical teratoid"[ti] OR SMARCB1[ti] OR INI1[ti] OR hSNF5[ti]) AND english[la] AND hasabstract NOT ("case reports"[pt] OR letter[pt] OR comment[pt] OR editorial[pt] OR "published erratum"[pt] OR news[pt] OR preprint[pt] OR "retracted publication"[pt] OR "case report"[ti] OR "case series"[ti] OR "a case"[ti])'
B='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'

MON={m:i+1 for i,m in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])}
def pdate(s):
  p=(s or '').replace(',','').split()
  if len(p)>=2 and p[0].isdigit() and p[1][:3] in MON:
    d=int(p[2]) if len(p)>=3 and p[2].isdigit() else 1
    return '%s-%02d-%02d'%(p[0],MON[p[1][:3]],d)
  return ''
def get(u): return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'irtc-feed'}),timeout=30))
r=get(B+'esearch.fcgi?db=pubmed&retmode=json&sort=pub_date&retmax=120&datetype=pdat&mindate=2020&maxdate=%d/12/31' % (datetime.date.today().year+1) + '&term='+urllib.parse.quote(Q))
ids=r['esearchresult']['idlist']; total=r['esearchresult']['count']
s=get(B+'esummary.fcgi?db=pubmed&retmode=json&id='+','.join(ids))['result']
out=[]
for i in ids:
  d=s[i]; au=[a['name'] for a in d.get('authors',[]) if a.get('authtype')=='Author']
  doi=next((x['value'] for x in d.get('articleids',[]) if x['idtype']=='doi'),'')
  pmc=next((x['value'] for x in d.get('articleids',[]) if x['idtype']=='pmc'),'')
  out.append(dict(pmid=i,title=d['title'],journal=d.get('source',''),date=(pdate(d.get('epubdate')) or d.get('sortpubdate','')[:10].replace('/','-')),online=bool(pdate(d.get('epubdate'))),
    pubdate=d.get('pubdate',''),authors=(au[0]+(' … '+au[-1] if len(au)>1 else '')) if au else '',nauth=len(au),
    doi=doi,pmc=pmc,types=[t for t in d.get('pubtype',[]) if t.startswith('Clinical Trial') or t in('Randomized Controlled Trial','Meta-Analysis','Systematic Review','Review','Multicenter Study','Practice Guideline','Guideline','Consensus Development Conference')][:2] or ['Original research']))
import re
BAD_J=re.compile(r'case rep|cases j|case reports',re.I)
BAD_T=re.compile(r'mimick|case report|\bcases?\b(?! of \d)|year-old|month-old|\ba (girl|boy|child|patient|woman|man|neonate|newborn|infant)\b|\bin an? (girl|boy|child|infant|patient|adult)\b|syndrome|developmental disorder|schwannom|dendrite|reovir|rhabdoid (morpholog|differentiat|feature)|erratum|corrigendum|retraction',re.I)
RT=re.compile(r'rhabdoid|teratoid|\bAT/?RT\b',re.I)
OTHER=re.compile(r'carcinoma|sarcoma|meningioma|chordoma|lymphoma|schwannom|glioma|melanoma|leukemia|myeloma|neuroepithelial|pineal|LGDIT',re.I)
out=[o for o in out if not BAD_J.search(o['journal']) and not BAD_T.search(o['title']) and (RT.search(o['title']) or not OTHER.search(o['title'])) and is_neuro(o['title'])]
# abstract check for titles that do not name the CNS
import xml.etree.ElementTree as ET, time
gen=[o['pmid'] for o in out if not is_neuro_strict(o['title'])]
ABS={}
for k in range(0,len(gen),100):
  time.sleep(0.5)
  x=urllib.request.urlopen(urllib.request.Request(B+'efetch.fcgi?db=pubmed&retmode=xml&id='+','.join(gen[k:k+100]),headers={'User-Agent':'irtc-feed'}),timeout=60).read()
  for a in ET.fromstring(x).findall('.//PubmedArticle'):
    ABS[a.findtext('.//PMID')]=' '.join(''.join(e.itertext()) for e in a.findall('.//AbstractText'))
out=[o for o in out if is_neuro_strict(o['title'],ABS.get(o['pmid'],''))][:60]
res={'updated':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),'total':int(total),'items':out}
json.dump(res,open(sys.argv[1] if len(sys.argv)>1 else 'pubs.json','w'),separators=(',',':'))
print(total,len(out)); [print(o['date'],o['journal'],'|',o['title'][:80]) for o in out[:8]]
