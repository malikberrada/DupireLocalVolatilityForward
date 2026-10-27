"""Bounded analysis, precise failure records and immutable resumption of drafts."""
from copy import deepcopy
from collections import Counter
import json
from pathlib import Path
import re

from .io import read, write, copy, digest, sha, require, safe_child, check_manifest, seal
from . import reading_sources as sources
from .reading_model import validate_draft, quality_warnings, failure_code, local_endpoint


def diagnose(workbook, analysis_dir=None):
    book=read(workbook)
    require(book.get('format')=='dupire-reading-workbook-v1','Unknown reading workbook')
    ready,empty,missing=[],[],[]
    for work in book['works']:
        for decision in work['decisions']:
            pair=work['work_id']+'_'+decision['claim_id']
            a=decision['analysis']
            present=a.get('hypotheses') not in {None,'','À documenter dans le texte exact.'}
            if present:
                ready.append({'pair_id':pair,'relation':a['relation'],'derivability':a['derivability'],
                              'decision':decision['decision'],'scope':decision['scope'],'review_warnings':quality_warnings(a,decision['claim_id'])})
            elif work.get('source_sha256'):empty.append(pair)
            else:missing.append(pair)
    failures=[]
    if analysis_dir is not None:
        log=read(Path(analysis_dir)/'analysis_log.json')
        failures=[{'pair_id':x['pair_id'],'error_code':x.get('error_code') or failure_code(ValueError(x.get('error',''))),
                   'error':x.get('error',''),'details':x.get('details',{})} for x in log if x['status']=='analysis_failed']
    return {'status':'reading_analysis_diagnosed','comparison_pairs':len(ready)+len(empty)+len(missing),
            'drafts_present':len(ready),'empty_pairs_with_sources':len(empty),'pairs_without_source':len(missing),
            'drafts':ready,'empty_pairs':empty,'missing_source_pairs':missing,
            'failure_details_supplied':analysis_dir is not None,'failures':failures,
            'exact_failure_causes_known':bool(analysis_dir is not None and failures and all(f['error_code'] not in
                {'legacy_model_failure_or_truncation','invalid_analysis_schema','unknown'} for f in failures)),
            'scientific_priority_certified':False,'semantic_annotations_auto_verified':False}


def project_reference(root, claim_id):
    name='CRITERE_PROUVE_0.1.6.md' if claim_id=='C1' else 'JOINT_SEPARATION.md'
    path=root/'literature'/name
    text=path.read_text(encoding='utf-8')
    if claim_id=='C1':
        definitions=text[text.index('## 2.'):text.index('## 3.')]
        start=text.index('## 4.')
        proof=re.search(r'^### (?:Proof|Preuve)\b',text[start:],re.MULTILINE)
        require(proof is not None,'Missing proof heading in project reference: '+name)
        theorem=text[start:start+proof.start()]
        selection=definitions+'\n'+theorem
    elif claim_id=='C2':
        selection=text[text.index('## 1.'):text.index('## 2.')]+text[text.index('## 4.'):text.index('## 5.')]
    else:selection=text[text.index('## 1.'):text.index('## 4.')]
    return {'role':'project_result_not_prior_art','file':name,'source_sha256':sha(path),
            'scope':'selected_complete_sections','text':selection}


def select_anchored(extracted, task, registry, max_chars=11500, max_blocks=10):
    locators=' '.join(r['locator'] for r in registry['reviews'] if r['work_id']==task['work_id'])
    anchors=[]
    aliases={'théorème':'theorem','lemme':'lemma','remarque':'remark','définition':'definition',
             'hypothèse':'assumption','résultat':'result'}
    for kind,number in re.findall(r'\b(theorems?|théorèmes?|propositions?|lemmas?|lemmes?|remarks?|remarques?|definitions?|définitions?|assumptions?|hypothèses?|results?|résultats?)\s+([A-Z]?\d+(?:\.\d+)*)',locators,re.I):
        kind=kind.lower().rstrip('s')
        kind=aliases.get(kind,kind)
        anchors.append(re.compile(r'\b'+kind+r'\s+'+re.escape(number)+r'(?!\d|\.\d)',re.I))
    all_blocks=sources.passages(extracted)
    ranked=[]
    for index,block in enumerate(all_blocks):
        text=block['text'].lower()
        anchored=any(p.search(text) for p in anchors)
        score=sum(min(text.count(word),3) for word in sources.TERMS[task['claim_id']])
        if re.search(r'\b(theorem|proposition|lemma|definition|assumption)\s+\d',text):score+=4
        # Bibliography hits are useful context, not the work's own theorem statements.
        references=len(re.findall(r'\b(?:doi|arxiv|https?)\b',text))
        if references>=3:score-=15
        ranked.append((-int(anchored),-score,index,block))
    selected=[];used=0
    # Cover every named assumption/result before taking repeated references to one theorem.
    for pattern in anchors:
        candidates=[row for row in ranked if pattern.search(row[3]['text'])]
        if not candidates:continue
        candidates.sort(key=lambda row:(-int(any(pattern.match(line.strip()) for line in row[3]['text'].splitlines())),row[1],row[2]))
        block=candidates[0][3]
        if block['id'] in {b['id'] for b in selected}:continue
        if len(selected)<max_blocks and used+len(block['text'])<=max_chars:
            selected.append(block);used+=len(block['text'])
    for _,_,_,block in sorted(ranked):
        if len(selected)>=max_blocks:break
        if block['id'] in {b['id'] for b in selected}:continue
        if used+len(block['text'])>max_chars:continue
        selected.append(block);used+=len(block['text'])
    return sorted(selected,key=lambda b:(b['page'],b['line_start']))


def merge_batches(analyses,task,allowed):
    def unique(values):return list(dict.fromkeys(values))
    def prose(key):return '\n'.join(unique(a[key] for a in analyses))
    relations={a['relation'] for a in analyses};derivations={a['derivability'] for a in analyses}
    by_axis={a['axis_id']:a for value in analyses for a in value['axes']}
    result={'hypotheses':prose('hypotheses'),'conclusion':prose('conclusion'),
            'relation':next(iter(relations)) if len(relations)==1 else 'unresolved',
            'derivability':next(iter(derivations)) if len(derivations)==1 else 'unresolved',
            'derivation_note':prose('derivation_note'),
            'axes':[by_axis[a['id']] for a in task['axes']],
            'evidence_ids':unique(e for a in analyses for e in a['evidence_ids']),
            'limitations':unique(v for a in analyses for v in a['limitations'])}
    if len(relations)>1 or len(derivations)>1:result['limitations'].append('Conclusions des lots divergentes; synthèse conservée non résolue.')
    return validate_draft(result,task,allowed)


def recover_pair(task,blocks,client,model,endpoint,timeout,context,predict,thinking,retries,axes_per_call,out,progress):
    analyses=[];receipts=[];attempts=[];batch_number=0
    splittable={'invalid_analysis_schema','invalid_analysis_fields','invalid_field_type','empty_analysis_text',
                'empty_prior_condition','malformed_hypothesis','incomplete_hypothesis_coverage','axis_id_mismatch',
                'unknown_analysis_relation','unknown_axis_relation','unknown_evidence_id',
                'resolved_axis_without_evidence','resolved_conclusion_without_evidence',
                'invalid_json','duplicate_json_key','truncated_output','empty_output'}
    def generate(axes,parent=None):
        nonlocal batch_number
        batch_number+=1;batch=batch_number;previous=None
        sub=deepcopy(task);sub['axes']=axes
        for attempt in range(1,retries+2):
            diagnostic=out/'diagnostics'/f"{task['pair_id']}.batch{batch:02d}.try{attempt:02d}.response.json"
            progress('model_batch',pair=task['pair_id'],batch=batch,attempt=attempt,axes=len(sub['axes']),
                     thinking=thinking,num_predict=predict)
            try:
                value,receipt=client(sub,blocks,model,endpoint,timeout,context,predict,thinking,diagnostic,previous)
                validate_draft(value,sub,{b['id'] for b in blocks})
                analyses.append(value);receipts.append(receipt)
                attempts.append({'batch':batch,'parent_batch':parent,'axis_ids':[a['id'] for a in axes],
                                 'attempt':attempt,'status':'draft_ready',
                                 'diagnostic':diagnostic.relative_to(out).as_posix() if diagnostic.exists() else None})
                break
            except Exception as error:
                previous={'error_code':failure_code(error),'message':str(error)[:1000],
                          'details':getattr(error,'details',{}),
                          'instruction':'Respecter tous les axes et citer seulement les IDs autorisés; unresolved si preuve insuffisante.'}
                row={'batch':batch,'parent_batch':parent,'axis_ids':[a['id'] for a in axes],
                     'attempt':attempt,'status':'failed','error_code':failure_code(error),
                     'error':str(error)[:1000],'details':getattr(error,'details',{}),
                     'diagnostic':diagnostic.relative_to(out).as_posix() if diagnostic.exists() else None}
                attempts.append(row)
                progress('model_attempt_failed',pair=task['pair_id'],batch=batch,attempt=attempt,error_code=row['error_code'])
                write(out/'diagnostics'/f"{task['pair_id']}.attempts.json",attempts)
                if attempt==retries+1:
                    if len(axes)>1 and row['error_code'] in splittable:
                        progress('model_batch_split',pair=task['pair_id'],batch=batch,
                                 axes=len(axes),fallback_axes_per_call=1,error_code=row['error_code'])
                        for axis in axes:generate([axis],parent=batch)
                        return
                    raise RecoveryError(str(error),row['error_code'],attempts) from error
        write(out/'diagnostics'/f"{task['pair_id']}.attempts.json",attempts)
    for offset in range(0,len(task['axes']),axes_per_call):
        generate(task['axes'][offset:offset+axes_per_call])
    merged=merge_batches(analyses,task,{b['id'] for b in blocks})
    return merged,{'format':'dupire-model-receipt-v2','model_requested':model,'batch_receipts':receipts,
                   'attempts':attempts,'draft_sha256':digest(merged),'prompt_evidence_ids':[b['id'] for b in blocks],
                   'single_axis_fallback_used':any(a.get('parent_batch') is not None for a in attempts),
                   'source_sha256':task['source_sha256'],'project_reference_sha256':task['project_reference']['source_sha256'],
                   'review_warnings':quality_warnings(merged,task.get('claim_id')),'human_approved':False,'scope':'selected_statement',
                   'local_model_called':True,'remote_model_called':False}


class RecoveryError(ValueError):
    def __init__(self,message,code,attempts):
        super().__init__(message);self.code=code;self.attempts=attempts


def resume_drafts(campaign,previous,tasks,out):
    previous=Path(previous).resolve()
    check_manifest(previous)
    metadata=read(previous/'analysis.json')
    require(metadata['campaign_manifest_sha256']==sha(campaign/'manifest.json'),'Resume belongs to a different reading campaign')
    output=read(previous/'lectures_a_valider.json')
    original=read(campaign/'lectures_a_valider.json')
    require(output['format']==original['format'] and output['scientific_priority_certified'] is False,'Unsupported resume workbook')
    require([w['work_id'] for w in output['works']]==[w['work_id'] for w in original['works']],'Resume corpus changed')
    for old,new in zip(original['works'],output['works']):
        require(old['source_sha256']==new['source_sha256'],'Resume source bytes differ from the campaign')
    known={t['pair_id']:t for t in tasks};reused={}
    docs={d['work_id']:d for d in read(campaign/'documents.json')}
    for row in read(previous/'analysis_log.json'):
        if row['status']!='draft_ready_pending_reader':continue
        pair=row['pair_id'];require(pair in known and pair not in reused,'Duplicate/unknown saved model pair')
        task=known[pair]
        saved=read(safe_child(previous,pair+'.draft.json'))
        work=next(w for w in output['works'] if w['work_id']==task['work_id'])
        decision=next(d for d in work['decisions'] if d['claim_id']==task['claim_id'])
        require(saved['analysis']==decision['analysis'],'Resume workbook differs from its saved draft')
        receipt=saved['receipt']
        require(row.get('receipt')==receipt,'Resume log differs from the saved draft receipt')
        require(receipt.get('draft_sha256',digest(saved['analysis']))==digest(saved['analysis']),'Resume draft digest changed')
        # Version 0.5 receipts use exactly the original selection from the sealed campaign.
        allowed=set(receipt.get('prompt_evidence_ids',[b['id'] for b in task['selected_passages']]))
        doc=docs[task['work_id']]
        actual={b['id'] for b in sources.passages(read(safe_child(campaign,doc['pages_path'])))}
        require(allowed<=actual,'Resume packet cited passages absent from the source')
        validate_draft(saved['analysis'],task,allowed)
        copy(safe_child(previous,pair+'.draft.json'),out/(pair+'.draft.json'))
        for attempt in receipt.get('attempts',[]):
            if attempt.get('diagnostic'):
                copy(safe_child(previous,attempt['diagnostic']),safe_child(out,attempt['diagnostic']))
        attempt_log=Path('diagnostics')/(pair+'.attempts.json')
        if (previous/attempt_log).exists():copy(previous/attempt_log,out/attempt_log)
        decision['review_warnings']=quality_warnings(decision['analysis'],task['claim_id'])
        reused[pair]={**row,'reused_from_previous_run':True}
    return output,reused


def run(campaign,out,model,client,endpoint='http://127.0.0.1:11434',pairs=(),max_pairs=37,timeout=600,context=16384,
        resume=None,predict=8000,thinking='off',retries=1,axes_per_call=7):
    from . import readings as base
    campaign=Path(campaign).resolve();base.verify(campaign);local_endpoint(endpoint)
    require(not Path(out).resolve().is_relative_to(campaign),'Analysis output must be outside the sealed reading campaign')
    require(1<=max_pairs<=100 and 1<=timeout<=3600 and 4096<=context<=65536,'Invalid model budget')
    require(1024<=predict<=32768 and 0<=retries<=3 and 1<=axes_per_call<=14 and thinking in {'off','on','auto'},'Invalid retry/output budget')
    out=base.new_folder(out)
    tasks=read(campaign/'tasks.json');requested=set(pairs)
    require(not requested or requested <= {t['pair_id'] for t in tasks},'Unknown --pair ID')
    eligible=[t for t in tasks if (not requested or t['pair_id'] in requested) and t['selected_passages']]
    require(eligible,'No usable source passages; acquire a main text first')
    output,reused=(resume_drafts(campaign,resume,tasks,out) if resume else (read(campaign/'lectures_a_valider.json'),{}))
    chosen=[t for t in eligible if t['pair_id'] not in reused][:max_pairs]
    registry=read(campaign/'input_priority/registry.json')
    documents={d['work_id']:d for d in read(campaign/'documents.json')}
    log=list(reused.values())
    base.progress('analysis_resume',drafts_reused=len(reused),pairs_to_attempt=len(chosen),usable_pairs=len(eligible))
    metadata={'format':'dupire-reading-model-drafts-v2','campaign_manifest_sha256':sha(campaign/'manifest.json'),
              'model':model,'source_pairs':[t['pair_id'] for t in eligible],'readings_automatically_completed':0,
              'scientific_priority_certified':False,'local_model_called':bool(chosen),'remote_model_called':False,
              'settings':{'num_predict':predict,'num_ctx':context,'thinking':thinking,'retries':retries,'axes_per_call':axes_per_call,
                          'wire_axes_layout':'named_properties','single_axis_fallback':True}}
    def checkpoint():
        write(out/'lectures_a_valider.json',output);write(out/'analysis_log.json',log);write(out/'analysis.json',metadata)
        seal(out)
    checkpoint()
    for index,original in enumerate(chosen,1):
        task=deepcopy(original)
        doc=documents[task['work_id']]
        extracted=read(safe_child(campaign,doc['pages_path']))
        blocks=select_anchored(extracted,task,registry)
        task['project_reference']=project_reference(base.ROOT,task['claim_id'])
        base.progress('model_analysis',pair=task['pair_id'],index=index,total=len(chosen))
        try:
            draft,receipt=recover_pair(task,blocks,client,model,endpoint,timeout,context,predict,thinking,retries,axes_per_call,out,base.progress)
            work=next(w for w in output['works'] if w['work_id']==task['work_id'])
            decision=next(d for d in work['decisions'] if d['claim_id']==task['claim_id'])
            decision.update(analysis=draft,decision='pending',scope='selected_statement',review_warnings=receipt['review_warnings'])
            write(out/(task['pair_id']+'.draft.json'),{'analysis':draft,'receipt':receipt})
            log.append({'pair_id':task['pair_id'],'status':'draft_ready_pending_reader','receipt':receipt})
        except Exception as error:
            log.append({'pair_id':task['pair_id'],'status':'analysis_failed','error_code':getattr(error,'code',failure_code(error)),
                        'error':str(error)[:1000],'attempts':getattr(error,'attempts',[]),
                        'details':error.attempts[-1].get('details',{}) if getattr(error,'attempts',[]) else getattr(error,'details',{})})
        checkpoint()
    ready=sum(l['status']=='draft_ready_pending_reader' for l in log);failed=sum(l['status']=='analysis_failed' for l in log)
    return {'status':'partial_model_drafts' if ready and failed else 'model_analysis_failed' if failed else 'model_drafts_produced',
            'drafts_ready':ready,'drafts_reused':len(reused),'drafts_generated':ready-len(reused),'drafts_failed':failed,
            'pairs_attempted':len(chosen),'requested_usable_pairs':len(eligible),
            'usable_pairs':sum(bool(t['selected_passages']) for t in tasks),
            'comparisons_not_attempted':sum(bool(t['selected_passages']) for t in tasks)-ready-failed,
            'comparisons_without_source':sum(not t['selected_passages'] for t in tasks),
            'failure_counts':dict(Counter(l.get('error_code','unknown') for l in log if l['status']=='analysis_failed')),
            'workbook':str(out/'lectures_a_valider.json'),'local_model_called':bool(chosen),'remote_model_called':False,
            'readings_automatically_completed':0,'scientific_priority_certified':False}
