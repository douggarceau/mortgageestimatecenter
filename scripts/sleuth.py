# Fresh-signal feeds: preprints (Europe PMC) and NIH grants (RePORTER). Usage: python3 sleuth.py out.json
import sys as _s, os as _o
_s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__)))
from neuro import is_neuro, is_neuro_strict
import json,re,sys,urllib.request,urllib.parse,datetime
today=datetime.date.today()
RT=re.compile(r'rhabdoid|teratoid|\bAT/?RT\b|SMARCB1|INI1',re.I)
RTSTRICT=re.compile(r'rhabdoid|teratoid|\bAT/?RT\b',re.I)
BAD=re.compile(r'case report|case series|\ba case\b|year-old|month-old|\bin an? (girl|boy|child|infant|adolescent|patient|adult)\b|syndrome|mimick|HIV|schwannom|dendrite|neurodevelop|rhabdoid (morpholog|differentiat|feature)',re.I)
OTHER=re.compile(r'carcinoma|sarcoma|meningioma|chordoma|lymphoma|schwannom|glioma|melanoma|leukemia|myeloma|neuroepithelial|pineal|HCC|breast|prostate|lung',re.I)
keep=lambda title,ab='': not BAD.search(title) and ((RTSTRICT.search(title)) or (RT.search(title) and not OTHER.search(title)) or (RTSTRICT.search(ab) and not OTHER.search(title)))
# preprints
start=(today-datetime.timedelta(days=365)).isoformat()
q='(TITLE:"rhabdoid" OR TITLE:"teratoid" OR TITLE:"SMARCB1" OR TITLE:"INI1" OR ABSTRACT:"rhabdoid") AND SRC:PPR AND FIRST_PDATE:[%s TO %s]'%(start,(today+datetime.timedelta(days=2)).isoformat())
u='https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&pageSize=100&sort=FIRST_PDATE_D%20desc&resultType=core&query='+urllib.parse.quote(q)
d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'irtc'}),timeout=60))
pre=[]
for r in d['resultList']['result']:
  title=re.sub(r'<[^>]+>','',r.get('title','')).strip()
  if not keep(title,r.get('abstractText','')) or not is_neuro_strict(title,re.sub(r'<[^>]+>','',r.get('abstractText',''))): continue
  au=r.get('authorString','').split(', ')
  pub=(r.get('bookOrReportDetails') or {}).get('publisher') or r.get('journalInfo',{}).get('journal',{}).get('title','') or 'Preprint server'
  doi=r.get('doi','')
  pre.append(dict(id=r['id'],title=title,date=r.get('firstPublicationDate',''),server=pub,doi=doi,
    first=au[0] if au and au[0] else '',nauth=len([a for a in au if a]),url=('https://doi.org/'+doi) if doi else 'https://europepmc.org/article/PPR/'+r['id'],
    abstract=re.sub(r'<[^>]+>','',r.get('abstractText',''))[:600]))
# NIH grants
body={"criteria":{"advanced_text_search":{"operator":"or","search_field":"projecttitle,abstracttext","search_text":"rhabdoid OR \"atypical teratoid\""},"fiscal_years":[today.year-1,today.year,today.year+1]},
 "include_fields":["ApplId","ProjectNum","ProjectTitle","PrincipalInvestigators","Organization","AwardAmount","FiscalYear","ProjectStartDate","ProjectEndDate","AwardNoticeDate","AgencyIcAdmin","ProjectDetailUrl","AbstractText"],
 "offset":0,"limit":100,"sort_field":"award_notice_date","sort_order":"desc"}
req=urllib.request.Request('https://api.reporter.nih.gov/v2/projects/search',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','User-Agent':'irtc'})
r=json.load(urllib.request.urlopen(req,timeout=90))
gr=[];seen=set()
for x in r['results']:
  title=x.get('project_title','') or ''; ab=x.get('abstract_text','') or ''
  if re.search(r'HIV|schwannom',title,re.I): continue
  if not (RTSTRICT.search(title) or len(RTSTRICT.findall(ab))>=3): continue
  if not is_neuro_strict(title,ab) or not x.get('award_notice_date'): continue
  core=(x.get('project_num') or '')[1:12]
  if core in seen: continue
  seen.add(core)
  pis=[p.get('full_name','').title().replace('  ',' ') for p in (x.get('principal_investigators') or [])]
  org=(x.get('organization') or {})
  gr.append(dict(appl=x.get('appl_id'),num=x.get('project_num',''),title=title.strip(),pis=pis[:3],org=(org.get('org_name') or '').title(),
    city=(org.get('org_city') or '').title(),amount=x.get('award_amount'),fy=x.get('fiscal_year'),notice=(x.get('award_notice_date') or '')[:10],
    start=(x.get('project_start_date') or '')[:10],end=(x.get('project_end_date') or '')[:10],ic=(x.get('agency_ic_admin') or {}).get('abbreviation',''),
    url='https://reporter.nih.gov/project-details/%s'%x.get('appl_id')))
res={'updated':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),'preprints':pre[:40],'grants':gr[:40],'grantsTotal':len(gr)}
json.dump(res,open(sys.argv[1],'w'),separators=(',',':'))
print(len(pre),'preprints',len(gr),'grants')
