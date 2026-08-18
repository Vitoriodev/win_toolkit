#!/usr/bin/env python3
"""
Windows Admin & Power-User Toolkit v7.1 (Resilient GUI Edition)
"""

from __future__ import annotations

import ctypes
import datetime
import os
import subprocess
import sys
import threading
import traceback
from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Elevação de Privilégios Segura (UAC)
# ---------------------------------------------------------------------------

def is_admin() -> bool:
    if os.name != "nt":
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    """Solicita elevação de privilégios e encerra o processo não elevado se autorizado."""
    if os.name != "nt":
        return True
    try:
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
        # 1 = SW_SHOWNORMAL
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{sys.argv[0]}" {params}', None, 1
        )
        # Códigos acima de 32 indicam sucesso
        if ret > 32:
            sys.exit(0)
        else:
            return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Importação Segura do Tkinter
# ---------------------------------------------------------------------------

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, ttk
except Exception as e:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Erro crítico ao carregar interface gráfica (Tkinter):\n\n{e}",
            "Toolkit - Falha de Inicialização",
            0x10  # MB_ICONERROR
        )
    sys.exit(1)

VERSION = "7.1.0"
LOG_FILE = os.path.join(os.path.expanduser("~"), "win_toolkit_gui_log.txt")


class ActionType:
    NORMAL = "normal"
    DANGEROUS = "dangerous"
    CUSTOM = "custom"


class CommandItem:
    def __init__(self, title: str, command: Optional[str], action_type: str, description: str, handler: Optional[Callable] = None):
        self.title = title
        self.command = command
        self.action_type = action_type
        self.description = description
        self.handler = handler


class ToolkitGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        admin_status = "[ADMIN]" if is_admin() else "[USUÁRIO COMUM]"
        self.title(f"Windows Admin & Power-User Toolkit v{VERSION} {admin_status}")
        self.geometry("1200x780")
        self.minsize(1000, 660)
        self.configure(bg="#0f172a")

        self.categories: Dict[str, List[CommandItem]] = {}
        self.init_catalog()
        self.setup_ui()

    def setup_ui(self):
        header_frame = tk.Frame(self, bg="#1e293b", height=60)
        header_frame.pack(side=tk.TOP, fill=tk.X)

        title_lbl = tk.Label(
            header_frame,
            text=f"⚙ WINDOWS ADMIN TOOLKIT v{VERSION}",
            font=("Segoe UI", 13, "bold"),
            bg="#1e293b",
            fg="#38bdf8",
            padx=20,
            pady=15
        )
        title_lbl.pack(side=tk.LEFT)

        adm = is_admin()
        status_color = "#4ade80" if adm else "#f87171"
        status_text = "● PRIVILÉGIOS ELEVADOS (ADMIN)" if adm else "● MODO NÃO-ELEVADO (ACESSO LIMITADO)"

        status_lbl = tk.Label(
            header_frame,
            text=status_text,
            font=("Segoe UI", 9, "bold"),
            bg="#1e293b",
            fg=status_color,
            padx=20
        )
        status_lbl.pack(side=tk.RIGHT)

        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 1. Painel Lateral
        left_frame = tk.Frame(main_paned, bg="#1e293b", width=260)
        main_paned.add(left_frame, weight=1)

        cat_title = tk.Label(left_frame, text="MÓDULOS DEDICADOS", font=("Segoe UI", 10, "bold"), bg="#1e293b", fg="#94a3b8", pady=10)
        cat_title.pack(fill=tk.X)

        self.cat_listbox = tk.Listbox(
            left_frame,
            bg="#0f172a",
            fg="#f8fafc",
            selectbackground="#38bdf8",
            selectforeground="#0f172a",
            font=("Segoe UI", 9),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none"
        )
        self.cat_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.cat_listbox.bind("<<ListboxSelect>>", self.on_category_select)

        for cat_name in self.categories.keys():
            self.cat_listbox.insert(tk.END, f"  {cat_name}")

        # 2. Painel Central
        center_frame = tk.Frame(main_paned, bg="#0f172a", width=370)
        main_paned.add(center_frame, weight=2)

        self.cmd_title = tk.Label(center_frame, text="AÇÕES DO MÓDULO", font=("Segoe UI", 10, "bold"), bg="#0f172a", fg="#94a3b8", pady=10)
        self.cmd_title.pack(fill=tk.X)

        self.buttons_canvas = tk.Canvas(center_frame, bg="#0f172a", highlightthickness=0)
        self.buttons_scrollbar = ttk.Scrollbar(center_frame, orient=tk.VERTICAL, command=self.buttons_canvas.yview)
        self.buttons_frame = tk.Frame(self.buttons_canvas, bg="#0f172a")

        self.buttons_frame.bind(
            "<Configure>",
            lambda e: self.buttons_canvas.configure(scrollregion=self.buttons_canvas.bbox("all"))
        )

        self.canvas_window = self.buttons_canvas.create_window((0, 0), window=self.buttons_frame, anchor="nw")
        self.buttons_canvas.bind("<Configure>", lambda e: self.buttons_canvas.itemconfig(self.canvas_window, width=e.width))
        self.buttons_canvas.configure(yscrollcommand=self.buttons_scrollbar.set)

        self.buttons_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.buttons_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 3. Painel Direito (Console)
        right_frame = tk.Frame(main_paned, bg="#1e293b", width=570)
        main_paned.add(right_frame, weight=3)

        console_header = tk.Frame(right_frame, bg="#1e293b")
        console_header.pack(fill=tk.X, padx=10, pady=6)

        tk.Label(console_header, text="CONSOLE POWERSHELL (TEMPO REAL)", font=("Segoe UI", 10, "bold"), bg="#1e293b", fg="#94a3b8").pack(side=tk.LEFT)

        clear_btn = tk.Button(console_header, text="Limpar Console", bg="#334155", fg="#f8fafc", font=("Segoe UI", 8), command=self.clear_console, relief=tk.FLAT)
        clear_btn.pack(side=tk.RIGHT)

        self.console_txt = tk.Text(
            right_frame,
            bg="#020617",
            fg="#e2e8f0",
            font=("Consolas", 10),
            wrap=tk.WORD,
            borderwidth=0,
            highlightthickness=0,
            padx=10,
            pady=10
        )
        self.console_txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        if self.categories:
            self.cat_listbox.select_set(0)
            self.load_category_buttons(list(self.categories.keys())[0])

    def on_category_select(self, event):
        selection = self.cat_listbox.curselection()
        if selection:
            idx = selection[0]
            cat_name = list(self.categories.keys())[idx]
            self.load_category_buttons(cat_name)

    def load_category_buttons(self, cat_name: str):
        self.cmd_title.config(text=f"MÓDULO: {cat_name.upper()}")
        for widget in self.buttons_frame.winfo_children():
            widget.destroy()

        items = self.categories.get(cat_name, [])
        for item in items:
            btn_color = "#1e293b"
            fg_color = "#f8fafc"

            if item.action_type == ActionType.DANGEROUS:
                btn_color = "#7f1d1d"
            elif item.action_type == ActionType.CUSTOM:
                btn_color = "#1e3a8a"

            card = tk.Frame(self.buttons_frame, bg=btn_color, pady=8, padx=10, cursor="hand2")
            card.pack(fill=tk.X, pady=4, padx=5)

            title_lbl = tk.Label(card, text=item.title, font=("Segoe UI", 9, "bold"), bg=btn_color, fg=fg_color, anchor="w")
            title_lbl.pack(fill=tk.X)

            desc_lbl = tk.Label(card, text=item.description, font=("Segoe UI", 8), bg=btn_color, fg="#94a3b8", anchor="w", wraplength=310, justify=tk.LEFT)
            desc_lbl.pack(fill=tk.X, pady=(2, 0))

            for w in (card, title_lbl, desc_lbl):
                w.bind("<Button-1>", lambda e, it=item: self.dispatch_command(it))

    def write_console(self, text: str):
        self.console_txt.insert(tk.END, text)
        self.console_txt.see(tk.END)

    def clear_console(self):
        self.console_txt.delete("1.0", tk.END)

    def run_powershell_async(self, command: str, title: str):
        def worker():
            self.write_console(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] > EXECUTANDO: {title}\n")
            self.write_console(f"$ {command}\n\n")

            full_cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]

            try:
                # Flag para impedir criação de terminal piscando
                creationflags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
                proc = subprocess.Popen(
                    full_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=creationflags
                )

                for line in proc.stdout:
                    self.write_console(line)

                stderr_out = proc.stderr.read()
                if stderr_out:
                    self.write_console(f"\n[ERRO]:\n{stderr_out}\n")

                proc.wait()
                self.write_console(f"\n[✓] Concluído (Código {proc.returncode})\n")
            except Exception as e:
                self.write_console(f"\n[FALHA DE EXECUÇÃO]: {e}\n")

        threading.Thread(target=worker, daemon=True).start()

    def dispatch_command(self, item: CommandItem):
        if item.action_type == ActionType.DANGEROUS:
            if not messagebox.askyesno("Confirmação de Segurança", f"ATENÇÃO: '{item.title}' causará alterações no sistema.\n\nDeseja continuar?"):
                return

        if item.handler:
            item.handler()
        elif item.command:
            self.run_powershell_async(item.command, item.title)

    # -----------------------------------------------------------------------
    # Handlers Customizados
    # -----------------------------------------------------------------------

    def custom_ticket_summary(self):
        cmd = """
        $cs = Get-CimInstance Win32_ComputerSystem
        $bios = Get-CimInstance Win32_BIOS
        $os = Get-CimInstance Win32_OperatingSystem
        $cpu = Get-CimInstance Win32_Processor
        $disks = Get-PhysicalDisk | ForEach-Object { "$($_.FriendlyName) ($($_.MediaType), $($_.HealthStatus))" }
        $failed = (Get-PnpDevice | Where-Object Status -ne 'OK').Count

        [PSCustomObject]@{
            HostName      = $cs.Name
            Equipamento   = "$($cs.Manufacturer) $($cs.Model)"
            SerialBIOS    = $bios.SerialNumber
            Sistema       = "$($os.Caption) ($($os.OSArchitecture))"
            Processador   = $cpu.Name
            RAM_Total_GB  = [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
            Discos        = ($disks -join ' | ')
            DevComFalha   = $failed
        } | Format-List
        """
        self.run_powershell_async(cmd, "Resumo Técnico para Chamados")

    def custom_chkdsk_dynamic(self):
        drive = simpledialog.askstring("Verificar Disco", "Informe a letra da unidade (ex: C, D, E):")
        if drive and len(drive.strip()) == 1:
            clean = drive.strip().upper()
            self.run_powershell_async(f"chkdsk {clean}: /scan", f"CHKDSK em {clean}:")

    def custom_trim_dynamic(self):
        drive = simpledialog.askstring("Otimização TRIM", "Informe a letra do SSD (ex: C, D):")
        if drive and len(drive.strip()) == 1:
            clean = drive.strip().upper()
            self.run_powershell_async(f"Optimize-Volume -DriveLetter {clean} -Defrag -Verbose", f"TRIM no SSD {clean}:")

    def custom_format_volume(self):
        drive = simpledialog.askstring("Formatar Volume", "Informe a letra da unidade SECUNDÁRIA (ex: D, E, F):")
        if not drive or len(drive.strip()) != 1:
            return
        clean = drive.strip().upper()
        sys_drive = os.environ.get("SystemDrive", "C:").replace(":", "").upper()
        if clean == sys_drive:
            messagebox.showerror("Bloqueio de Segurança", f"Não é permitido formatar a partição do sistema ({clean}:) por este método.")
            return

        fs = simpledialog.askstring("Sistema de Arquivos", "Digite NTFS, FAT32 ou exFAT:", initialvalue="NTFS")
        if not fs or fs.upper() not in ("NTFS", "FAT32", "EXFAT"):
            return

        if messagebox.askyesno("ATENÇÃO CRÍTICA", f"TODOS OS DADOS DA UNIDADE {clean}: SERÃO APAGADOS.\n\nFormatar em {fs.upper()} agora?"):
            cmd = f'Format-Volume -DriveLetter {clean} -FileSystem {fs.upper()} -Force'
            self.run_powershell_async(cmd, f"Formatando Volume {clean}: ({fs.upper()})")

    def custom_kill_process(self):
        pid = simpledialog.askstring("Finalizar Processo", "Informe o PID do processo a encerrar:")
        if pid and pid.isdigit():
            self.run_powershell_async(f"Stop-Process -Id {pid} -Force", f"Kill PID {pid}")

    def custom_unlock_file(self):
        path = simpledialog.askstring("Desbloquear Arquivo", "Caminho do arquivo ou pasta presa:")
        if path:
            escaped = path.replace("'", "''")
            cmd = f"Get-Process | Where-Object {{ $_.Path -like '*{escaped}*' }} | Select-Object Id,ProcessName,Path | Format-Table -AutoSize"
            self.run_powershell_async(cmd, f"Inspecionar arquivo travado: {path}")

    def custom_test_port(self):
        host = simpledialog.askstring("Testar Porta TCP", "Informe o Host ou IP (ex: 8.8.8.8, google.com):")
        if not host:
            return
        port = simpledialog.askstring("Testar Porta TCP", "Informe a Porta TCP (ex: 80, 443, 22):")
        if port and port.isdigit():
            escaped = host.replace("'", "''")
            cmd = f"Test-NetConnection -ComputerName '{escaped}' -Port {port} -InformationLevel Detailed"
            self.run_powershell_async(cmd, f"Testando conexão com {host}:{port}")

    def custom_calc_hash(self):
        path = filedialog.askopenfilename(title="Selecione um arquivo para calcular o Hash SHA-256")
        if path:
            escaped = path.replace("'", "''")
            cmd = f"Get-FileHash -Path '{escaped}' -Algorithm SHA256 | Format-List"
            self.run_powershell_async(cmd, f"Calculando SHA-256 de {os.path.basename(path)}")

    def custom_show_wifi(self):
        cmd = """
        $profiles = netsh wlan show profiles | Select-String "All User Profile\\s*:\\s*(.*)$" | ForEach-Object { $_.Matches.Groups[1].Value.Trim() }
        foreach ($p in $profiles) {
            $pass = (netsh wlan show profile name="$p" key=clear | Select-String "Key Content\\s*:\\s*(.*)$")
            $key = if ($pass) { $pass.Matches.Groups[1].Value.Trim() } else { "[Aberta]" }
            [PSCustomObject]@{ 'SSID / Rede' = $p; 'Senha' = $key }
        } | Format-Table -AutoSize
        """
        self.run_powershell_async(cmd, "Senhas Wi-Fi Salvas")

    def custom_safeboot(self):
        res = messagebox.askquestion("Modo de Segurança", "Escolha a opção desejada:\n\n'Sim' = Modo Seguro com Rede\n'Não' = Restaurar Boot Normal")
        if res == "yes":
            self.run_powershell_async("bcdedit /set '{current}' safeboot network", "Ativar Safe Mode com Rede")
        else:
            self.run_powershell_async("bcdedit /deletevalue '{current}' safeboot", "Restaurar Boot Normal")

    def custom_factory_reset(self):
        res = messagebox.askquestion(
            "Restauração de Fábrica",
            "Deseja abrir o Assistente Nativo do Windows (systemreset.exe)?\n\nEscolha 'Não' se preferir reiniciar no menu WinRE."
        )
        if res == "yes":
            self.run_powershell_async("systemreset.exe", "Restauração de Fábrica (GUI)")
        else:
            if messagebox.askyesno("Reiniciar no WinRE", "O computador será reiniciado imediatamente no menu de recuperação. Confirmar?"):
                self.run_powershell_async("shutdown /r /o /f /t 00", "Reiniciar no WinRE")

    def custom_generate_html_report(self):
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        target_file = os.path.join(desktop_path, f"Laudo_Tecnico_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html")

        def worker():
            self.write_console(f"\n[*] Gerando laudo técnico consolidado em HTML...\n")
            cmd = """
            $d = Get-PhysicalDisk | Select-Object DeviceId,FriendlyName,MediaType,HealthStatus | Out-String
            $v = Get-Volume | Select-Object DriveLetter,FileSystemLabel,SizeRemaining,Size | Out-String
            $c = Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors | Out-String
            $m = Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator,Capacity,Speed | Out-String
            $n = Get-NetIPConfiguration | Out-String
            [PSCustomObject]@{ Discos = $d; Volumes = $v; CPU = $c; RAM = $m; Rede = $n } | ConvertTo-Json
            """
            proc = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
            try:
                import json
                data = json.loads(proc.stdout)
                html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Laudo Técnico</title>
                <style>body{{font-family:Segoe UI,sans-serif;background:#0f172a;color:#f8fafc;padding:20px;}} .card{{background:#1e293b;padding:15px;border-radius:8px;margin-bottom:15px;}} pre{{background:#020617;padding:10px;border-radius:4px;color:#a5f3fc;overflow-x:auto;}}</style></head><body>
                <h2>Relatório Consolidado de Diagnóstico - {os.environ.get('COMPUTERNAME', 'Localhost')}</h2>
                <div class="card"><h3>Hardware & CPU</h3><pre>{data.get('CPU')}</pre></div>
                <div class="card"><h3>Memória RAM</h3><pre>{data.get('RAM')}</pre></div>
                <div class="card"><h3>Saúde de Armazenamento</h3><pre>{data.get('Discos')}</pre></div>
                <div class="card"><h3>Partições</h3><pre>{data.get('Volumes')}</pre></div>
                <div class="card"><h3>Configurações de Rede</h3><pre>{data.get('Rede')}</pre></div>
                </body></html>"""
                with open(target_file, "w", encoding="utf-8") as f:
                    f.write(html)
                self.write_console(f"\n[✓] Laudo salvo com sucesso na Área de Trabalho:\n{target_file}\n")
            except Exception as e:
                self.write_console(f"\n[!] Falha ao gerar HTML: {e}\n")

        threading.Thread(target=worker, daemon=True).start()

    # -----------------------------------------------------------------------
    # Catálogo
    # -----------------------------------------------------------------------

    def init_catalog(self):
        self.categories = {
            "1. Triagem & Chamados": [
                CommandItem("Resumo Técnico para Chamados", None, ActionType.CUSTOM, "Gera sumário formatado de Host, Serial, CPU e Discos para tickets.", self.custom_ticket_summary),
                CommandItem("Gerar Laudo Técnico Completo (HTML)", None, ActionType.CUSTOM, "Exporta relatório consolidado de Hardware, Discos e Rede para o Desktop.", self.custom_generate_html_report),
                CommandItem("Informações Gerais (systeminfo)", "systeminfo", ActionType.NORMAL, "Relatório nativo com dados de BIOS, placa-mãe e patches."),
                CommandItem("Versão Exata do Windows (winver)", "winver", ActionType.NORMAL, "Interface gráfica com build e kernel NT."),
            ],
            "2. Processador & CPU": [
                CommandItem("Topologia de CPU e Frequências", "Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | Format-List", ActionType.NORMAL, "Exibe núcleos, threads e clock base."),
                CommandItem("Monitorar Clock e Throttling", "Get-CimInstance Win32_Processor | Select-Object Name,CurrentClockSpeed,MaxClockSpeed | Format-List", ActionType.NORMAL, "Verifica se a CPU está operando com corte de frequência."),
                CommandItem("Caches L2/L3 do Processador", "Get-CimInstance Win32_Processor | Select-Object Name,L2CacheSize,L3CacheSize | Format-List", ActionType.NORMAL, "Consulta memória cache do processador."),
            ],
            "3. Memória RAM": [
                CommandItem("Pentes Instalados e Barramento (MHz)", "Get-CimInstance Win32_PhysicalMemory | Select-Object DeviceLocator,Capacity,Speed,Manufacturer,PartNumber | Format-Table -AutoSize", ActionType.NORMAL, "Módulos de memória instalados, frequências e slots ocupados."),
                CommandItem("Agendar Teste de Memória (mdsched)", "mdsched.exe", ActionType.NORMAL, "Abre a rotina nativa para testar a RAM no próximo boot."),
            ],
            "4. Bateria & Energia": [
                CommandItem("Relatório de Bateria (HTML no Desktop)", 'powercfg /batteryreport /output "$env:USERPROFILE\\Desktop\\bateria_relatorio.html"', ActionType.NORMAL, "Gera laudo oficial sobre capacidade e ciclos de carga."),
                CommandItem("Desativar Hibernação / Fast Startup", "powercfg /hibernate off", ActionType.NORMAL, "Desliga a hibernação híbrida contra instabilidades de boot."),
                CommandItem("Ativar Hibernação / Fast Startup", "powercfg /hibernate on", ActionType.NORMAL, "Habilita a hibernação e inicialização rápida."),
            ],
            "5. Armazenamento & SMART": [
                CommandItem("Integridade SMART e Tipo de Mídia", "Get-PhysicalDisk | Select-Object DeviceId,FriendlyName,MediaType,HealthStatus | Format-Table -AutoSize", ActionType.NORMAL, "Exibe saúde física de SSDs, HDDs e NVMe."),
                CommandItem("Horas de Uso e Desgaste (Reliability)", "Get-PhysicalDisk | Get-StorageReliabilityCounter | Select-Object DeviceId,ReadErrorsTotal,PowerOnHours,Temperature | Format-Table -AutoSize", ActionType.NORMAL, "Tempo total de operação (Power-On Hours) e temperatura."),
                CommandItem("Partições e Espaço Disponível", "Get-Volume | Select-Object DriveLetter,FileSystemLabel,SizeRemaining,Size | Format-Table -AutoSize", ActionType.NORMAL, "Lista partições montadas e espaço livre."),
                CommandItem("CHKDSK Dinâmico (Scan Leitura)", None, ActionType.CUSTOM, "Executa varredura de integridade na unidade informada.", self.custom_chkdsk_dynamic),
                CommandItem("Otimização/TRIM em SSD", None, ActionType.CUSTOM, "Dispara comando TRIM na partição selecionada.", self.custom_trim_dynamic),
            ],
            "6. Formatação & Partições": [
                CommandItem("Restauração / Formatação de Fábrica", None, ActionType.DANGEROUS, "Reinstalação do Windows sem pendrive ou reinício no WinRE.", self.custom_factory_reset),
                CommandItem("Formatar Volume Secundário / Pendrive", None, ActionType.DANGEROUS, "Formata volumes D:, E: em NTFS, FAT32 ou exFAT com trava na C:.", self.custom_format_volume),
                CommandItem("Abrir DiskPart (CLI)", "Start-Process diskpart.exe", ActionType.DANGEROUS, "Abre a ferramenta nativa de baixo nível para particionamento."),
            ],
            "7. Reparo de Arquivos (SFC/DISM)": [
                CommandItem("Verificar Sistema (SFC /scannow)", "sfc /scannow", ActionType.NORMAL, "Verifica e repara binários protegidos corrompidos."),
                CommandItem("DISM CheckHealth", "DISM /Online /Cleanup-Image /CheckHealth", ActionType.NORMAL, "Consulta flags de corrupção identificadas pelo kernel."),
                CommandItem("DISM ScanHealth", "DISM /Online /Cleanup-Image /ScanHealth", ActionType.NORMAL, "Varredura profunda no repositório WinSxS."),
                CommandItem("DISM RestoreHealth", "DISM /Online /Cleanup-Image /RestoreHealth", ActionType.NORMAL, "Restaura pacotes corrompidos via Windows Update."),
                CommandItem("Limpeza do WinSxS (ResetBase)", "DISM /Online /Cleanup-Image /StartComponentCleanup /ResetBase", ActionType.DANGEROUS, "Remove versões antigas de atualizações para liberar espaço."),
            ],
            "8. Rede Cabeada & TCP/IP": [
                CommandItem("Configuração de Interfaces e IPs", "Get-NetIPConfiguration -Detailed", ActionType.NORMAL, "Lista endereços IPv4/IPv6, gateways e servidores DNS."),
                CommandItem("Reiniciar Adaptadores Físicos de Rede", "Get-NetAdapter -Physical | ForEach-Object { Disable-NetAdapter -Name $_.Name -Confirm:$false; Start-Sleep 2; Enable-NetAdapter -Name $_.Name -Confirm:$false }", ActionType.NORMAL, "Desativa e reativa placas Ethernet e Wi-Fi no driver."),
                CommandItem("Testar Porta TCP (Conectividade)", None, ActionType.CUSTOM, "Executa handshake TCP contra host e porta específicos.", self.custom_test_port),
                CommandItem("Limpar Cache DNS", "Clear-DnsClientCache", ActionType.NORMAL, "Descarta registros resolvidos em cache."),
                CommandItem("Tabela de Sockets e Portas em Escuta", "netstat -ano -p tcp", ActionType.NORMAL, "Lista conexões TCP ativas e portas em LISTENING."),
                CommandItem("Reset Completo de Rede (Winsock + IP)", "netsh winsock reset; netsh int ip reset", ActionType.DANGEROUS, "Restaura catálogo Winsock e pilha TCP/IP aos padrões de fábrica."),
            ],
            "9. Rede Sem Fio (Wi-Fi)": [
                CommandItem("Recuperar Senhas Wi-Fi Salvas", None, ActionType.CUSTOM, "Lista redes sem fio salvas e exibe a senha em texto limpo.", self.custom_show_wifi),
                CommandItem("Status da Interface Wi-Fi", "netsh wlan show interfaces", ActionType.NORMAL, "Exibe sinal, canal, BSSID e taxa de transmissão da conexão atual."),
                CommandItem("Relatório Completo WLAN (HTML)", 'netsh wlan show wlanreport', ActionType.NORMAL, "Gera diagnóstico histórico detalhado da conexão sem fio."),
            ],
            "10. Limpeza & Otimização": [
                CommandItem("Limpar Pastas Temporárias (%TEMP%)", 'Remove-Item "$env:TEMP\\*" -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item "$env:SystemRoot\\Temp\\*" -Recurse -Force -ErrorAction SilentlyContinue', ActionType.NORMAL, "Esvazia pastas temporárias do usuário e do sistema."),
                CommandItem("Esvaziar Lixeira do Windows", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue", ActionType.NORMAL, "Remove todos os arquivos da Lixeira sem confirmação."),
                CommandItem("Limpar Cache do Windows Update", "net stop wuauserv; Remove-Item -Path \"$env:SystemRoot\\SoftwareDistribution\\Download\\*\" -Recurse -Force -ErrorAction SilentlyContinue; net start wuauserv", ActionType.NORMAL, "Apaga downloads de atualizações antigas acumuladas."),
                CommandItem("Reparar Cache de Ícones & Explorer", "Stop-Process -Name explorer -Force; Remove-Item -Path \"$env:LOCALAPPDATA\\IconCache.db\" -Force -ErrorAction SilentlyContinue; Start-Process explorer.exe", ActionType.NORMAL, "Corrige ícones em branco e reinicia o explorer."),
            ],
            "11. Processos & Desbloqueio": [
                CommandItem("Desbloquear Arquivo / Pasta Travada", None, ActionType.CUSTOM, "Localiza processos com handles abertos em um arquivo.", self.custom_unlock_file),
                CommandItem("Top Processos por Consumo de CPU", "Get-Process | Sort-Object CPU -Descending | Select-Object -First 15 Id,ProcessName,CPU | Format-Table -AutoSize", ActionType.NORMAL, "Lista os 15 processos que mais consomem processamento."),
                CommandItem("Mapeamento Processo -> Serviços", "tasklist /svc", ActionType.NORMAL, "Identifica serviços rodando dentro de cada svchost.exe."),
                CommandItem("Finalizar Processo por PID", None, ActionType.CUSTOM, "Envia sinal de término imediato para o PID informado.", self.custom_kill_process),
            ],
            "12. Serviços & Spooler": [
                CommandItem("Destravar Fila de Impressão (Spooler)", 'net stop spooler; Remove-Item "$env:SystemRoot\\System32\\spool\\PRINTERS\\*" -Force -Recurse -ErrorAction SilentlyContinue; net start spooler', ActionType.NORMAL, "Para o spooler, esvazia o buffer travado e reinicia o serviço."),
                CommandItem("Reset Profundo do Windows Update", 'net stop wuauserv; net stop cryptSvc; net stop bits; Remove-Item "$env:SystemRoot\\SoftwareDistribution" -Recurse -Force -ErrorAction SilentlyContinue; net start bits; net start cryptSvc; net start wuauserv', ActionType.NORMAL, "Para serviços e reconstrói catálogos de atualização."),
                CommandItem("Consultar Serviços em Execução", "Get-Service | Where-Object Status -eq 'Running' | Format-Table -AutoSize", ActionType.NORMAL, "Lista todos os serviços ativos no SCM."),
            ],
            "13. Drivers & Dispositivos": [
                CommandItem("Dispositivos com Falha (Device Manager)", "Get-PnpDevice | Where-Object Status -ne 'OK' | Format-Table -AutoSize", ActionType.NORMAL, "Localiza hardwares com erro ou sem driver instalado."),
                CommandItem("Backup de Drivers OEM de Terceiros", 'if (!(Test-Path "C:\\DriverBackup")) { New-Item -ItemType Directory -Path "C:\\DriverBackup" -Force }; Export-WindowsDriver -Online -Destination "C:\\DriverBackup"', ActionType.NORMAL, "Exporta drivers instalados para C:\\DriverBackup."),
                CommandItem("Listar Drivers Carregados no Kernel", "driverquery /fo TABLE", ActionType.NORMAL, "Exibe todos os módulos .sys ativos no sistema."),
            ],
            "14. Segurança & Licenciamento": [
                CommandItem("Chave de Ativação Original (BIOS OEM)", "(Get-CimInstance SoftwareLicensingService).OA3xOriginalProductKey", ActionType.NORMAL, "Recupera a chave de ativação gravada na placa-mãe."),
                CommandItem("Calcular Hash SHA-256 de Arquivo", None, ActionType.CUSTOM, "Calcula o checksum SHA-256 selecionando um arquivo via diálogo.", self.custom_calc_hash),
                CommandItem("Status do BitLocker e TPM", "manage-bde -status; Get-Tpm", ActionType.NORMAL, "Verifica criptografia de volume e segurança do chip TPM 2.0."),
                CommandItem("Criar Ponto de Restauração", 'Checkpoint-Computer -Description "WinToolkit Backup" -RestorePointType "MODIFY_SETTINGS"', ActionType.NORMAL, "Gera ponto de restauração prévio no Windows."),
                CommandItem("Varredura Rápida Defender (CLI)", "Start-MpScan -ScanType QuickScan", ActionType.NORMAL, "Dispara verificação rápida do antivírus nativo."),
                CommandItem("Atualizar Assinaturas do Defender", "Update-MpSignature", ActionType.NORMAL, "Força download das definições de malwares mais recentes."),
            ],
            "15. Inicialização & Boot": [
                CommandItem("Configurar Modo de Segurança (BCD)", None, ActionType.CUSTOM, "Alterna boot para Modo Seguro com Rede ou restaura normal.", self.custom_safeboot),
                CommandItem("Listar Programas na Inicialização", "Get-CimInstance Win32_StartupCommand | Select-Object Name,Command,Location,User | Format-Table -AutoSize", ActionType.NORMAL, "Inspeciona itens que iniciam com o Windows."),
                CommandItem("Configuração de Dumps (CrashDump BSOD)", "Get-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\CrashControl' | Format-List", ActionType.NORMAL, "Exibe tipo de dump gerado em caso de tela azul."),
            ],
            "16. Instalação & Pós-Formatação": [
                CommandItem("Instalar Softwares Essenciais (WinGet)", "winget install --id Google.Chrome -e --silent; winget install --id 7zip.7zip -e --silent; winget install --id Adobe.Acrobat.Reader.64-bit -e --silent; winget install --id VideoLAN.VLC -e --silent", ActionType.NORMAL, "Instalação silenciosa de Chrome, 7-Zip, PDF e VLC."),
                CommandItem("Atualizar Todos os Programas (WinGet)", "winget upgrade --all --include-unknown", ActionType.NORMAL, "Atualiza todos os aplicativos gerenciados pelo WinGet."),
                CommandItem("Status de Instâncias WSL", "wsl --list --verbose", ActionType.NORMAL, "Lista distribuições Linux e estado do WSL."),
            ],
            "17. Tweaks Comunitários & Debloat": [
                CommandItem(
                    "Chris Titus Tech WinUtil",
                    "Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'irm https://christitus.com/win | iex'",
                    ActionType.DANGEROUS,
                    "Abre o painel gráfico comunitário para debloat, telemetria e instalação em massa."
                ),
                CommandItem(
                    "Win-Debloat (raphi.re)",
                    "Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', '& ([scriptblock]::Create((irm https://debloat.raphi.re/)))'",
                    ActionType.DANGEROUS,
                    "Automação focada em remoção de bloatwares do Windows e otimização de privacidade."
                ),
                CommandItem(
                    "Microsoft Activation Scripts (MAS)",
                    "Start-Process powershell -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', 'irm https://get.activated.win | iex'",
                    ActionType.DANGEROUS,
                    "Interface interativa de terminal para gerenciamento de licenças HWID/KMS38."
                ),
            ],
        }


# ---------------------------------------------------------------------------
# Bloco de Proteção e Execução Principal
# ---------------------------------------------------------------------------

def main():
    if not is_admin():
        # Tenta elevar; se o usuário recusar o prompt UAC, continua em modo usuário comum
        relaunch_as_admin()

    app = ToolkitGUI()
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        err_msg = traceback.format_exc()
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Ocorreu um erro durante a execução do Toolkit:\n\n{err_msg}",
                "Toolkit - Erro Não Tratado",
                0x10  # MB_ICONERROR
            )
        else:
            print(err_msg, file=sys.stderr)
        sys.exit(1)