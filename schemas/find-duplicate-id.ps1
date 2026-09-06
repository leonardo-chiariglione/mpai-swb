<#
.SYNOPSIS
  Find all JSON files (within selected families) that declare a given $id (exact match).

.EXAMPLE
  .\find-duplicate-id.ps1 -Id 'https://schemas.mpai.community/MMM4/V2.2/data/Process.json' `
                          -Families 'AIF\V3.0\data','OSD\V1.5\data','MMM4\V2.2\data'

.NOTES
  Run from your schemas root:
  PS C:\Users\Ashraf\OneDrive - CEDEO\My Standards\mpai\schemas>
#>

[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)] [string]$Id,
  [string[]]$Families = @('AIF\V3.0\data','OSD\V1.5\data','MMM4\V2.2\data')
)

Write-Host ("Searching for `$id = {0}" -f $Id) -ForegroundColor Cyan
$items = foreach ($fam in $Families) { $glob = ".\{0}\*.json" -f $fam; Get-ChildItem -Path $glob -Recurse -Filter *.json -File -ErrorAction SilentlyContinue }
$hits  = foreach ($f in $items) { $t = Get-Content -Raw $f.FullName; if ($t -match '"\$id"\s*:\s*"' + [regex]::Escape($Id) + '"') { $f.FullName } }
if ($hits -and $hits.Count) { Write-Host "Found in:" -ForegroundColor Green; $hits | Sort-Object | ForEach-Object { $_ }; if ($hits.Count -gt 1) { Write-Warning ("Duplicate `$id detected in {0} files." -f $hits.Count) } }
else { Write-Host "No files found declaring that `$id in the provided families." -ForegroundColor Yellow }
