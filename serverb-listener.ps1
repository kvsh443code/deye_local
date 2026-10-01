param([int]$Port = 8899, [string]$Log = "$PSScriptRoot\serverb-capture.log")

$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
$listener.Start()
"$(Get-Date -Format o) listening on 0.0.0.0:$Port" | Tee-Object -FilePath $Log -Append

while ($true) {
    $client = $listener.AcceptTcpClient()
    $remote = $client.Client.RemoteEndPoint
    "$(Get-Date -Format o) CONNECT from $remote" | Tee-Object -FilePath $Log -Append
    $stream = $client.GetStream()
    $stream.ReadTimeout = 120000
    $buf = New-Object byte[] 4096
    try {
        while ($true) {
            $n = $stream.Read($buf, 0, $buf.Length)
            if ($n -le 0) { break }
            $hex = ($buf[0..($n - 1)] | ForEach-Object { $_.ToString('X2') }) -join ' '
            "$(Get-Date -Format o) RX $n bytes: $hex" | Tee-Object -FilePath $Log -Append
        }
    } catch {
        "$(Get-Date -Format o) read ended: $($_.Exception.InnerException.Message)" | Tee-Object -FilePath $Log -Append
    }
    $client.Close()
    "$(Get-Date -Format o) CLOSED $remote" | Tee-Object -FilePath $Log -Append
}
