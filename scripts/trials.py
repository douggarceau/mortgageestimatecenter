# Fetch active rhabdoid-tumor trials from ClinicalTrials.gov and assign working groups. Usage: python3 trials.py out.json
import sys as _s, os as _o
_s.path.insert(0,_o.path.dirname(_o.path.abspath(__file__)))
from neuro import is_neuro, CNS
import json,re,sys,urllib.request,datetime
ACTIVE='RECRUITING,NOT_YET_RECRUITING,ACTIVE_NOT_RECRUITING,ENROLLING_BY_INVITATION,AVAILABLE'
u='https://clinicaltrials.gov/api/v2/studies?query.cond=rhabdoid&pageSize=200&filter.overallStatus='+ACTIVE
d=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'irtc'}),timeout=60))
NOVEL=r'tazemetostat|ribociclib|lee011|palbociclib|abemaciclib|alisertib|vorinostat|panobinostat|selinexor|olaparib|samotolisib|tipifarnib|ulixertinib|erdafitinib|ensartinib|larotrectinib|selpercatinib|vemurafenib|idasanutlin|ivosidenib|cabozantinib|cediranib|sirolimus|bortezomib|talabostat|everolimus|paxalisib|nivolumab|ipilimumab|pembrolizumab|atezolizumab|tiragolumab|durvalumab|ono-4538|car[ -]?t|\bcar\b|t cell|t-cell|lymphocyte|virus|g207|pvsripo|dnx|vaccine|8h9|moab|omburtamab|antibody|inhibitor|gallium|celecoxib|onivyde|talazoparib|nk cell|dendritic|chimeric|dfmo|eflornithine|amxt|onc206|becotatug|clr 131|zoledronic|fhd-609'
CARE=r'cyclophosphamide|etoposide|carboplatin|cisplatin|methotrexate|vincristine|thiotepa|melphalan|busulfan|topotecan|irinotecan|temozolomide|doxorubicin|ifosfamide|dactinomycin|gemcitabine|docetaxel|transplant|stem cell|chemotherapy|radiation|irradiation|radiotherapy|proton|surgery|surgical|backbone|quality|psychosocial|counseling|neurocog'
LB=r'liquid biopsy|cell-free|cfdna|ctdna|circulating tumor|cerebrospinal fluid'
out=[]
OVERRIDE={'NCT06942039':['care'],'NCT07589361':['care'],'NCT00602667':['care']}
EXCLUDE={'NCT01238250','NCT03959800'}
for st in d['studies']:
  p=st['protocolSection']; idm=p['identificationModule']
  if idm['nctId'] in EXCLUDE: continue
  sm=p['statusModule']; dm=p.get('designModule',{})
  ivs=p.get('armsInterventionsModule',{}).get('interventions',[])
  locs=p.get('contactsLocationsModule',{}).get('locations',[])
  title=idm['briefTitle']; summ=re.sub(r'\s+',' ',p.get('descriptionModule',{}).get('briefSummary',''))
  ivtxt=' '.join(i['name'] for i in ivs).lower(); full=(title+' '+summ+' '+ivtxt).lower()
  conds=' '.join(p.get('conditionsModule',{}).get('conditions',[]))
  specific=bool(re.search(r'rhabdoid|at/?rt|smarcb1|ini1|teratoid',title.lower())) and is_neuro(title)
  if not specific and not CNS.search(title+' '+conds+' '+summ): continue
  if specific is False and re.search(r'rhabdoid|teratoid',title,re.I): continue
  g=[]
  if re.search(NOVEL,ivtxt): g.append('novel')
  elif re.search(CARE,ivtxt) or any(i['type'] in('RADIATION','BEHAVIORAL') for i in ivs): g.append('care')
  if re.search(LB,full) and dm.get('studyType')=='OBSERVATIONAL' or re.search(r'liquid biopsy|cfdna|ctdna|cell-free',full): g.append('liquid')
  if dm.get('studyType')=='OBSERVATIONAL' and 'liquid' not in g: g.append('data')
  if not g: g.append('novel' if ivs else 'data')
  g=OVERRIDE.get(idm['nctId'],g)
  ther=[]
  for i in ivs:
    n=i['name']
    if i['type'] in('OTHER','PROCEDURE','GENETIC','DIAGNOSTIC_TEST','DEVICE') and not re.search(r'surg|transplant|car|t cell',n.lower()): continue
    if re.search(r'filgrastim|mesna|leucovorin|laboratory|pharmacolog|imaging|questionnaire|echocardiograph',n.lower()): continue
    if n.lower() not in [x.lower() for x in ther]: ther.append(n)
  out.append(dict(nct=idm['nctId'],title=title,status=sm['overallStatus'],
    phase=[x.replace('PHASE','Phase ').replace('EARLY_Phase 1','Early Phase 1').replace('NA','N/A') for x in dm.get('phases',[])],
    type=dm.get('studyType'),start=sm.get('startDateStruct',{}).get('date',''),
    firstPosted=sm.get('studyFirstPostDateStruct',{}).get('date',''),lastUpdate=sm.get('lastUpdatePostDateStruct',{}).get('date',''),
    enroll=dm.get('enrollmentInfo',{}).get('count'),sponsor=p['sponsorCollaboratorsModule']['leadSponsor']['name'],
    countries=sorted({l.get('country') for l in locs if l.get('country')}),nsites=len(locs),specific=specific,
    minAge=p.get('eligibilityModule',{}).get('minimumAge',''),maxAge=p.get('eligibilityModule',{}).get('maximumAge',''),
    summary=(summ[:400].rsplit(' ',1)[0]+'…') if len(summ)>400 else summ,groups=g,therapies=ther[:8]))
res={'updated':datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'),'items':out}
json.dump(res,open(sys.argv[1],'w'),separators=(',',':'))
print(len(out),'active trials')
