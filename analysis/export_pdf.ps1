param([Parameter(Mandatory = $true)][string]$Path)

$full = (Resolve-Path $Path).Path
$pdf = [System.IO.Path]::ChangeExtension($full, ".pdf")
$word = New-Object -ComObject Word.Application
$word.Visible = $false
try {
    $doc = $word.Documents.Open($full, $false, $true)
    $doc.ExportAsFixedFormat($pdf, 17)
    Write-Output "Pages: $($doc.ComputeStatistics(2))"
    $doc.Close($false)
    Write-Output "Exported $pdf"
}
finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
