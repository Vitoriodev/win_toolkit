# Windows Admin & Power-User Toolkit 🛠️

Interface interativa de terminal (CLI/TUI) para Windows 10/11 x64 focada em rotinas de baixo nível, diagnóstico de hardware, segurança, manutenção avançada, análise forense e virtualização.

---

## ✨ Funcionalidades Principais

- **Informações do Sistema & Hardware**: BIOS/UEFI, topologia de CPU (núcleos/threads/cache), pentes de RAM e frequência, barramento, GPU e drivers.
- **Processos & Análise Forense**: Consumo de CPU/RAM, sockets TCP mapeados a PIDs, inspeção de DLLs em memória, terminação segura de processos.
- **Armazenamento, SMART & NVMe**: Saúde de discos físicos, volumes e partições GPT/MBR, CHKDSK, TRIM e DiskPart.
- **Reparo do Sistema & WinSxS**: SFC Scannow, DISM Check/Scan/RestoreHealth, ComponentCleanup ResetBase.
- **Rede Avançada & Sockets**: Mapeamento IP/DNS/Gateway, conexões TCP ativas, rotas de kernel, ARP, testes de porta e reset de Winsock.
- **Segurança & Criptografia**: Hash SHA-256, TPM, BitLocker, VBS/Credential Guard, auditoria de certificados e varreduras do Windows Defender.
- **Limpeza & Otimização do Sistema**: Remoção de temporários (%temp%, Windows\Temp), esvaziamento de lixeira, limpeza de cache do Windows Update e Prefetch.
- **Gerenciamento de Inicialização & Serviços**: Auditoria de programas que iniciam com o Windows e controle de serviços no SCM.
- **Kits de Diagnóstico com Exportação**: Execução composta de diagnósticos com exportação automática de relatórios em Markdown/Texto.
- **Ponto de Restauração**: Criação preventiva de pontos de restauração do sistema antes de alterações críticas.
- **Visualizador de Logs Integrado**: Auditoria e histórico de comandos executados com timestamp.

---

## 🚀 Como Executar

### Pré-requisitos
- **Windows 10 / 11 (64-bit)**
- Privilégios de Administrador (o toolkit solicita elevação UAC automaticamente)

### Execução direta com Python:
```cmd
python win_toolkit.py
```

### Modo Demonstração / Dry-Run (Compatível com Linux / macOS / Windows):
Ideal para testar a interface ou validar comandos sem alterar o sistema:
```bash
python win_toolkit.py --dry-run
```

---

## 🔨 Como Gerar o Executável (.exe)

### Opção 1: No Linux usando Docker
```bash
docker run --rm -v "$(pwd):/src" cdrx/pyinstaller-windows "pyinstaller --onefile --uac-admin --icon=ico/app.ico win_toolkit.py"
```

### Opção 2: No Windows com Python + PyInstaller
```cmd
pip install pyinstaller
pyinstaller --onefile --uac-admin --icon=ico/app.ico win_toolkit.py
```

---

## 🛡️ Segurança e Boas Práticas
- Entradas de usuários são estritamente sanitizadas contra injeções de comando PowerShell.
- Comandos com potencial de impacto exigem confirmação explícita.
- Todos os comandos e saídas são gravados no log de auditoria `win_toolkit_log.txt`.
