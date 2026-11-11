import sys, runpy, json, logging
from pathlib import Path
logging.basicConfig(level=logging.INFO)
counts={'cache_wrapper_calls':0,'tavily_calls':0}
last={}
def trace(frame,event,arg):
 name=frame.f_code.co_name; file=frame.f_code.co_filename.replace('\\','/')
 if '/france_admission_agent/' not in file: return None
 if event=='call' and name=='search' and file.endswith(('search/cache.py','search/tavily.py')):
  kind='tavily_calls' if file.endswith('tavily.py') else 'cache_wrapper_calls'; counts[kind]+=1
  print('TRACE',kind,frame.f_locals.get('query'))
 if event=='return' and name in ('generate_frontier_query','is_exact_duplicate','extract_candidates_from_search_results','get_default_search_client'):
  value = ('configured' if arg is not None else 'missing') if name=='get_default_search_client' else (len(arg) if name=='extract_candidates_from_search_results' else (arg[0] if name=='is_exact_duplicate' and arg else arg))
  print('TRACE',name,value)
 if event=='line' and name=='execute_discovery_round':
  state={k:frame.f_locals.get(k) for k in ['searches_attempted','consecutive_actual_low_value','stop_reason']}
  if state!=last:
   last.clear();last.update(state);print('TRACE state',json.dumps(state))
 if event=='return' and name=='search' and file.endswith('tavily.py'):
  print('TRACE provider results',len(arg.results) if arg else None)
 if event=='exception' and file.endswith('tavily.py'):
  print('TRACE provider exception',arg[0].__name__)
 return trace
sys.settrace(trace)
try: runpy.run_path('run_discovery_round.py',run_name='__main__')
finally:
 sys.settrace(None); print('TRACE boundary counts',json.dumps(counts))
