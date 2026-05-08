import subprocess, sys
# Test with Chinese characters in output
r = subprocess.run("echo \"你好世界\"", shell=True, text=True, encoding="utf-8", capture_output=True)
print("Result: " + repr(r.stdout))
