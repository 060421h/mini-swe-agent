import subprocess
r = subprocess.run("echo " + chr(0x4f60) + chr(0x597d), shell=True, text=True, encoding="utf-8", errors="replace", capture_output=True)
with open("result3.txt", "w", encoding="utf-8") as f:
    f.write("stdout: " + repr(r.stdout) + "\n")
    f.write("returncode: " + str(r.returncode) + "\n")
