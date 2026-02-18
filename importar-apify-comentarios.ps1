# Importar COMENTARIOS desde una corrida de "Facebook Comments Scraper" en Apify.
# El post debe estar ya en la BD (importa antes con importar-apify-run.ps1 los posts).
# Uso: .\importar-apify-comentarios.ps1 -RunId "abc123xyz"
#      .\importar-apify-comentarios.ps1 -RunId "abc123xyz" -ProfileId 3

param(
    [Parameter(Mandatory=$true)][string]$RunId,
    [string]$Platform = "facebook",
    [int]$ProfileId = 0
)

$body = @{
    run_id = $RunId
    platform = $Platform.ToLower()
}
if ($ProfileId -gt 0) {
    $body["profile_id"] = $ProfileId
}
$bodyJson = $body | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/import-apify-comments-run" `
        -Method Post `
        -ContentType "application/json" `
        -Body $bodyJson
    Write-Host "OK: $($response.message)" -ForegroundColor Green
    Write-Host "Comentarios importados: $($response.comments_imported)"
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
