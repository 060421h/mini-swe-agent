import subprocess
import locale

r = subprocess.run("echo " + chr(0x4f60) + chr(0x597d), shell=True, capture_output=True)

with open("result2.txt", "w", encoding="utf-8") as f:
    f.write("bytes: " + repr(r.stdout) + "\n")
    f.write("locale: " + locale.getpreferredencoding() + "\n")
    for enc in ["utf-8", "gbk", "cp936"]:
        try:
            decoded = r.stdout.decode(enc, errors="replace")
            f.write(enc + ": " + repr(decoded) + "\n")
        except Exception as e:
            f.write(enc + " error: " + str(e) + "\n")
