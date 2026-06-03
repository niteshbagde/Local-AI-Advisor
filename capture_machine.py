#!/usr/bin/env python3
"""
Machine Profiler for Local AI Ecosystem Planning
Run: python3 capture_machine.py
Outputs: machine_profile.json
"""

import json, platform, subprocess, sys, os, shutil
from pathlib import Path

def run(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, text=True).strip()
    except:
        return None

def get_cpu():
    info = {}
    s = platform.system()
    if s == "Linux":
        for line in (Path("/proc/cpuinfo").read_text().splitlines()):
            if "model name" in line:
                info["model"] = line.split(":")[1].strip(); break
        info["cores_physical"] = run("nproc --all")
        info["cores_logical"]  = run("nproc")
        info["arch"] = platform.machine()
        freq = run("lscpu | grep 'CPU MHz'")
        if freq: info["freq_mhz"] = freq.split(":")[1].strip()
    elif s == "Darwin":
        info["model"] = run("sysctl -n machdep.cpu.brand_string")
        info["cores_physical"] = run("sysctl -n hw.physicalcpu")
        info["cores_logical"]  = run("sysctl -n hw.logicalcpu")
        info["arch"] = platform.machine()
    elif s == "Windows":
        info["model"] = run('wmic cpu get Name /value').split("=")[-1] if run('wmic cpu get Name /value') else "Unknown"
        info["cores_logical"] = os.cpu_count()
        info["arch"] = platform.machine()
    return info

def get_ram():
    s = platform.system()
    if s == "Linux":
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                kb = int(line.split()[1])
                return {"total_gb": round(kb/1024/1024, 1)}
    elif s == "Darwin":
        b = run("sysctl -n hw.memsize")
        return {"total_gb": round(int(b)/1024**3, 1)} if b else {}
    elif s == "Windows":
        out = run("wmic computersystem get TotalPhysicalMemory /value")
        if out:
            b = int(out.split("=")[-1].strip())
            return {"total_gb": round(b/1024**3, 1)}
    return {}

def get_gpu():
    gpus = []
    s = platform.system()
    # NVIDIA
    nv = run("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader")
    if nv:
        for line in nv.splitlines():
            parts = line.split(",")
            gpus.append({"vendor":"NVIDIA","name":parts[0].strip(),
                         "vram":parts[1].strip(),"driver":parts[2].strip() if len(parts)>2 else "?"})
    # AMD ROCm
    rocm = run("rocm-smi --showproductname 2>/dev/null")
    if rocm:
        for line in rocm.splitlines():
            if "GPU" in line and "Card" in line:
                gpus.append({"vendor":"AMD","name":line.strip(),"vram":"check rocm-smi"})
    # Apple Silicon
    if s == "Darwin":
        chip = run("sysctl -n machdep.cpu.brand_string")
        if chip and ("M1" in chip or "M2" in chip or "M3" in chip or "M4" in chip):
            mem = run("sysctl -n hw.memsize")
            gpus.append({"vendor":"Apple","name":chip,"vram":f"Unified {round(int(mem)/1024**3,1)}GB","unified":True})
    # Fallback lspci
    if not gpus and s == "Linux":
        lspci = run("lspci | grep -i 'vga\\|3d\\|display'")
        if lspci:
            for line in lspci.splitlines():
                gpus.append({"vendor":"Unknown","name":line.strip()})
    if not gpus:
        gpus.append({"vendor":"None/Integrated","name":"No dedicated GPU detected"})
    return gpus

def get_disk():
    total, used, free = shutil.disk_usage("/")
    return {
        "total_gb": round(total/1024**3, 1),
        "used_gb":  round(used/1024**3, 1),
        "free_gb":  round(free/1024**3, 1)
    }

def get_os():
    return {
        "system":   platform.system(),
        "release":  platform.release(),
        "version":  platform.version(),
        "machine":  platform.machine(),
        "python":   platform.python_version()
    }

def get_tools():
    tools = {}
    for t in ["git","docker","python3","pip3","node","npm","curl","wget","cmake","gcc","make"]:
        tools[t] = shutil.which(t) is not None
    # CUDA
    tools["cuda"] = run("nvcc --version") is not None
    tools["ollama"] = shutil.which("ollama") is not None
    tools["lm_studio"] = Path(os.path.expanduser("~/.lmstudio")).exists() or Path("/Applications/LM Studio.app").exists()
    return tools

def score_hardware(ram, gpus):
    """Score 1-5 for AI workload capability"""
    ram_gb = ram.get("total_gb", 0)
    has_gpu = any(g.get("vendor") not in ["None/Integrated"] for g in gpus)
    has_nvidia = any(g.get("vendor") == "NVIDIA" for g in gpus)
    has_apple = any(g.get("vendor") == "Apple" for g in gpus)

    score = 1
    if ram_gb >= 8:  score = 2
    if ram_gb >= 16: score = 3
    if ram_gb >= 32: score = 4
    if ram_gb >= 64: score = 5
    if has_nvidia:   score = min(5, score + 1)
    if has_apple:    score = min(5, score + 1)
    return score

def main():
    print("🔍 Scanning your machine for AI ecosystem planning...\n")

    profile = {
        "os":    get_os(),
        "cpu":   get_cpu(),
        "ram":   get_ram(),
        "gpu":   get_gpu(),
        "disk":  get_disk(),
        "tools": get_tools(),
    }
    profile["ai_score"] = score_hardware(profile["ram"], profile["gpu"])

    out = Path("machine_profile.json")
    out.write_text(json.dumps(profile, indent=2))

    print("✅ Profile saved to machine_profile.json\n")
    print("="*55)
    print(f"  OS       : {profile['os']['system']} {profile['os']['release']}")
    print(f"  CPU      : {profile['cpu'].get('model','?')}")
    print(f"  RAM      : {profile['ram'].get('total_gb','?')} GB")
    print(f"  GPU      : {profile['gpu'][0]['name']}")
    print(f"  Disk Free: {profile['disk']['free_gb']} GB")
    print(f"  AI Score : {'⭐'*profile['ai_score']} ({profile['ai_score']}/5)")
    print("="*55)
    print("\n📋 Copy machine_profile.json contents and paste into")
    print("   the AI Ecosystem Advisor dashboard for recommendations.")
    print("\nJSON output:\n")
    print(json.dumps(profile, indent=2))

if __name__ == "__main__":
    main()
