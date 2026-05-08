import subprocess
import os

# Use non-Chinese command first
try:
    result = subprocess.run(
        "echo hello",
        shell=True,
        text=True,
        cwd=os.getcwd(),
        timeout=30,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    with open("sim_output.txt", "w", encoding="utf-8") as f:
        f.write("stdout: " + repr(result.stdout) + "\n")
        f.write("returncode: " + str(result.returncode) + "\n")
except Exception as e:
    with open("sim_output.txt", "w", encoding="utf-8") as f:
        f.write("exception: " + type(e).__name__ + ": " + str(e) + "\n")
