import re


def diversify(matches,queries):
    candidates=[];seen=set()
    for item in matches:
        tokens=set(re.findall(r'\w+',item['text'].casefold()))
        key=item['text'].strip().casefold()
        if key not in seen:
            seen.add(key);candidates.append((item,tokens))
    candidates=candidates[:128]
    selected=[];used=[]
    while candidates:
        best_index=0;best_score=-float('inf')
        for index,(item,tokens) in enumerate(candidates):
            relevance=sum(item['text'].casefold().count(q.casefold()) for q in queries)/max(1,len(tokens))
            redundancy=max((len(tokens & previous)/max(1,len(tokens | previous)) for previous in used),default=0)
            score=.65*min(1,relevance)-.35*redundancy
            if score>best_score:best_index=index;best_score=score
        item,tokens=candidates.pop(best_index);selected.append(item);used.append(tokens)
    return selected

