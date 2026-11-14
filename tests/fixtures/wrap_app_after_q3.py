import sys, runpy, os
sys.path.insert(0, "/home/claude/investor-research-agent"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_edgar_qubt_after_q3 as fake_edgar_qubt3
from agent import onboarding
onboarding._get = lambda url, log: (log.append(url) if log is not None else None) or fake_edgar_qubt3.fetch(url)
os.chdir("/home/claude/investor-research-agent")
runpy.run_path("/home/claude/investor-research-agent/app.py", run_name="__main__")
