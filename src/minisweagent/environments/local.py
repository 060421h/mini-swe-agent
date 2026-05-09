import os
import platform
import subprocess
from typing import Any
import re
from pathlib import Path

from pydantic import BaseModel

from minisweagent.exceptions import Submitted
from minisweagent.utils.serialize import recursive_merge


class LocalEnvironmentConfig(BaseModel):
    cwd: str = ""
    env: dict[str, str] = {}
    timeout: int = 30
    # 新增安全配置
    enable_security: bool = True  # 是否启用安全限制
    blocked_commands: list[str] = []  # 自定义黑名单

class LocalEnvironment:
    def __init__(self, *, config_class: type = LocalEnvironmentConfig, **kwargs):
        """This class executes bash commands directly on the local machine."""
        self.config = config_class(**kwargs)
        # ========== 命令安全黑名单 ==========
        self.default_blocked_patterns = [
            # 危险删除命令
            r"rm\s+-rf\s+/",           # 删除根目录
            r"rm\s+-rf\s+~",           # 删除用户目录
            r"rm\s+-rf\s+/\w+",        # 删除系统目录
            r"rm\s+-rf\s+\*",          # 删除当前目录所有文件
            r"rm\s+-rf\s+\.\*",        # 删除隐藏文件
            
            # 权限修改
            r"chmod\s+777\s+/",        # 修改根目录权限
            r"chmod\s+777\s+/etc",     # 修改系统配置权限
            r"chown\s+-R",             # 递归修改所有者
            
            # 危险系统操作
            r"sudo\s+",                # 提权命令
            r"dd\s+if=/dev/zero",      # 磁盘写入
            r">\s*/dev/sda",           # 直接写入磁盘
            r"mkfs",                   # 格式化磁盘
            r"fdisk",                  # 分区操作
            
            # Fork bomb
            r":\(\)\{:\|:&};:",        # Fork bomb
            
            # 网络危险
            r"curl.*\|.*sh",           # 下载并执行
            r"wget.*\|.*sh",           # 下载并执行
            r"bash\s+-c\s+.*curl",     # 通过 bash 执行下载脚本
            
            # 进程操作
            r"kill\s+-9\s+1",          # 杀死 init 进程
            r"pkill\s+.*",             # 杀死进程（可能误杀）
            r"killall\s+.*",           # 杀死所有进程
        ]

    def execute(self, action: dict, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        """Execute a command in the local environment and return the result as a dict."""
        tool_name = action.get("tool_name", "bash")

        if tool_name == "list_directory":
            args = action.get("tool_args", {})
            path = args.get("path", ".")
            show_hidden = args.get("show_hidden", False)
            target_path = os.path.abspath(os.path.join(cwd or self.config.cwd or os.getcwd(), path))
            if platform.system() == "Windows":
                flags = "/a" if show_hidden else ""
                command = f'dir {flags} "{target_path}"'
            else:
                flags = "-la" if show_hidden else "-lh"
                command = f'ls {flags} "{target_path}"'
        else:
            command = action.get("command", "")

        # ========== 安全检查 ==========
        is_safe, reason = self._is_safe_command(command)
        if not is_safe:
            return {
                "output": f"[SECURITY BLOCKED] {reason}\n\n被阻止的命令: {command}",
                "returncode": 403,  # Forbidden
                "exception_info": f"Security policy violation: {reason}"
            }
        
        cwd = cwd or self.config.cwd or os.getcwd()
        try:
            result = subprocess.run(
                command,
                shell=True,
                text=True,
                cwd=cwd,
                env=os.environ | self.config.env,
                timeout=timeout or self.config.timeout,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            output = {"output": result.stdout, "returncode": result.returncode, "exception_info": ""}
        except Exception as e:
            raw_output = getattr(e, "output", None)
            raw_output = (
                raw_output.decode("utf-8", errors="replace") if isinstance(raw_output, bytes) else (raw_output or "")
            )
            output = {
                "output": raw_output,
                "returncode": -1,
                "exception_info": f"An error occurred while executing the command: {e}",
                "extra": {"exception_type": type(e).__name__, "exception": str(e)},
            }
        self._check_finished(output)
        return output

    def _check_finished(self, output: dict):
        """Raises Submitted if the output indicates task completion."""
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        if lines and lines[0].strip() == "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" and output["returncode"] == 0:
            submission = "".join(lines[1:])
            raise Submitted(
                {
                    "role": "exit",
                    "content": submission,
                    "extra": {"exit_status": "Submitted", "submission": submission},
                }
            )

    def get_template_vars(self, **kwargs) -> dict[str, Any]:
        return recursive_merge(self.config.model_dump(), platform.uname()._asdict(), os.environ, kwargs)

    def serialize(self) -> dict:
        return {
            "info": {
                "config": {
                    "environment": self.config.model_dump(mode="json"),
                    "environment_type": f"{self.__class__.__module__}.{self.__class__.__name__}",
                }
            }
        }
    
    def _is_safe_command(self, command: str) -> tuple[bool, str]:
        """检查命令是否安全。
        
        Returns:
            (是否安全, 拒绝原因)
        """
        if not self.config.enable_security:
            return True, ""
        
        # 合并默认黑名单和用户自定义黑名单
        blocked_patterns = list(self.default_blocked_patterns)
        if self.config.blocked_commands:
            blocked_patterns.extend(self.config.blocked_commands)
        
        # 1. 检查黑名单模式
        for pattern in blocked_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"匹配危险模式: '{pattern}'"
        
        # 2. 检查路径遍历（防止访问父目录）
        if ".." in command and re.search(r'\.\./', command):
            return False, "禁止访问上级目录 (..)"
        
        # 3. 检查命令长度（防止超长命令）
        if len(command) > 2000:
            return False, f"命令长度超过限制: {len(command)} > 2000"
        
        # 4. 检查危险字符组合
        dangerous_combos = [
            ("&&", r"\brm\b"),   # 组合命令中带删除
            ("||", r"\brm\b"),   # 或逻辑中带删除
            ("$(", r"\brm\b"),   # 命令替换中带删除
            ("`", r"\brm\b"),    # 反引号命令替换
        ]
        
        for combo, dangerous_cmd_re in dangerous_combos:
            if combo in command and re.search(dangerous_cmd_re, command.lower()):
                return False, f"危险的命令组合: {combo} 和 {dangerous_cmd_re}"
        
        return True, ""