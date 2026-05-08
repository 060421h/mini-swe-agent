import subprocess, locale
r = subprocess.run("echo hello", shell=True, capture_output=True)
open("result.txt", "w", encoding="utf-8").write(repr(r.stdout))
