Get-Process chrome | ForEach-Object {
    $proc = $_
    $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
    Write-Output "PID: $($proc.Id)"
    Write-Output "Command: $cmd"
    Write-Output "---"
}
