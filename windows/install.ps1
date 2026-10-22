# Windows: the apps from winget. Ansible sets up macOS, Linux and WSL; Windows itself only gets this list.
#
#   powershell -ExecutionPolicy Bypass -File windows\install.ps1
#
# Verify IDs once with: winget search <name>
$ids = @(
    '7zip.7zip'
    'Bitwarden.Bitwarden'
    'Brave.Brave'
    'Discord.Discord'
    'Docker.DockerDesktop'
    'Git.Git'
    'GitHub.cli'
    'Google.AndroidStudio'
    'JetBrains.Toolbox'
    'Microsoft.PowerShell'
    'Microsoft.VisualStudioCode'
    'Microsoft.WindowsTerminal'
    'Neovim.Neovim'
    'Postman.Postman'
    'Tailscale.Tailscale'
    'jdx.mise'
    'wez.wezterm'
)
$failed = @()
foreach ($id in $ids) {
    winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements
    # 0: installed; -1978335189: already installed
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) { $failed += $id }
}
if ($failed.Count -gt 0) { Write-Warning "Not installed: $($failed -join ', ')" }
