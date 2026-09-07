param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Ports', 'Build', 'Flash', 'Read')]
    [string]$Action,
    [string]$Port,
    [ValidateRange(2, 100)]
    [int]$Reads = 3,
    [string]$ArduinoCli = 'C:\Program Files\Arduino CLI\arduino-cli.exe'
)

$ErrorActionPreference = 'Stop'
$sketch = Join-Path $PSScriptRoot 'arduino\82s123-reader'
$build = Join-Path $PSScriptRoot 'build'
$fqbn = 'arduino:avr:leonardo'

function Invoke-Arduino {
    param([string[]]$CliArgs)
    if (-not (Test-Path -LiteralPath $ArduinoCli)) {
        throw "Arduino CLI not found: $ArduinoCli"
    }
    & $ArduinoCli @CliArgs
    if ($LASTEXITCODE -ne 0) { throw "Arduino CLI failed with exit code $LASTEXITCODE" }
}

if ($Action -eq 'Ports') {
    Invoke-Arduino -CliArgs @('board', 'list')
    return
}
if ($Action -eq 'Build' -or $Action -eq 'Flash') {
    if ($Action -eq 'Flash' -and -not $Port) { throw 'Flash requires -Port COMx.' }
    # Recompile before flashing, so an old binary cannot silently be uploaded.
    Invoke-Arduino -CliArgs @('compile', '--fqbn', $fqbn, '--build-path', $build, $sketch)
    if ($Action -eq 'Flash') {
        Invoke-Arduino -CliArgs @('upload', '--fqbn', $fqbn, '--port', $Port,
                                 '--input-dir', $build, '--verify', $sketch)
    }
    return
}
if (-not $Port) { throw 'Read requires -Port COMx.' }

function Receive-Dump {
    param([System.IO.Ports.SerialPort]$Serial)
    $data = New-Object byte[] 32
    $seen = New-Object bool[] 32
    $checksum = -1
    $deadline = [DateTime]::UtcNow.AddSeconds(5)
    $Serial.WriteLine('READ')
    while ([DateTime]::UtcNow -lt $deadline) {
        try { $line = $Serial.ReadLine().Trim() }
        catch [TimeoutException] { continue }
        $script:transcript.Add($line)
        if ($line -match '^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})$') {
            $address = [Convert]::ToInt32($Matches[1], 16)
            $value = [Convert]::ToByte($Matches[2], 16)
            if ($address -ge 32 -or $seen[$address]) { throw "Invalid/duplicate address: $line" }
            $data[$address] = $value
            $seen[$address] = $true
        } elseif ($line -match '^CHK:([0-9A-Fa-f]{2})$') {
            if ($checksum -ge 0) { throw 'Duplicate checksum.' }
            $checksum = [Convert]::ToInt32($Matches[1], 16)
        } elseif ($line -eq 'OK') {
            if ($seen -contains $false) { throw 'Incomplete PROM read.' }
            $computed = 0
            foreach ($value in $data) { $computed = $computed -bxor $value }
            if ($checksum -ne $computed) { throw 'Missing or incorrect transfer checksum.' }
            return ,$data
        } else {
            throw "Unexpected reader response: $line"
        }
    }
    throw 'Timed out receiving PROM dump.'
}

$captureRoot = Join-Path $PSScriptRoot ('captures\' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $captureRoot -Force | Out-Null
$script:transcript = New-Object 'System.Collections.Generic.List[string]'
$serial = New-Object System.IO.Ports.SerialPort($Port, 115200, 'None', 8, 'One')
$serial.DtrEnable = $true
$serial.RtsEnable = $false
$serial.ReadTimeout = 500
$serial.WriteTimeout = 1000
$serial.NewLine = "`n"
try {
    $serial.Open()
    Start-Sleep -Milliseconds 1500
    $serial.DiscardInBuffer()
    $serial.WriteLine('PING')
    $identity = $serial.ReadLine().Trim()
    $script:transcript.Add($identity)
    if ($identity -ne 'PONG 82S123-READER v0.1.1') {
        throw "Unexpected firmware identity: $identity (expected v0.1.1 from this repository)."
    }
    Write-Host $identity
    $first = $null
    $stable = $true
    for ($iteration = 1; $iteration -le $Reads; $iteration++) {
        $data = Receive-Dump -Serial $serial
        $path = Join-Path $captureRoot ('read-{0:D2}.bin' -f $iteration)
        [IO.File]::WriteAllBytes($path, $data)
        $hex = ($data | ForEach-Object { '{0:X2}' -f $_ }) -join ' '
        Write-Host "Read ${iteration}: $hex"
        if ($null -eq $first) { $first = $data }
        elseif ([BitConverter]::ToString($first) -ne [BitConverter]::ToString($data)) {
            $stable = $false
        }
    }
    Write-Host "Saved $Reads checksummed reads to $captureRoot"
    if (-not $stable) { throw 'PROM readings differ. Individual captures retained; do not treat them as a verified dump.' }
    Write-Host "All $Reads PROM reads are identical."
    $reference = Join-Path $PSScriptRoot '..\..\literature\82s123_dump_mobo.bin'
    $expected = [IO.File]::ReadAllBytes($reference)
    if ([BitConverter]::ToString($first) -eq [BitConverter]::ToString($expected)) {
        Write-Host 'Matches the original PROM dump currently used by the CPLD.'
    } else {
        Write-Host 'DIFFERS from the PROM dump currently used by the CPLD:'
        for ($i = 0; $i -lt [Math]::Max($first.Length, $expected.Length); $i++) {
            if ($i -ge $first.Length -or $i -ge $expected.Length -or $first[$i] -ne $expected[$i]) {
                Write-Host ('Address {0:X2}: saved={1:X2}, newly read={2:X2}' -f $i, $expected[$i], $first[$i])
            }
        }
    }
} finally {
    if ($serial.IsOpen) { $serial.Close() }
    $serial.Dispose()
    [IO.File]::WriteAllLines((Join-Path $captureRoot 'serial.log'), $script:transcript.ToArray())
}
