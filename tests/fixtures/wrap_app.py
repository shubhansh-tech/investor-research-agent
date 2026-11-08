import sys, runpy, os, shutil
sys.path.insert(0, "/home/claude/investor-research-agent"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_edgar_qubt
from agent import onboarding
onboarding._get = lambda url, log: (log.append(url) if log is not None else None) or fake_edgar_qubt.fetch(url)
_copytree = shutil.copytree
shutil.copytree = lambda src, dst, *a, **k: _copytree(src, dst, ignore=shutil.ignore_patterns("QUBT"))  # start without QUBT
os.chdir("/home/claude/investor-research-agent")
runpy.run_path("/home/claude/investor-research-agent/app.py", run_name="__main__")
