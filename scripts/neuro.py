import re
CNS=re.compile(r'teratoid|\bAT/?RT\b|\bATRTs?\b|brain|\bCNS\b|intracranial|central nervous|neuro|cerebr|spinal|spine|posterior fossa|embryonal tumou?r|medulloblastoma|glioma|leptomening',re.I)
EXCL=re.compile(r'kidney|renal|\bRTK\b|\bMRTK\b|liver|hepat|soft[- ]tissue|extracranial|extra-cranial|extrarenal|extra-renal|\beMRT\b|ovar|SCCOHT|thorac|vulva|uter|bladder|malignant rhabdoid|\bMRTs?\b|sarcoma|carcinoma|wilms',re.I)
def is_neuro(text):
    """True if the text is about CNS (neuro-oncology) rhabdoid disease, or generic rhabdoid/SMARCB1 biology not tied to a non-CNS site."""
    return bool(CNS.search(text)) or not EXCL.search(text)

CNS_STRICT=re.compile(r'teratoid|\bAT/?RT\b|\bATRTs?\b|brain|\bCNS\b|intracranial|central nervous|cerebr|posterior fossa|embryonal tumou?r|neuro-?oncolog',re.I)
NONCNS_MODELS=re.compile(r'non-CNS|extracranial|extra-cranial|kidney|renal|G401|liver|soft[- ]tissue',re.I)
def is_neuro_strict(title, abstract=''):
    """Title names CNS disease; or title is generic and the abstract is about AT/RT / CNS and not only non-CNS models."""
    if CNS.search(title) and not EXCL.search(title): return True
    if CNS_STRICT.search(title): return True
    if EXCL.search(title): return False
    if not abstract: return False
    return bool(CNS_STRICT.search(abstract)) and not (NONCNS_MODELS.search(abstract) and not re.search(r'teratoid|AT/?RT|ATRT',abstract,re.I))
