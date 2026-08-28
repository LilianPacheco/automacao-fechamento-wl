param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$StorageFile = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$FileAccessMode = [Windows.Storage.FileAccessMode, Windows.Storage, ContentType=WindowsRuntime]
$RandomAccessStream = [Windows.Storage.Streams.IRandomAccessStream, Windows.Storage, ContentType=WindowsRuntime]
$BitmapDecoder = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$SoftwareBitmap = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$Language = [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]
$OcrEngine = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$OcrResult = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType=WindowsRuntime]

$AsTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq "AsTask" -and $_.IsGenericMethodDefinition -and $_.GetParameters().Count -eq 1
})[0]

function Await-WinRT($Operation, [Type]$ResultType) {
    $Task = $AsTaskGeneric.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $Task.Wait()
    return $Task.Result
}

$Stream = $null
try {
    $Resolved = (Resolve-Path -LiteralPath $Path).Path
    $File = Await-WinRT ($StorageFile::GetFileFromPathAsync($Resolved)) $StorageFile
    $Stream = Await-WinRT ($File.OpenAsync($FileAccessMode::Read)) $RandomAccessStream
    $Decoder = Await-WinRT ($BitmapDecoder::CreateAsync($Stream)) $BitmapDecoder
    $Bitmap = Await-WinRT ($Decoder.GetSoftwareBitmapAsync()) $SoftwareBitmap
    $Portuguese = [Activator]::CreateInstance($Language, @("pt-BR"))
    $Engine = $OcrEngine::TryCreateFromLanguage($Portuguese)
    if ($null -eq $Engine) { throw "O OCR em português não está disponível no Windows." }
    $Result = Await-WinRT ($Engine.RecognizeAsync($Bitmap)) $OcrResult
    $Lines = @()
    foreach ($Line in $Result.Lines) {
        $Words = @($Line.Words)
        if ($Words.Count -eq 0) { continue }
        $Left = ($Words | ForEach-Object { $_.BoundingRect.X } | Measure-Object -Minimum).Minimum
        $Top = ($Words | ForEach-Object { $_.BoundingRect.Y } | Measure-Object -Minimum).Minimum
        $Right = ($Words | ForEach-Object { $_.BoundingRect.X + $_.BoundingRect.Width } | Measure-Object -Maximum).Maximum
        $Bottom = ($Words | ForEach-Object { $_.BoundingRect.Y + $_.BoundingRect.Height } | Measure-Object -Maximum).Maximum
        $Lines += [PSCustomObject]@{
            text = [string]$Line.Text
            x = [double]$Left
            y = [double]$Top
            width = [double]($Right - $Left)
            height = [double]($Bottom - $Top)
        }
    }
    $Payload = [PSCustomObject]@{ text = [string]$Result.Text; lines = $Lines }
    $Json = $Payload | ConvertTo-Json -Depth 5 -Compress
    [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Json))
}
finally {
    if ($null -ne $Stream) { $Stream.Dispose() }
}
