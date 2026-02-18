# Importar datos desde una corrida guardada en Apify (sin gastar tokens)
# Uso: .\importar-apify-run.ps1 -RunId "abc123xyz" -Platform "facebook" -ProfileId 3

param(
    [Parameter(Mandatory=$true)][string]$RunId,
    [Parameter(Mandatory=$true)][string]$Platform,
    [Parameter(Mandatory=$true)][int]$ProfileId
)

$body = @{
    run_id = $RunId
    platform = $Platform.ToLower()
    profile_id = $ProfileId
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/import-apify-run" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
    Write-Host "OK: $($response.message)" -ForegroundColor Green
    Write-Host "Posts importados: $($response.posts_imported)"
    Write-Host "Comentarios importados: $($response.comments_imported)"
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
