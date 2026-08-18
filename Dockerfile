# escape=`
FROM mcr.microsoft.com/windows/servercore:ltsc2022

SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

# Install Python 3.12
RUN Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe" -OutFile python-installer.exe; `
    Start-Process python-installer.exe -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1' -Wait; `
    Remove-Item python-installer.exe -Force

# Install PyInstaller
RUN pip install --no-cache-dir pyinstaller

WORKDIR /src

# Copy source files
COPY win_toolkit.py .
COPY win_toolkit.spec .
COPY ico/ ico/

# Build the exe
RUN pyinstaller --clean --noconfirm win_toolkit.spec

# Copy result to /output for easy extraction
RUN mkdir C:\output; `
    Copy-Item C:\src\dist\win_toolkit.exe C:\output\win_toolkit.exe

CMD ["cmd"]
