"""Apply a reviewed, digest-bound correction packet. Never approve a reading."""
from copy import deepcopy
from pathlib import Path
import argparse
import json
import re
import unicodedata

from .io import read, write, copy, sha, digest, require, check_manifest, seal, safe_child
from . import reading_sources as sources
from .reading_model import validate_draft, quality_warnings
from .argument_checks import verify_arguments

ROOT = Path(__file__).resolve().parents[1]


def normalized(text):
    text=unicodedata.normalize('NFKC', text).casefold().translate(str.maketrans({'–':'-','—':'-','−':'-'}))
    return re.sub(r'\s+', '', text)


def bind_references(campaign, packet):
    from .readings import verify
    campaign=Path(campaign).resolve(); verify(campaign)
    docs={d['work_id']:d for d in read(campaign/'documents.json')}
    bindings={}
    for wid, source in packet['sources'].items():
        doc=docs.get(wid)
        require(doc and doc.get('source_sha256')==source['source_sha256'], 'Source bytes differ from reviewed version: '+wid)
        require(sha(safe_child(campaign,doc['source_path']))==source['source_sha256'], 'Source PDF changed: '+wid)
        extracted=read(safe_child(campaign,doc['pages_path']));blocks=sources.passages(extracted)
        refs={}
        for key, ref in source['references'].items():
            page=next((p for p in extracted['pages'] if p['page']==ref['page']),None)
            require(page is not None,'Reviewed physical page is unavailable: '+wid+'/'+key)
            positions=[i+1 for i,line in enumerate(page['lines']) if normalized(ref['needle']) in normalized(line)]
            require(positions,'Reviewed statement anchor is unavailable: '+wid+'/'+key)
            line=positions[0]
            candidates=[b for b in blocks if b['page']==ref['page'] and b['line_start']<=line<=b['line_end']]
            require(candidates,'No passage contains reviewed statement anchor: '+wid+'/'+key)
            if ref.get('whole_pages') or ref.get('end_page') or ref.get('end_needle'):
                first_line=1 if ref.get('whole_pages') else line
                end_page=ref.get('end_page',ref['page'])
                last_page=next((p for p in extracted['pages'] if p['page']==end_page),None)
                require(last_page is not None,'Reviewed end page is unavailable: '+wid+'/'+key)
                last_line=len(last_page['lines'])
                if ref.get('end_needle'):
                    endings=[i+1 for i,value in enumerate(last_page['lines'])
                             if normalized(ref['end_needle']) in normalized(value) and
                             (end_page>ref['page'] or i+1>first_line)]
                    require(endings,'Reviewed statement end anchor is unavailable: '+wid+'/'+key)
                    last_line=endings[0]-1
                selected=[b for b in blocks if
                          (b['page']>ref['page'] or (b['page']==ref['page'] and b['line_end']>=first_line)) and
                          (b['page']<end_page or (b['page']==end_page and b['line_start']<=last_line))]
            else:
                selected=[min(candidates,key=lambda b:abs(line-b['line_start']-3))]
            require(selected,'No passages cover reviewed statement: '+wid+'/'+key)
            chosen=selected[0]
            refs[key]={'page':ref['page'],'anchor':ref['needle'],'line':line,'evidence_id':chosen['id'],
                       'evidence_ids':[b['id'] for b in selected],
                       'passage_text_sha256':{b['id']:digest(b['text']) for b in selected}}
        bindings[wid]={'source_sha256':source['source_sha256'],'version_id':source['version_id'],
                       'page_index_sha256':sha(safe_child(campaign,doc['pages_path'])),
                       'extractor':extracted.get('extractor'),'references':refs}
    return bindings


def make_book(original,packet,bindings):
    from .readings import protocol
    output=deepcopy(original);changes=[]
    expected=protocol()['claims']
    for comparison in packet['comparisons']:
        wid,cid=comparison['work_id'],comparison['claim_id']
        work=next((w for w in output['works'] if w['work_id']==wid),None)
        require(work is not None,'Missing reviewed work: '+wid)
        require(work['source_sha256']==packet['sources'][wid]['source_sha256'],'Workbook source differs: '+wid)
        decision=next((d for d in work['decisions'] if d['claim_id']==cid),None)
        require(decision is not None and decision['decision']=='pending','Only the identified pending drafts may be corrected: '+wid+'_'+cid)
        require(digest(decision['analysis'])==comparison['input_analysis_sha256'],
                'Draft differs from the source-checked correction basis; preserve manual edits: '+wid+'_'+cid)
        source=deepcopy(comparison['analysis'])
        def evidence(keys):
            return list(dict.fromkeys(value for key in keys for value in bindings[wid]['references'][key]['evidence_ids']))
        source['evidence_ids']=evidence(source.pop('reference_keys'))
        for axis in source['axes']:axis['evidence_ids']=evidence(axis.pop('reference_keys'))
        all_ids=set(source['evidence_ids'])|{v for a in source['axes'] for v in a['evidence_ids']}
        validate_draft(source,{'axes':expected[cid]},all_ids)
        before=decision['analysis']
        changes.append({'pair_id':comparison['pair_id'],'before_analysis_sha256':digest(before),
                        'after_analysis_sha256':digest(source),
                        'changed_fields':[key for key in source if before.get(key)!=source[key]],
                        'scope':'selected_statement','human_approved':False})
        decision.update(analysis=source,decision='pending',scope='selected_statement',review_warnings=quality_warnings(source,cid))
        decision['bibliographic_verification']={
            'kind':packet['review_kind'],'date':packet['review_date'],
            'source_sha256':work['source_sha256'],'locator':packet['sources'][wid]['locator'],
            'scope':'selected_statements_and_explicit_mathematical_arguments',
            'human_approved':False,'full_work_exclusion':False,'scientific_priority_certified':False}
    output['scientific_priority_certified']=False
    return output,changes


def apply(workbook,out,campaign):
    from .readings import new_folder
    workbook=Path(workbook).resolve();campaign=Path(campaign).resolve()
    packet=read(ROOT/'bibliography/corrections_v053.json')
    original=read(workbook)
    require(original.get('format')=='dupire-reading-workbook-v1','Unknown workbook format')
    require(not Path(out).resolve().is_relative_to(campaign),'Write corrections outside the sealed campaign')
    require(not ((workbook.parent/'manifest.json').exists() and Path(out).resolve().is_relative_to(workbook.parent)),
            'Write corrections outside the sealed model run')
    # Verify source identity and citation anchors before any output mutation.
    bindings=bind_references(campaign,packet)
    corrected,changes=make_book(original,packet,bindings)
    out=new_folder(out)
    copy(workbook,out/'input_workbook.json')
    write(out/'correction_packet.json',packet);write(out/'source_bindings.json',bindings)
    write(out/'lectures_corrigees.json',corrected);write(out/'changes.json',changes)
    write(out/'argument_checks.json',verify_arguments())
    copy(ROOT/'bibliography/verification_v053.md',out/'verification_bibliographique.md')
    write(out/'verification.json',{'format':'dupire-reading-corrections-v1','review_date':packet['review_date'],
          'input_workbook_sha256':sha(workbook),'packet_sha256':digest(packet),
          'campaign_manifest_sha256':sha(campaign/'manifest.json'),'source_bytes_verified_when_applied':True,
          'source_count':len(bindings),'comparisons_corrected':len(changes),
          'axis_cells_rewritten':sum(len(c['analysis']['axes']) for c in packet['comparisons']),
          'human_readings_automatically_accepted':0,'semantic_annotations_auto_verified':False,
          'scientific_priority_certified':False,'solver_called':False,'network_used':False})
    seal(out)
    return verify_result(out,campaign)


def verify_result(folder,campaign=None):
    folder=Path(folder).resolve();count=check_manifest(folder)
    record=read(folder/'verification.json');packet=read(folder/'correction_packet.json')
    require(record.get('format')=='dupire-reading-corrections-v1','Unknown correction dossier')
    require(record['scientific_priority_certified'] is False and record['human_readings_automatically_accepted']==0,
            'Corrections cannot approve readings or establish priority')
    require(sha(folder/'input_workbook.json')==record['input_workbook_sha256'],'Original workbook changed')
    require(digest(packet)==record['packet_sha256'],'Correction packet changed')
    bindings=read(folder/'source_bindings.json')
    if campaign is not None:
        campaign=Path(campaign).resolve()
        require(sha(campaign/'manifest.json')==record['campaign_manifest_sha256'],'Verification campaign differs')
        require(bind_references(campaign,packet)==bindings,'Source or citation bindings changed')
    expected,changes=make_book(read(folder/'input_workbook.json'),packet,bindings)
    require(read(folder/'lectures_corrigees.json')==expected,'Corrected workbook differs from the reviewed changes')
    require(read(folder/'changes.json')==changes,'Change log differs')
    require(read(folder/'argument_checks.json')==verify_arguments(),'Scoped mathematical argument checks changed')
    return {'status':'bibliographic_corrections_verified','file_hashes':count,
            'comparisons_corrected':len(changes),'axis_cells_rewritten':record['axis_cells_rewritten'],
            'source_count':len(bindings),'source_bytes_reverified':campaign is not None,
            'source_bytes_verified_when_applied':record['source_bytes_verified_when_applied'],
            'mathematical_arguments_checked':2,'human_readings_automatically_accepted':0,
            'semantic_annotations_auto_verified':False,'scientific_priority_certified':False,
            'solver_called':False,'network_used':False,
            'workbook':str(folder/'lectures_corrigees.json')}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Appliquer les corrections bibliographiques vérifiées aux brouillons v052')
    parser.add_argument('--workbook',type=Path)
    parser.add_argument('--campaign',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--verify',type=Path)
    args=parser.parse_args(argv)
    if args.verify:
        require(not args.workbook and not args.out,'Use --verify separately from correction inputs')
        result=verify_result(args.verify,args.campaign)
    else:
        require(args.workbook and args.campaign and args.out,'Provide --workbook, --campaign and --out')
        result=apply(args.workbook,args.out,args.campaign)
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0
