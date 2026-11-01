import json, math, os, re, time


def service_operation(path,service,operation,outcome,retry_after,stamp=None):
    from .storage import atomic, persistent_lock
    from .store import read_bounded
    stamp=time.time() if stamp is None else stamp
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',service):raise ValueError('invalid service identifier')
    if retry_after is not None and (not math.isfinite(retry_after) or retry_after<0 or not math.isfinite(stamp+retry_after)):
        raise ValueError('invalid retry-after seconds')
    def load():
        if not os.path.lexists(path):return {}
        values=json.loads(read_bounded(path,1048576)[0].decode('utf-8-sig'))
        if not isinstance(values,dict) or len(values)>128:raise ValueError('invalid health store')
        for record in values.values():
            if not isinstance(record,dict) or set(record)!={'failures','until','probe_until','terminal'}:raise ValueError('invalid health record')
            if not isinstance(record['failures'],list) or len(record['failures'])>128 or type(record['terminal']) is not bool:
                raise ValueError('invalid health record')
            if not all(type(n) in (int,float) and math.isfinite(n) and n>=0 for n in record['failures']+[record['until'],record['probe_until']]):
                raise ValueError('invalid health timing')
        return values
    def report(record):
        state='terminal' if record['terminal'] else 'open' if stamp<record['until'] else 'half_open' if record['until'] else 'closed'
        allowed=state=='closed' or (state=='half_open' and stamp>=record['probe_until'])
        return {'service':service,'state':state,'allowed':allowed,'retry_at':max(record['until'],record['probe_until']),
                'advisory_only':True}
    if operation=='status':return report(load().get(service,{'failures':[],'until':0,'probe_until':0,'terminal':False}))
    path.parent.mkdir(parents=True,exist_ok=True)
    with persistent_lock(path.with_name(path.name+'.lock')):
        values=load();record=values.get(service,{'failures':[],'until':0,'probe_until':0,'terminal':False})
        result=report(record)
        if operation=='probe':
            if not result['allowed']:return result
            if result['state']=='half_open':record['probe_until']=stamp+10
            else:return result
        elif operation=='record':
            if outcome not in ('success','transient','terminal'):raise ValueError('observation outcome required')
            if outcome=='success':record={'failures':[],'until':0,'probe_until':0,'terminal':False}
            elif outcome=='terminal':record['terminal']=True
            else:
                record['failures']=[n for n in record['failures'] if stamp-60<=n<=stamp][-127:]+[stamp]
                if len(record['failures'])>=3 or record['until'] or retry_after:
                    record['until']=stamp+max(30,retry_after or 0);record['probe_until']=0
        else:raise ValueError('invalid service operation')
        if service not in values and len(values)>=128:raise ValueError('too many service records')
        values[service]=record;atomic(path,values)
        return result if operation=='probe' else report(record)

