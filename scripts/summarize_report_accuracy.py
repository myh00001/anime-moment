"""Summarize an offline report audit without exporting images or observations."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def summarize(data):
    rows=data['results']
    groups=defaultdict(list)
    for row in rows:
        groups[(row['kind'],row['group'])].append(row)
    output=[]
    for (kind,group),items in sorted(groups.items()):
        counts=Counter(row['status'] for row in items)
        supported=all(bool(row['accepted']) for row in items)
        specific=counts['correct']+counts['wrong_specific']
        result={'kind':kind,'group':group,'n':len(items),'counts':dict(counts)}
        if supported:
            result['strict_accuracy_including_abstentions']=counts['correct']/len(items)
            result['precision_when_specific']=counts['correct']/specific if specific else None
            result['specific_coverage']=specific/len(items)
        else:
            result['neutral_fraction']=(counts['abstain_unsupported']+counts['correct_neutral'])/len(items)
        output.append(result)
    core=[row for row in rows if row['kind']=='public_original' and row['accepted']]
    counts=Counter(row['status'] for row in core)
    specific=counts['correct']+counts['wrong_specific']
    return {'completed_cases':len(rows),'source_hashes':data.get('sources',{}),
            'supported_public_originals':{'n':len(core),'counts':dict(counts),
                'strict_accuracy_including_abstentions':counts['correct']/len(core) if core else None,
                'precision_when_specific':counts['correct']/specific if specific else None,
                'specific_coverage':specific/len(core) if core else None},
            'groups':output,
            'notes':['Abstentions are not correct classifications.',
                     'Unsupported specific claims require image-level review.',
                     'Derived cases are separate and are not independent source images.',
                     'Small stratified sample; not a deployment-wide accuracy estimate.']}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('results');parser.add_argument('--output')
    args=parser.parse_args();report=summarize(json.loads(Path(args.results).read_text(encoding='utf-8')))
    text=json.dumps(report,indent=2,ensure_ascii=False)
    if args.output:Path(args.output).write_text(text+'\n',encoding='utf-8')
    else:print(text)
