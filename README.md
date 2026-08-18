# Windows Admin & Power-User Toolkit

TUI de terminal para Windows 10/11 x64, feita para administração de baixo nível, diagnóstico de hardware, segurança, manutenção e virtualização. Interface colorida (ANSI/VT100), elevação automática de privilégios (UAC), log de auditoria completo e modo de simulação (`--dry-run`) para testar sem alterar o sistema.

## Funcionalidades

Comandos organizados em 10 categorias:

1. **Informações do Sistema & Hardware** — versão do Windows, BIOS/UEFI, topologia de CPU, slots de RAM, placa-mãe, GPU e driver de vídeo.
2. **Processos, Threads e Análise Forense** — top processos por CPU, mapeamento processo→serviço, conexões TCP por PID, DLLs carregadas, finalizar processo por PID/nome.
3. **Armazenamento, SMART e NVMe** — discos físicos e tipo de mídia, volumes e espaço livre, esquema de partições (GPT/MBR), CHKDSK, TRIM/otimização de SSD, DiskPart.
4. **Reparo do Sistema e Component Store (WinSxS)** — SFC e DISM (CheckHealth, ScanHealth, RestoreHealth, ResetBase).
5. **Rede Avançada e Sockets** — interfaces e IPs, sockets/portas abertas, tabela de roteamento, ARP, cache DNS, teste de porta/latência, reset completo da pilha de rede.
6. **Segurança, Criptografia e Políticas** — hash SHA-256 de arquivos, ponto de restauração do sistema, BitLocker/TPM, isolamento de núcleo (VBS/Credential Guard), certificados raiz, GPOs aplicadas, scan e atualização do Windows Defender.
7. **Manutenção, Inicialização e Serviços** — limpeza profunda do sistema (temp, lixeira, prefetch, cache do Windows Update), programas de inicialização automática, drivers do kernel e de terceiros, dispositivos com falha, configuração de dumps de memória (BSOD), gerenciamento de serviços.
8. **Subsistemas, DevTools e Virtualização** — status e shutdown do WSL, recursos Hyper-V, atualização em massa via WinGet, habilitar WinRM.
9. **Utilitários e Scripts da Comunidade** — atalhos para scripts públicos conhecidos (Microsoft Activation Scripts, Chris Titus Tech WinUtil, Win-Debloat).
10. **Kits de Diagnóstico Integrado & Exportação** — rotinas compostas (rede, segurança, hardware) executadas em sequência, com opção de exportar o resultado como relatório Markdown na Área de Trabalho.

Recursos gerais do programa:

- **Interface colorida (ANSI/VT100)** — destaque visual para avisos, ações de impacto, seções e resultados.
- **Modo Dry-Run** (`--dry-run` / `--demo` / `-d`) — simula todos os comandos sem executá-los de fato e sem exigir elevação, útil para testes e demonstração.
- **CLI livre** (`c`) — executa qualquer comando PowerShell digitado na hora.
- **Terminal interativo** (`p`) — abre um console PowerShell completo dentro do programa.
- **Documentação integrada** (`h`) — manual técnico com a descrição de cada comando, por categoria ou completo.
- **Visualizador de log** (`l`) — mostra as últimas linhas do log de auditoria diretamente no menu, com opção de limpar.
- **Log de auditoria** — todo comando e sua saída são registrados em `win_toolkit_log.txt`, na pasta do usuário.
- **Validação e sanitização de entrada** — PIDs, nomes de processo, hosts, portas e nomes de serviço são validados por regex e escapados antes de irem para o PowerShell.
- **Confirmação para ações de impacto** — comandos marcados como perigosos (reset de rede, limpeza do WinSxS, atualização em massa, scripts remotos, etc.) pedem confirmação explícita antes de rodar.
- **Exportação de relatórios** — os kits de diagnóstico podem gerar um relatório `.md` com data, host e saída completa de cada comando executado.

## Requisitos

- Windows 10 ou 11, 64 bits
- Python 3.10+ (se executado via código-fonte)
- Privilégios de administrador (solicitados automaticamente via UAC, exceto em modo `--dry-run`)

## Uso

```bash
python win_toolkit.py
```

Modo de simulação, sem alterar nada no sistema e sem pedir elevação:

```bash
python win_toolkit.py --dry-run
```

Navegação no menu:

- Número da categoria → abre a lista de comandos daquela categoria
- Número do comando → executa (pede confirmação se for uma ação de impacto)
- `h` — manual técnico / documentação dos comandos
- `l` — visualizar / limpar o log de auditoria
- `c` — modo CLI livre (comando PowerShell arbitrário)
- `p` — abrir terminal PowerShell interativo
- `q` — sair

## Estrutura do projeto

```
win_toolkit/
├── win_toolkit.py   # script principal
└── ico/
    └── app.ico      # ícone do aplicativo
```

## Aviso

Este programa executa comandos administrativos com privilégios elevados, incluindo operações que alteram configurações do sistema, rede, componentes do Windows e serviços. As opções marcadas como **[!] Impacto/Altera Sistema** exigem confirmação antes de rodar — ainda assim, revise o comando exibido antes de confirmar, especialmente os que baixam e executam scripts remotos (categoria 9). Use `--dry-run` para conhecer o fluxo do programa sem risco.

## Autor

[github.com/Vitoriodev](https://github.com/Vitoriodev)
