#!/usr/bin/env python3
"""
Windows Admin & Power-User Toolkit v2.5
=======================================
Interface interativa de terminal (CLI/TUI) para rotinas administrativas de baixo nível,
diagnóstico de hardware, segurança, manutenção avançada, análise forense e virtualização.

Requisitos: Windows 10/11 x64
Uso:        python win_toolkit.py [--dry-run]
"""

from __future__ import annotations

import argparse
import ctypes
import datetime
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configurações Globais e Flags
# ---------------------------------------------------------------------------

VERSION = "2.5.0"
DRY_RUN = False
LOG_FILE = os.path.join(os.path.expanduser("~"), "win_toolkit_log.txt")


# ---------------------------------------------------------------------------
# Suporte a Cores ANSI / TUI
# ---------------------------------------------------------------------------

class Color:
    """Controle de cores e estilos ANSI com suporte a Windows Terminal VT100."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Cores de Primeiro Plano
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    @classmethod
    def enable_vt_support(cls) -> None:
        """Habilita Virtual Terminal Processing no console nativo do Windows 10/11."""
        if os.name == "nt":
            try:
                kernel32 = ctypes.windll.kernel32
                h_stdout = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
                mode = ctypes.c_ulong()
                kernel32.GetConsoleMode(h_stdout, ctypes.byref(mode))
                # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
                mode.value |= 0x0004
                kernel32.SetConsoleMode(h_stdout, mode)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Elevação de Privilégios (UAC)
# ---------------------------------------------------------------------------

def is_admin() -> bool:
    """Verifica se o processo atual possui privilégios de Administrador."""
    if DRY_RUN or os.name != "nt":
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin() -> None:
    """Reabre o próprio script em um processo elevado solicitando o prompt UAC."""
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{sys.argv[0]}" {params}', None, 1
    )
    sys.exit(0)


def ensure_admin() -> None:
    """Garante execução em ambiente administrativo ou encerra com aviso."""
    if DRY_RUN:
        return
    if os.name != "nt":
        print(f"{Color.RED}[!] Este programa foi desenvolvido para Windows 10/11.{Color.RESET}")
        print(f"{Color.YELLOW}[*] Use a flag --dry-run para testar em outros sistemas operacionais.{Color.RESET}")
        sys.exit(1)
    if not is_admin():
        print(f"{Color.YELLOW}[!] Privilégios de Administrador necessários. Solicitando elevação (UAC)...{Color.RESET}")
        relaunch_as_admin()


# ---------------------------------------------------------------------------
# Execução de Comandos, Validação e Logging
# ---------------------------------------------------------------------------

def append_to_log(text: str) -> None:
    """Registra eventos de auditoria com timestamp."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"[{timestamp}] {text}\n")
    except Exception:
        pass


def run_powershell(command: str, live: bool = True, timeout: Optional[int] = None) -> tuple[int, str]:
    """
    Executa um comando no PowerShell com bypass de ExecutionPolicy.
    Retorna uma tupla (returncode, output_text).
    """
    append_to_log(f"$ {command}")

    if DRY_RUN:
        print(f"{Color.CYAN}[DRY-RUN Simulação]{Color.RESET} {Color.BOLD}{command}{Color.RESET}")
        return (0, "[DRY-RUN: Comando simulado com sucesso]")

    full_cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-Command", command,
    ]

    try:
        if live:
            proc = subprocess.run(full_cmd, timeout=timeout)
            return proc.returncode, ""
        else:
            proc = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )
            output = proc.stdout + (proc.stderr or "")
            if proc.stdout:
                print(proc.stdout)
            if proc.stderr:
                print(f"{Color.RED}{proc.stderr}{Color.RESET}")
            append_to_log(f"OUTPUT:\n{output}")
            return proc.returncode, output
    except subprocess.TimeoutExpired:
        msg = f"{Color.RED}[ERRO] O comando excedeu o tempo limite de execução ({timeout}s).{Color.RESET}"
        print(msg)
        append_to_log(f"TIMEOUT: {timeout}s")
        return (124, "Timeout")
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}[!] Execução interrompida pelo usuário.{Color.RESET}")
        append_to_log("INTERRUPTED BY USER")
        return (130, "KeyboardInterrupt")
    except Exception as e:
        msg = f"{Color.RED}[ERRO DE EXECUÇÃO] {e}{Color.RESET}"
        print(msg)
        append_to_log(f"ERROR: {e}")
        return (1, str(e))


def confirm(message: str) -> bool:
    """Exibe confirmação segura do usuário."""
    try:
        resp = input(f"{Color.YELLOW}{message} (s/N): {Color.RESET}").strip().lower()
        return resp in ("s", "sim", "y", "yes")
    except KeyboardInterrupt:
        print()
        return False


def sanitize_input(val: str, pattern: str, error_msg: str = "Entrada inválida.") -> Optional[str]:
    """Valida e sanitiza strings contra injeção de parâmetros maliciosos."""
    cleaned = val.strip()
    if not cleaned:
        return None
    if re.match(pattern, cleaned):
        return cleaned
    print(f"{Color.RED}[!] {error_msg}{Color.RESET}")
    return None


def escape_ps_string(val: str) -> str:
    """Escapa aspas simples para interpolação segura no PowerShell."""
    return val.replace("'", "''")


# ---------------------------------------------------------------------------
# Estrutura de Dados e Dataclasses
# ---------------------------------------------------------------------------

class ActionKind(Enum):
    NORMAL = "normal"
    DANGEROUS = "dangerous"
    INTERACTIVE = "interactive"
    KIT = "kit"


@dataclass
class CommandItem:
    title: str
    command: Optional[str]
    kind: ActionKind
    description: str
    action_key: Optional[str] = None


@dataclass
class Category:
    name: str
    items: List[CommandItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ações Especiais e Interativas
# ---------------------------------------------------------------------------

def action_kill_pid() -> None:
    pid = input(f"{Color.CYAN}PID do processo a finalizar: {Color.RESET}").strip()
    clean_pid = sanitize_input(pid, r"^\d+$", "O PID deve conter apenas números.")
    if clean_pid:
        if confirm(f"Tem certeza que deseja forçar o encerramento do PID {clean_pid}?"):
            run_powershell(f"Stop-Process -Id {clean_pid} -Force")


def action_kill_name() -> None:
    name = input(f"{Color.CYAN}Nome do processo (ex: chrome, notepad): {Color.RESET}").strip()
    clean_name = sanitize_input(name, r"^[a-zA-Z0-9_\-\.]+$", "Nome de processo inválido.")
    if clean_name:
        if confirm(f"Tem certeza que deseja encerrar todos os processos com nome '{clean_name}'?"):
            escaped = escape_ps_string(clean_name)
            run_powershell(f"Stop-Process -Name '{escaped}' -Force")


def action_list_dlls() -> None:
    pid = input(f"{Color.CYAN}PID do processo para inspecionar módulos/DLLs: {Color.RESET}").strip()
    clean_pid = sanitize_input(pid, r"^\d+$", "O PID deve conter apenas números.")
    if clean_pid:
        cmd = f"(Get-Process -Id {clean_pid}).Modules | Select-Object ModuleName,FileName,Size | Format-Table -AutoSize"
        run_powershell(cmd)


def action_test_port() -> None:
    host = input(f"{Color.CYAN}Host ou IP de destino (ex: 8.8.8.8, github.com): {Color.RESET}").strip()
    clean_host = sanitize_input(host, r"^[a-zA-Z0-9\.\-_]+$", "Host/IP inválido.")
    if not clean_host:
        return

    port = input(f"{Color.CYAN}Porta TCP (ex: 443, 22, 80): {Color.RESET}").strip()
    clean_port = sanitize_input(port, r"^\d+$", "Porta deve ser numérica.")
    if clean_port and 1 <= int(clean_port) <= 65535:
        escaped_host = escape_ps_string(clean_host)
        run_powershell(f"Test-NetConnection -ComputerName '{escaped_host}' -Port {clean_port} -InformationLevel Detailed")
    else:
        print(f"{Color.RED}[!] A porta deve estar no intervalo de 1 a 65535.{Color.RESET}")


def action_calc_hash() -> None:
    path = input(f"{Color.CYAN}Caminho completo do arquivo: {Color.RESET}").strip().strip('"').strip("'")
    if not path:
        return
    if os.path.isfile(path) or DRY_RUN:
        escaped_path = escape_ps_string(path)
        run_powershell(f"Get-FileHash -Path '{escaped_path}' -Algorithm SHA256 | Format-List")
    else:
        print(f"{Color.RED}[!] Arquivo não encontrado no caminho especificado.{Color.RESET}")


def action_manage_service() -> None:
    srv = input(f"{Color.CYAN}Nome do Serviço (Service Name): {Color.RESET}").strip()
    clean_srv = sanitize_input(srv, r"^[a-zA-Z0-9_\-\. \$]+$", "Nome de serviço inválido.")
    if not clean_srv:
        return

    print(f"\n{Color.BOLD}Operações para o serviço '{clean_srv}':{Color.RESET}")
    print(" 1) Iniciar serviço")
    print(" 2) Parar serviço")
    print(" 3) Reiniciar serviço")
    print(" 4) Consultar Status Completo")
    print(" 0) Cancelar")
    op = input(f"{Color.CYAN}Opção: {Color.RESET}").strip()

    escaped = escape_ps_string(clean_srv)
    if op == "1":
        run_powershell(f"Start-Service -Name '{escaped}'")
    elif op == "2":
        if confirm(f"Deseja parar o serviço '{clean_srv}'?"):
            run_powershell(f"Stop-Service -Name '{escaped}' -Force")
    elif op == "3":
        run_powershell(f"Restart-Service -Name '{escaped}' -Force")
    elif op == "4":
        run_powershell(f"Get-Service -Name '{escaped}' | Select-Object * | Format-List")


def action_create_restore_point() -> None:
    """Cria um Ponto de Restauração do Sistema com confirmação."""
    print(f"{Color.YELLOW}[*] Criando Ponto de Restauração do Sistema...{Color.RESET}")
    cmd = 'Checkpoint-Computer -Description "WinToolkit Backup Manual" -RestorePointType "MODIFY_SETTINGS"'
    run_powershell(cmd)


def action_system_cleanup() -> None:
    """Rotina integrada de limpeza de arquivos temporários, caches e lixeira."""
    print(f"\n{Color.BOLD}{Color.YELLOW}=== ROTINA DE LIMPEZA E OTIMIZAÇÃO DO SISTEMA ==={Color.RESET}\n")
    print("Esta rotina limpará:")
    print(" • Arquivos temporários do usuário (%TEMP%) e do sistema (C:\\Windows\\Temp)")
    print(" • Arquivos da Lixeira do Windows")
    print(" • Cache de arquivos Prefetch")
    print(" • Cache de downloads do Windows Update (SoftwareDistribution\\Download)")
    print()

    if not confirm("Deseja executar a limpeza profunda agora?"):
        print("Operação cancelada.")
        return

    commands = [
        ("Limpando Lixeira do Windows...", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"),
        ("Limpando arquivos temporários do usuário (%TEMP%)...", "Remove-Item -Path \"$env:TEMP\\*\" -Recurse -Force -ErrorAction SilentlyContinue"),
        ("Limpando pasta temporária do Windows...", "Remove-Item -Path \"$env:SystemRoot\\Temp\\*\" -Recurse -Force -ErrorAction SilentlyContinue"),
        ("Limpando pasta Prefetch...", "Remove-Item -Path \"$env:SystemRoot\\Prefetch\\*\" -Recurse -Force -ErrorAction SilentlyContinue"),
        ("Limpando cache do Windows Update...", "net stop wuauserv; Remove-Item -Path \"$env:SystemRoot\\SoftwareDistribution\\Download\\*\" -Recurse -Force -ErrorAction SilentlyContinue; net start wuauserv"),
    ]

    for desc, cmd in commands:
        print(f"\n{Color.CYAN}>> {desc}{Color.RESET}")
        run_powershell(cmd)

    print(f"\n{Color.GREEN}[✓] Limpeza do sistema concluída com sucesso!{Color.RESET}")


def action_view_logs() -> None:
    """Visualizador de log de auditoria integrado."""
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print(f"{Color.BOLD}{'=' * 75}{Color.RESET}")
        print(f"{Color.GREEN} AUDITORIA & VISUALIZADOR DE LOGS: {LOG_FILE}{Color.RESET}")
        print(f"{Color.BOLD}{'=' * 75}{Color.RESET}")

        if not os.path.exists(LOG_FILE):
            print(f"{Color.YELLOW}Nenhum registro de log encontrado ainda.{Color.RESET}")
        else:
            try:
                with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                total_lines = len(lines)
                print(f"Total de linhas registradas: {Color.CYAN}{total_lines}{Color.RESET}\n")
                last_lines = lines[-35:]
                print("".join(last_lines))
            except Exception as e:
                print(f"{Color.RED}Erro ao ler arquivo de log: {e}{Color.RESET}")

        print(f"{Color.BOLD}{'=' * 75}{Color.RESET}")
        print(" [L] Limpar todo o log  |  [0] Voltar ao Menu")
        choice = input(f"\n{Color.CYAN}Opção: {Color.RESET}").strip().lower()
        if choice in ("0", ""):
            break
        elif choice == "l":
            if confirm("Tem certeza que deseja apagar todos os registros do log?"):
                try:
                    with open(LOG_FILE, "w", encoding="utf-8") as f:
                        f.write("")
                    print(f"{Color.GREEN}[✓] Log limpo.{Color.RESET}")
                except Exception as e:
                    print(f"{Color.RED}Erro ao limpar log: {e}{Color.RESET}")
                input("Pressione Enter...")


def export_diagnostic_kit(name: str, desc: str, kit_commands: str) -> None:
    """Executa um kit de diagnóstico e exporta o relatório consolidado."""
    print(f"\n{Color.BOLD}{Color.CYAN}Executando Kit de Diagnóstico: {desc}{Color.RESET}\n")
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"Relatorio_{name}_{timestamp_str}.md"
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    if not os.path.exists(desktop_path):
        desktop_path = os.path.expanduser("~")
    target_file = os.path.join(desktop_path, report_filename)

    report_content = [
        f"# Relatório de Diagnóstico Técnico - {desc}",
        f"**Data de Geração:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Host:** {os.environ.get('COMPUTERNAME', 'Localhost')}",
        f"**Versão Toolkit:** {VERSION}",
        "\n---\n"
    ]

    for line in kit_commands.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        print(f"{Color.CYAN}$ {line}{Color.RESET}")
        code, out = run_powershell(line, live=False)
        report_content.append(f"### `$ {line}`")
        report_content.append("```text")
        report_content.append(out.strip() if out else "[Sem saída]")
        report_content.append("```\n")

    try:
        with open(target_file, "w", encoding="utf-8") as rf:
            rf.write("\n".join(report_content))
        print(f"\n{Color.GREEN}[✓] Relatório exportado com sucesso em:{Color.RESET} {Color.BOLD}{target_file}{Color.RESET}")
    except Exception as e:
        print(f"{Color.RED}[!] Falha ao salvar arquivo de relatório: {e}{Color.RESET}")


SPECIAL_ACTIONS: Dict[str, Callable[[], None]] = {
    "kill_pid": action_kill_pid,
    "kill_name": action_kill_name,
    "list_dlls": action_list_dlls,
    "test_port": action_test_port,
    "calc_hash": action_calc_hash,
    "manage_service": action_manage_service,
    "create_restore_point": action_create_restore_point,
    "system_cleanup": action_system_cleanup,
    "view_logs": action_view_logs,
}


# ---------------------------------------------------------------------------
# Catálogo de Comandos e Categorias
# ---------------------------------------------------------------------------

KITS_RAW = {
    "KIT_REDE_PRO": """
Get-NetIPConfiguration
ping -n 2 1.1.1.1
Resolve-DnsName google.com
Get-NetRoute -AddressFamily IPv4
Get-NetTCPConnection | Where-Object State -eq 'Listen' | Select-Object LocalAddress,LocalPort,OwningProcess
netstat -e
""",
    "KIT_SECURITY": """
whoami /all
manage-bde -status
Get-Tpm
Get-NetFirewallProfile | Select-Object Name,Enabled
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4624} -MaxEvents 5 -ErrorAction SilentlyContinue
""",
    "KIT_HARDWARE": """
Get-PhysicalDisk | Select-Object DeviceId,FriendlyName,MediaType,HealthStatus
Get-Volume
Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed
Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2} -MaxEvents 10 -ErrorAction SilentlyContinue
""",
}

CATEGORIES_DATA: List[Category] = [
    Category("1. Informações do Sistema & Hardware", [
        CommandItem("Versão do Windows (winver)", "winver", ActionKind.NORMAL,
                    "Abre a interface gráfica com a compilação exata do kernel NT."),
        CommandItem("Informações completas (systeminfo)", "systeminfo", ActionKind.NORMAL,
                    "Exibe dados de BIOS, Hyper-V, placa-mãe, memória física e hotfixes."),
        CommandItem("Info do Sistema Detalhada (PowerShell)", "Get-ComputerInfo", ActionKind.NORMAL,
                    "Coleta objetos estruturados de hardware, SO e patches via CIM."),
        CommandItem("Topologia de CPU (Cores/Threads/Cache)",
                    "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,L2CacheSize,L3CacheSize | Format-List",
                    ActionKind.NORMAL, "Lista arquitetura da CPU, núcleos físicos, threads e caches L2/L3."),
        CommandItem("Slots de RAM, Barramento e Frequência",
                    "Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator,Capacity,Speed,ConfiguredClockSpeed,Manufacturer,PartNumber | Format-Table -AutoSize",
                    ActionKind.NORMAL, "Exibe cada pente de memória, barramento (MHz) e Part Number."),
        CommandItem("Placa-Mãe e Firmware",
                    "Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product,SerialNumber,Version | Format-List",
                    ActionKind.NORMAL, "Inspeciona modelo da motherboard e versão de fabricação."),
        CommandItem("Parâmetros da BIOS/UEFI",
                    "Get-CimInstance Win32_BIOS | Select-Object SMBIOSBIOSVersion,ReleaseDate,Manufacturer | Format-List",
                    ActionKind.NORMAL, "Exibe versão do microcódigo/firmware UEFI instalado."),
        CommandItem("GPU e Driver de Vídeo",
                    "Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM,VideoProcessor | Format-List",
                    ActionKind.NORMAL, "Consulta modelo da placa de vídeo dedicada/integrada e versão do driver."),
    ]),

    Category("2. Processos, Threads e Análise Forense", [
        CommandItem("Listar processos por consumo de CPU",
                    "Get-Process | Sort-Object CPU -Descending | Select-Object -First 20 Id,ProcessName,CPU,WorkingSet64 | Format-Table -AutoSize",
                    ActionKind.NORMAL, "Exibe o Top 20 de processos com maior consumo de ciclos de processamento e RAM."),
        CommandItem("Mapeamento Processo -> Serviços", "tasklist /svc", ActionKind.NORMAL,
                    "Identifica quais serviços do Windows rodam dentro de cada processo svchost.exe."),
        CommandItem("Processos com conexão TCP aberta",
                    "Get-NetTCPConnection | Where-Object State -eq 'Established' | Select-Object LocalAddress,LocalPort,RemoteAddress,RemotePort,OwningProcess | Sort-Object OwningProcess | Format-Table -AutoSize",
                    ActionKind.NORMAL, "Associa sockets TCP ativos diretamente ao PID do processo responsável."),
        CommandItem("Investigar DLLs carregadas por um processo", None, ActionKind.INTERACTIVE,
                    "Lista todos os módulos/DLLs mapeados no espaço de memória de um PID específico.",
                    action_key="list_dlls"),
        CommandItem("Finalizar processo por PID", None, ActionKind.INTERACTIVE,
                    "Envia sinal de término imediato forçado para o PID indicado.",
                    action_key="kill_pid"),
        CommandItem("Finalizar processo por Nome", None, ActionKind.INTERACTIVE,
                    "Mata todas as árvores de processos correspondentes ao executável.",
                    action_key="kill_name"),
    ]),

    Category("3. Armazenamento, SMART e NVMe", [
        CommandItem("Listar discos físicos e tipo de mídia (SSD/HDD/NVMe)",
                    "Get-PhysicalDisk | Select-Object DeviceId,FriendlyName,MediaType,BusType,HealthStatus,OperationalStatus | Format-Table -AutoSize",
                    ActionKind.NORMAL, "Inspeciona a integridade SMART básica, tipo de barramento e estado operacional do disco."),
        CommandItem("Volumes e Espaço Livre",
                    "Get-Volume | Select-Object DriveLetter,FileSystemLabel,FileSystem,SizeRemaining,Size | Format-Table -AutoSize",
                    ActionKind.NORMAL, "Exibe tabela de partições montadas e espaço disponível em bytes."),
        CommandItem("Análise de Partições (GPT/MBR)",
                    "Get-Disk | Select-Object Number,FriendlyName,PartitionStyle,OperationalStatus,TotalSize | Format-Table -AutoSize",
                    ActionKind.NORMAL, "Informa o esquema de particionamento (GPT/MBR) de cada disco físico."),
        CommandItem("Verificar integridade C: (somente leitura)", "chkdsk C: /scan", ActionKind.NORMAL,
                    "Executa varredura online do sistema de arquivos NTFS sem desmontar a unidade."),
        CommandItem("Agendar reparo profundo de disco (CHKDSK /F /R)", "chkdsk C: /f /r", ActionKind.DANGEROUS,
                    "Agenda para o próximo boot a correção de clusters e recuperação de setores defeituosos."),
        CommandItem("Otimização/TRIM em SSDs", "Optimize-Volume -DriveLetter C -Defrag -Verbose", ActionKind.NORMAL,
                    "Executa o comando TRIM para liberar blocos não utilizados no SSD."),
        CommandItem("Abrir DiskPart (CLI)", "diskpart", ActionKind.DANGEROUS,
                    "Abre a ferramenta nativa de baixo nível para particionamento e controle de volumes."),
    ]),

    Category("4. Reparo do Sistema e Component Store (WinSxS)", [
        CommandItem("Verificar integridade de arquivos protegidos (SFC)", "sfc /scannow", ActionKind.NORMAL,
                    "Analisa a assinatura e integridade de todos os binários essenciais do sistema operacional."),
        CommandItem("Verificar status da imagem (DISM CheckHealth)", "DISM /Online /Cleanup-Image /CheckHealth", ActionKind.NORMAL,
                    "Consulta flags de corrupção já identificadas pelo kernel."),
        CommandItem("Varredura profunda do repositório WinSxS (ScanHealth)", "DISM /Online /Cleanup-Image /ScanHealth", ActionKind.NORMAL,
                    "Executa hash check completo do repositório de componentes contra corrupções silenciosas."),
        CommandItem("Reparação da imagem via Windows Update (RestoreHealth)", "DISM /Online /Cleanup-Image /RestoreHealth", ActionKind.NORMAL,
                    "Restaura pacotes corrompidos baixando fontes oficiais da Microsoft."),
        CommandItem("Limpeza do repositório WinSxS (ResetBase)", "DISM /Online /Cleanup-Image /StartComponentCleanup /ResetBase", ActionKind.DANGEROUS,
                    "Remove versões antigas de atualizações substituídas, liberando espaço em disco."),
    ]),

    Category("5. Rede Avançada e Sockets", [
        CommandItem("Configuração de interfaces e IPs", "Get-NetIPConfiguration -Detailed", ActionKind.NORMAL,
                    "Lista endereços IPv4/IPv6, gateways, rotas e servidores DNS configurados."),
        CommandItem("Tabela de Sockets Abertos e Portas em Escuta", "netstat -ano -p tcp", ActionKind.NORMAL,
                    "Lista todas as conexões TCP ativas e portas em estado LISTENING com seus respectivos PIDs."),
        CommandItem("Tabela de Roteamento IP (Kernel)", "route print", ActionKind.NORMAL,
                    "Exibe as tabelas de rotas IPv4 e IPv6 gerenciadas pela pilha TCP/IP."),
        CommandItem("Tabela ARP (Mapeamento IP -> MAC)", "arp -a", ActionKind.NORMAL,
                    "Mostra a tabela de resolução de camada 2 (Data Link) da sub-rede local."),
        CommandItem("Limpar Cache DNS do Host", "Clear-DnsClientCache", ActionKind.NORMAL,
                    "Descarta registros resolvidos em cache pelo serviço DNS Client."),
        CommandItem("Testar Latência e Portas (Test-NetConnection)", None, ActionKind.INTERACTIVE,
                    "Executa handshake TCP completo contra host e porta arbitrários.",
                    action_key="test_port"),
        CommandItem("Estatísticas de Protocolos TCP/IP", "netstat -s", ActionKind.NORMAL,
                    "Exibe métricas detalhadas de pacotes transmitidos, erros, retransmissões e conexões abortadas."),
        CommandItem("Reset Completo da Pilha de Rede (Winsock + IP)", "netsh winsock reset; netsh int ip reset", ActionKind.DANGEROUS,
                    "Restaura buffers de rede, catálogos LSP do Winsock e configurações de TCP/IP aos padrões de fábrica."),
    ]),

    Category("6. Segurança, Criptografia e Políticas", [
        CommandItem("Calcular Hash SHA-256 de arquivo", None, ActionKind.INTERACTIVE,
                    "Calcula o checksum criptográfico (SHA256) de um arquivo para verificar autenticidade.",
                    action_key="calc_hash"),
        CommandItem("Criar Ponto de Restauração do Sistema", None, ActionKind.INTERACTIVE,
                    "Gera um ponto de restauração prévio no Windows para proteção contra falhas.",
                    action_key="create_restore_point"),
        CommandItem("Status do BitLocker e TPM", "manage-bde -status", ActionKind.NORMAL,
                    "Consulta algoritmos de cifra, estado de bloqueio e método de proteção dos volumes."),
        CommandItem("Status do Chip TPM (Segurança de Hardware)", "Get-Tpm", ActionKind.NORMAL,
                    "Verifica se o TPM está ativado, pronto para uso e sua versão de especificação (2.0)."),
        CommandItem("Status de Isolamento de Núcleo (VBS / Credential Guard)",
                    "Get-CimInstance -ClassName Win32_DeviceGuard -Namespace root/Microsoft/Windows/DeviceGuard | Select-Object SecurityServicesConfigured,SecurityServicesRunning | Format-List",
                    ActionKind.NORMAL, "Analisa a segurança baseada em virtualização (VBS) e mitigação contra roubo de hashes."),
        CommandItem("Auditoria de Certificados na Raiz do Sistema", "Get-ChildItem -Path Cert:\\LocalMachine\\Root | Format-Table -AutoSize", ActionKind.NORMAL,
                    "Lista as Autoridades Certificadoras Raiz Confiáveis instaladas no armazenamento local."),
        CommandItem("Políticas de Grupo Aplicadas (GPO Result)", "gpresult /r", ActionKind.NORMAL,
                    "Extrai os escopos de gerenciamento e GPOs que incidem sobre o computador e usuário."),
        CommandItem("Varredura Rápida do Windows Defender (CLI)", "Start-MpScan -ScanType QuickScan", ActionKind.NORMAL,
                    "Dispara uma rotina de verificação rápida do antivírus via PowerShell."),
        CommandItem("Atualizar Assinaturas do Windows Defender", "Update-MpSignature", ActionKind.NORMAL,
                    "Força o download dos arquivos de definição de malwares mais recentes."),
    ]),

    Category("7. Manutenção, Inicialização e Serviços", [
        CommandItem("Limpeza de Disco e Cache do Sistema (Profunda)", None, ActionKind.INTERACTIVE,
                    "Limpa arquivos temporários, Prefetch, Lixeira e cache do Windows Update.",
                    action_key="system_cleanup"),
        CommandItem("Listar Programas de Inicialização Automática",
                    "Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location,User | Format-Table -AutoSize",
                    ActionKind.NORMAL, "Lista todos os aplicativos configurados para iniciar com o Windows."),
        CommandItem("Listar drivers carregados no Kernel", "driverquery /fo TABLE", ActionKind.NORMAL,
                    "Exibe todos os módulos .sys em execução no ring 0."),
        CommandItem("Drivers de Terceiros instalados (Dism /Get-Drivers)", "dism /online /get-drivers /format:table", ActionKind.NORMAL,
                    "Lista exclusivamente drivers OEM (não nativos da Microsoft) instalados no sistema."),
        CommandItem("Dispositivos com Falha no Gerenciador de Dispositivos", "Get-PnpDevice | Where-Object Status -ne 'OK' | Format-Table -AutoSize", ActionKind.NORMAL,
                    "Localiza hardwares com problemas de inicialização ou sem driver correspondente."),
        CommandItem("Configuração de Dumps de Memória (BSOD CrashDump)",
                    "Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\CrashControl' | Format-List",
                    ActionKind.NORMAL, "Exibe o tipo de dump gerado em caso de tela azul (Small, Kernel ou Complete Dump)."),
        CommandItem("Iniciar / Parar / Consultar Serviços", None, ActionKind.INTERACTIVE,
                    "Permite alterar o ciclo de vida de qualquer serviço registrado no SCM.",
                    action_key="manage_service"),
    ]),

    Category("8. Subsistemas, DevTools e Virtualização", [
        CommandItem("Status das Distribuições WSL", "wsl --list --verbose", ActionKind.NORMAL,
                    "Lista as distribuições Linux instaladas, versão do subsistema (WSL 1 vs WSL 2) e estado."),
        CommandItem("Encerrar todas as instâncias WSL (Shutdown)", "wsl --shutdown", ActionKind.NORMAL,
                    "Termina a máquina virtual leve do WSL2 liberando toda a memória RAM alocada."),
        CommandItem("Verificar Recursos de Virtualização Hyper-V", "Get-WindowsOptionalFeature -Online | Where-Object FeatureName -like '*Hyper-V*'", ActionKind.NORMAL,
                    "Verifica se os módulos do hypervisor tipo-1 nativo estão habilitados."),
        CommandItem("Atualizar todos os pacotes instalados via WinGet", "winget upgrade --all --include-unknown", ActionKind.DANGEROUS,
                    "Verifica e atualiza todos os programas e bibliotecas gerenciados pelo Windows Package Manager."),
        CommandItem("Habilitar WinRM (PowerShell Remoting)", "Enable-PSRemoting -Force", ActionKind.DANGEROUS,
                    "Configura a máquina para receber comandos remotos via WS-Management."),
    ]),

    Category("9. Utilitários e Scripts Remotos da Comunidade", [
        CommandItem("Microsoft Activation Scripts (MAS)", "irm https://get.activated.win | iex", ActionKind.DANGEROUS,
                    "Interface comunitária open-source para gerenciamento e ativação de licenças HWID/KMS38."),
        CommandItem("Chris Titus Tech WinUtil", "irm https://christitus.com/win | iex", ActionKind.DANGEROUS,
                    "Ferramenta para tweaks do sistema, debloat, desativação de telemetria e instalação em massa."),
        CommandItem("Win-Debloat (raphi.re)", "& ([scriptblock]::Create((irm 'https://debloat.raphi.re/')))", ActionKind.DANGEROUS,
                    "Automação focada na remoção de bloatware, otimização de privacidade e corte de serviços nativos."),
    ]),

    Category("10. Kits de Diagnóstico Integrado & Exportação", [
        CommandItem("Kit Completo: Diagnóstico de Rede & DNS", "KIT_REDE_PRO", ActionKind.KIT,
                    "Executa coleta de IPs, testes ICMP, resolução DNS, rotas, conexões ativas e estatísticas."),
        CommandItem("Kit Completo: Auditoria Forense e Segurança", "KIT_SECURITY", ActionKind.KIT,
                    "Gera relatório de privilégios (whoami /all), auditoria de portas, VBS, drivers e firewall."),
        CommandItem("Kit Completo: Triage de Saúde de Hardware e Disco", "KIT_HARDWARE", ActionKind.KIT,
                    "Coleta integridade SMART, partições, topologia de CPU, uso de RAM e erros críticos nos logs."),
    ]),
]


# ---------------------------------------------------------------------------
# Manual Técnico & Documentação
# ---------------------------------------------------------------------------

def show_documentation() -> None:
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print(f"{Color.BOLD}{'=' * 75}{Color.RESET}")
        print(f"{Color.CYAN} MANUAL TÉCNICO & DOCUMENTAÇÃO DE COMANDOS{Color.RESET}")
        print(f"{Color.BOLD}{'=' * 75}{Color.RESET}")
        print(" Selecione a categoria para consultar detalhes arquiteturais:\n")
        for i, cat in enumerate(CATEGORIES_DATA, start=1):
            print(f" {Color.BOLD}{i:2d}){Color.RESET} {cat.name}")
        print(f"  {Color.YELLOW}A){Color.RESET} Ver documentação completa de TODAS as opções")
        print(f"  {Color.GREEN}0){Color.RESET} Retornar ao menu principal")
        print(f"{Color.BOLD}{'=' * 75}{Color.RESET}")

        try:
            choice = input(f"\n{Color.CYAN}Opção: {Color.RESET}").strip().lower()
        except KeyboardInterrupt:
            break

        if choice in ("0", ""):
            break
        elif choice == "a":
            os.system("cls" if os.name == "nt" else "clear")
            for cat in CATEGORIES_DATA:
                print(f"\n{Color.BOLD}{'=' * 75}\n {cat.name.upper()}\n{'=' * 75}{Color.RESET}")
                for item in cat.items:
                    cmd_str = item.command if item.command else f"[Rotina Especial: {item.action_key}]"
                    tag = f" {Color.RED}[Ação de Impacto]{Color.RESET}" if item.kind == ActionKind.DANGEROUS else ""
                    print(f"\n {Color.BOLD}• {item.title}{Color.RESET}{tag}")
                    print(f"   {Color.DIM}Comando : {cmd_str}{Color.RESET}")
                    print(f"   Detalhes: {item.description}")
            input(f"\n{Color.CYAN}Pressione Enter para continuar...{Color.RESET}")
        elif choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES_DATA):
            selected_cat = CATEGORIES_DATA[int(choice) - 1]
            os.system("cls" if os.name == "nt" else "clear")
            print(f"\n{Color.BOLD}{'=' * 75}\n {selected_cat.name.upper()}\n{'=' * 75}{Color.RESET}")
            for item in selected_cat.items:
                cmd_str = item.command if item.command else f"[Rotina Especial: {item.action_key}]"
                tag = f" {Color.RED}[Ação de Impacto]{Color.RESET}" if item.kind == ActionKind.DANGEROUS else ""
                print(f"\n {Color.BOLD}• {item.title}{Color.RESET}{tag}")
                print(f"   {Color.DIM}Comando : {cmd_str}{Color.RESET}")
                print(f"   Detalhes: {item.description}")
            input(f"\n{Color.CYAN}Pressione Enter para continuar...{Color.RESET}")


# ---------------------------------------------------------------------------
# Loop Principal e Interface
# ---------------------------------------------------------------------------

def print_header() -> None:
    os.system("cls" if os.name == "nt" else "clear")
    dry_tag = f" {Color.YELLOW}[MODO DRY-RUN / DEMO]{Color.RESET}" if DRY_RUN else ""
    print(f"{Color.BOLD}{'=' * 75}{Color.RESET}")
    print(f"{Color.GREEN} WINDOWS ADMIN & POWER-USER TOOLKIT v{VERSION}{Color.RESET}{dry_tag}")
    print(f" {Color.DIM}Ambiente: {sys.platform.upper()} | Python {sys.version.split()[0]} | Autor: github.com/Vitoriodev{Color.RESET}")
    print(f"{Color.BOLD}{'=' * 75}{Color.RESET}")
    print(f" Log de auditoria : {Color.CYAN}{LOG_FILE}{Color.RESET}")
    print(f" Comandos globais : {Color.BOLD}[h]{Color.RESET} Ajuda/Doc | {Color.BOLD}[l]{Color.RESET} Logs | {Color.BOLD}[c]{Color.RESET} CLI Livre | {Color.BOLD}[p]{Color.RESET} PowerShell | {Color.BOLD}[q]{Color.RESET} Sair")
    print(f"{Color.BOLD}{'=' * 75}{Color.RESET}\n")


def show_categories() -> None:
    for i, cat in enumerate(CATEGORIES_DATA, start=1):
        print(f" {Color.BOLD}{i:2d}){Color.RESET} {cat.name}")


def show_commands(cat: Category) -> None:
    print(f"\n{Color.BOLD}{Color.CYAN}--- {cat.name} ---{Color.RESET}")
    for i, item in enumerate(cat.items, start=1):
        tag = ""
        if item.kind == ActionKind.DANGEROUS:
            tag = f"  {Color.RED}[!] Impacto/Altera Sistema{Color.RESET}"
        elif item.kind == ActionKind.INTERACTIVE:
            tag = f"  {Color.YELLOW}[interativo]{Color.RESET}"
        elif item.kind == ActionKind.KIT:
            tag = f"  {Color.MAGENTA}[Kit Composto]{Color.RESET}"
        print(f" {Color.BOLD}{i:2d}){Color.RESET} {item.title}{tag}")
    print(f"  {Color.GREEN}0){Color.RESET} Voltar")


def free_command() -> None:
    try:
        cmd = input(f"\n{Color.GREEN}PowerShell> {Color.RESET}").strip()
        if not cmd or cmd.lower() in ("exit", "quit"):
            return
        run_powershell(cmd)
    except KeyboardInterrupt:
        print()


def interactive_powershell() -> None:
    print(f"\n{Color.YELLOW}Abrindo console PowerShell interativo (digite 'exit' para retornar ao toolkit)...{Color.RESET}\n")
    if DRY_RUN:
        print("[DRY-RUN] Terminal interativo PowerShell simulado.")
    else:
        try:
            subprocess.run(["powershell", "-NoExit", "-NoProfile"])
        except Exception as e:
            print(f"{Color.RED}Erro ao iniciar PowerShell: {e}{Color.RESET}")


def category_loop(cat: Category) -> None:
    while True:
        show_commands(cat)
        try:
            choice = input(f"\n{Color.CYAN}Escolha um comando: {Color.RESET}").strip()
        except KeyboardInterrupt:
            print()
            return

        if choice in ("0", ""):
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(cat.items)):
            print(f"{Color.RED}Opção inválida.{Color.RESET}")
            continue

        item = cat.items[int(choice) - 1]

        # Execução de Ações Especiais
        if item.kind == ActionKind.INTERACTIVE and item.action_key:
            if item.action_key in SPECIAL_ACTIONS:
                try:
                    SPECIAL_ACTIONS[item.action_key]()
                except KeyboardInterrupt:
                    print(f"\n{Color.YELLOW}[!] Ação cancelada.{Color.RESET}")
                input(f"\n{Color.CYAN}Pressione Enter para continuar...{Color.RESET}")
            continue

        # Execução de Kits Compostos
        if item.kind == ActionKind.KIT and item.command in KITS_RAW:
            print(f"\n{Color.BOLD}Kit selecionado: {item.title}{Color.RESET}")
            print(" 1) Executar e exibir na tela")
            print(" 2) Executar e Exportar Relatório completo (Markdown)")
            print(" 0) Cancelar")
            kit_opt = input(f"\n{Color.CYAN}Opção: {Color.RESET}").strip()
            if kit_opt == "1":
                for line in KITS_RAW[item.command].strip().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    print(f"\n{Color.CYAN}$ {line}{Color.RESET}")
                    run_powershell(line)
                input(f"\n{Color.CYAN}Pressione Enter para continuar...{Color.RESET}")
            elif kit_opt == "2":
                export_diagnostic_kit(item.command, item.title, KITS_RAW[item.command])
                input(f"\n{Color.CYAN}Pressione Enter para continuar...{Color.RESET}")
            continue

        # Confirmação para comandos perigosos
        if item.kind == ActionKind.DANGEROUS:
            if not confirm(f"ATENÇÃO: '{item.title}' causará alterações persistentes no sistema. Deseja continuar?"):
                print(f"{Color.YELLOW}Operação abortada pelo usuário.{Color.RESET}")
                continue

        if item.command:
            print(f"\n{Color.CYAN}$ {item.command}{Color.RESET}\n")
            run_powershell(item.command)
            input(f"\n{Color.CYAN}Pressione Enter para continuar...{Color.RESET}")


def main() -> None:
    global DRY_RUN

    Color.enable_vt_support()

    parser = argparse.ArgumentParser(description=f"Windows Admin & Power-User Toolkit v{VERSION}")
    parser.add_argument("--dry-run", "--demo", "-d", action="store_true", help="Executa em modo de simulação sem alterar o sistema.")
    args = parser.parse_args()

    if args.dry_run:
        DRY_RUN = True

    ensure_admin()

    while True:
        print_header()
        show_categories()
        try:
            choice = input(f"\n{Color.CYAN}Selecione uma categoria: {Color.RESET}").strip().lower()
        except KeyboardInterrupt:
            print(f"\n{Color.YELLOW}Saindo.{Color.RESET}")
            break

        if choice in ("q", "quit", "exit"):
            print(f"{Color.GREEN}Sessão encerrada com sucesso.{Color.RESET}")
            break
        elif choice in ("h", "help", "doc", "ajuda"):
            show_documentation()
        elif choice in ("l", "log", "logs"):
            action_view_logs()
        elif choice == "c":
            free_command()
            input(f"\n{Color.CYAN}Pressione Enter para continuar...{Color.RESET}")
        elif choice == "p":
            interactive_powershell()
        elif choice.isdigit() and 1 <= int(choice) <= len(CATEGORIES_DATA):
            category_loop(CATEGORIES_DATA[int(choice) - 1])
        else:
            print(f"{Color.RED}Entrada não reconhecida.{Color.RESET}")
            try:
                input(f"{Color.CYAN}Pressione Enter para continuar...{Color.RESET}")
            except KeyboardInterrupt:
                pass


if __name__ == "__main__":
    main()
