"""Read-only workload against a deployed TEST instance with 50 existing accounts."""
import argparse,json,time,threading,statistics
from concurrent.futures import ThreadPoolExecutor
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import build_opener,HTTPCookieProcessor,Request

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--accounts',required=True,help='Private JSON file: [{"login":"...","password":"..."}, ...]')
    parser.add_argument('--output',default='reports/server-load.json')
    args=parser.parse_args();origin=args.url.rstrip('/')
    accounts=json.loads(Path(args.accounts).read_text(encoding='utf-8'))
    if len(accounts)!=50 or len({a['login'] for a in accounts})!=50:raise SystemExit('Exactly 50 distinct existing accounts are required')
    barrier=threading.Barrier(50,timeout=120)
    def work(account):
        client=build_opener(HTTPCookieProcessor(CookieJar()));times=[]
        def call(path,data=None):
            body=json.dumps(data).encode() if data is not None else None
            req=Request(origin+'/api'+path,data=body,headers={'Origin':origin,'Content-Type':'application/json'})
            with client.open(req,timeout=120) as r:return json.load(r)
        try:
            login=call('/auth/login',account)
            if login['user']['mustChange']:raise RuntimeError('Change temporary passwords before testing')
            barrier.wait()
            for iteration in range(5):
                for path in ('/requests','/dashboard','/notifications'):
                    start=time.perf_counter();call(path);times.append((time.perf_counter()-start)*1000)
            return {'role':login['user']['role'],'times':times}
        except Exception as e:
            barrier.abort()
            return {'error':type(e).__name__}
    with ThreadPoolExecutor(max_workers=50) as pool:results=list(pool.map(work,accounts))
    durations=sorted(t for r in results for t in r.get('times',[]));errors=[r['error'] for r in results if 'error' in r]
    report={'users':50,'roles':sorted({r['role'] for r in results if 'role' in r}),'requests_completed':len(durations),'errors':errors,'scope':'Concurrent authenticated API reads; excludes import/export and browser layout'}
    if durations:report.update(median_ms=round(statistics.median(durations),2),p95_ms=round(durations[int((len(durations)-1)*.95)],2),max_ms=round(max(durations),2))
    report['passed']=not errors and report['roles']==list(range(6)) and len(durations)==750 and max(durations,default=999999)<=2000
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)
if __name__=='__main__':main()
