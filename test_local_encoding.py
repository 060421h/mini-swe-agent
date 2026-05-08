import subprocess
import sys
import locale

# Test 1: binary mode
r1 = subprocess.run("echo hello", shell=True, capture_output=True)
print("Test 1 binary:", repr(r1.stdout))

# Test 2: text mode with utf-8
enc = locale.getpreferredencoding()
print("Locale encoding:", enc)
