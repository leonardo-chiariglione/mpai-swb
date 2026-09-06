<#
.SYNOPSIS
  Detect which schema families (e.g., OSD\V1.5\data, MMM4\V2.2\data) are required to validate a given family (e.g., AIF\V3.0\data).

.DESCRIPTION
  - Scans all *.json in the target family for $ref strings.
  - Extracts absolute references to schemas.mpai.community and groups them by family/version path:
        https://schemas.mpai.community/<FAMILY>/<VERSION>/<...>/<file>.json
    => required family reported as "<FAMILY>\\<VERSION>\\data".
  - Prints suggested AJV preloads and can export a CSV of all refs.

.PARAMETER Family
  The target family to scan (e.g., 'AIF\V3.0\data').

.PARAMETER Csv
  Optional path to write CSV of each discovered $ref:
  Columns: SourceFile, RefUrl, Family, Version, InferredFolder, RefFileName

.NOTES
  Run from your schemas root:
  PS C:\Users\Ashraf\OneDrive - CEDEO\My Standards\mpai\schemas>
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)] [string]$Family,
  [string]$Csv
)

$glob = ".\{0}\*.json" -f $Family
$files = Get-ChildItem -Path $glob -Recurse -Filter *.json -File -ErrorAction SilentlyContinue
if (-not $files -or $files.Count -eq 0) { Write-Error ("No JSON files found under: {0} (glob: {1})" -f $Family, $glob); exit 2 }

$rxRef = [regex]'(?im)"\$ref"\s*:\s*"(?<url>https://schemas\.mpai\.community/(?<family>[A-Za-z0-9_-]+)/(?<version>V[0-9]+\.[0-9]+)/(?<tail>[^"]+))"'
$rows = New-Object System.Collections.Generic.List[object]
foreach ($f in $files) {
  $t = Get-Content -Raw $f.FullName
  foreach ($m in $rxRef.Matches($t)) {
    $url     = $m.Groups['url'].Value
    $family  = $m.Groups['family'].Value
    $version = $m.Groups['version'].Value
    $tail    = $m.Groups['tail'].Value
    $refFile = [System.IO.Path]::GetFileName($tail)
    $localFolder = '{0}\{1}\data' -f $family, $version
    $rows.Add([pscustomobject]@{ SourceFile=$f.FullName; RefUrl=$url; Family=$family; Version=$version; InferredFolder=$localFolder; RefFileName=$refFile })
  }
}

$required = $rows | Group-Object InferredFolder | Select-Object @{N='InferredFolder';E={$_.Name}}, @{N='Count';E={$_.Count}} | Sort-Object InferredFolder
$normTarget = ($Family -replace '[/\\]+$','')
$externals = $required | Where-Object { $_.InferredFolder -ne $normTarget }

Write-Host ("Target family: {0}" -f $Family) -ForegroundColor Cyan
Write-Host ("Detected absolute $ref count: {0}" -f $rows.Count) -ForegroundColor DarkGray
if ($externals -and $externals.Count -gt 0) {
  Write-Host "Required external families (unique):" -ForegroundColor Green
  foreach ($e in $externals) { Write-Host ("  {0}    (refs: {1})" -f $e.InferredFolder, $e.Count) }
  Write-Host "Suggested AJV preloads:" -ForegroundColor Green
  foreach ($e in $externals) { Write-Host ('  -r ".\{0}\*.json"' -f $e.InferredFolder) }
} else { Write-Host "No external families (apart from the target) detected." -ForegroundColor Green }

if ($Csv) { try { $rows | Export-Csv -Path $Csv -NoTypeInformation -Encoding UTF8; Write-Host ("Wrote CSV: {0}" -f (Resolve-Path $Csv)) -ForegroundColor Green } catch { Write-Warning ("Could not write CSV: {0}" -f $_.Exception.Message) } }

exit 0
