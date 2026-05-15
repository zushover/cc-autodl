from datetime import datetime, timezone

import paramiko


class GPUCollector:
    def __init__(self, ssh_key_path: str, ssh_user: str = "root"):
        self.ssh_key_path = ssh_key_path
        self.ssh_user = ssh_user
        self._client: paramiko.SSHClient | None = None
        self._host: str = ""
        self._port: int = 22
        self._failures: int = 0

    def connect(self, host: str, port: int = 22):
        if self._client and host == self._host and port == self._port:
            return
        self.disconnect()
        self._host = host
        self._port = port
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=host,
            port=port,
            username=self.ssh_user,
            key_filename=self.ssh_key_path,
            timeout=10,
            banner_timeout=10,
        )

    def disconnect(self):
        if self._client:
            self._client.close()
            self._client = None
        self._failures = 0

    @property
    def reachable(self) -> bool:
        return self._failures < 3

    def collect(self, host: str, port: int) -> dict | None:
        try:
            self.connect(host, port)
            stdin, stdout, stderr = self._client.exec_command(
                "nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits",
                timeout=30,
            )
            line = stdout.read().decode().strip()
            if not line:
                self._failures += 1
                return None
            parts = [p.strip() for p in line.split(",")]
            result = {
                "util_percent": int(parts[0]),
                "mem_util_percent": int(parts[1]),
                "mem_used_gb": float(parts[2]) / 1024.0,
                "mem_total_gb": float(parts[3]) / 1024.0,
                "temp_c": int(parts[4]),
                "power_w": float(parts[5]),
            }

            stdin2, stdout2, stderr2 = self._client.exec_command(
                "nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits",
                timeout=30,
            )
            procs = stdout2.read().decode().strip()
            result["processes"] = []
            if procs:
                for pline in procs.split("\n"):
                    pparts = [p.strip() for p in pline.split(",")]
                    if len(pparts) >= 3:
                        result["processes"].append({
                            "pid": int(pparts[0]),
                            "name": pparts[1],
                            "mem_mb": int(pparts[2]),
                        })

            result["timestamp"] = datetime.now(timezone.utc).isoformat()
            self._failures = 0
            return result
        except Exception:
            self._failures += 1
            return None

    def collect_basic(self, host: str, port: int) -> dict | None:
        try:
            self.connect(host, port)
            stdin, stdout, stderr = self._client.exec_command(
                "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits",
                timeout=15,
            )
            line = stdout.read().decode().strip()
            if not line:
                self._failures += 1
                return None
            parts = [p.strip() for p in line.split(",")]
            result = {
                "util_percent": int(parts[0]),
                "mem_used_gb": float(parts[1]) / 1024.0,
                "mem_total_gb": float(parts[2]) / 1024.0,
                "temp_c": int(parts[3]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._failures = 0
            return result
        except Exception:
            self._failures += 1
            return None
