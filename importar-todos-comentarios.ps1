# Importa comentarios de todas las corridas de Facebook Comments Scraper listadas (una sola petición).
# Ejecutar con el backend levantado: .\importar-todos-comentarios.ps1
# Opcional: .\importar-todos-comentarios.ps1 -ProfileId 3

param([int]$ProfileId = 3)

$runIds = @(
    "lMvfrpyqnkm75jLIZ", "TjgWSwBxZlcsGa6ni", "QntxRKGhXwlhelrod", "3npyxiNMV9lB61UDq",
    "TZZt56SEjm5u0GjJy", "etXhUJOReG0WKktd9", "g0s4wVOFZZNiaKYaj", "IJM195pQ0Mgam21Em",
    "GOhKCmaVDfDyHDcAO", "5LxAuRpAgflTSU2Cq", "cFH4UqAyG3dJjkcJe", "wqXzt7iWQQSssBemf",
    "9UZTePM4aWtogeJ3f", "7zC0zofZlt15qfrrY", "zoTc0o7IbMoerHEUN", "YhdH3YpBc8pZ5EefP",
    "9o7UInE0RKHxC73gE", "XZtyB1uytkGT36HfH", "wLddT5gEvgal0RP7G", "t43Dhx5gSm59XRC1n",
    "SiJkWUpRRCfRz1QKG", "eKk4bLI4dQ8D0ejPf", "kiWQzXEeacv7ckjt8", "XXIMiZhHY4Qpq3WzR",
    "ixckPxktCX9VmwySF", "dkyY43syIaUt9wvdk", "nSC3EwbUyb7Kr5sxE", "Wi0MvpGjvmlwbXyRz",
    "1KoXIcJdZPBauzwBK", "sLKbDUJbKZWgyWzLD", "aAQ7cAJf08MmKliZg", "hM2GuKM2TiEU6jfnS",
    "hI5TUmy6fUDESINLa", "T0Zjr87hD8YiRkfx9", "AmSO8v3fQbsGf4ens", "zVTKL2pH2NadzHPbg",
    "Z41FLjXCNuvgNXdKy", "U3LhbzhbVDdPJVVbr", "Dh4kehQJGDRpERjGs", "iuWjmBUnDXRekIbJg",
    "glEocKPYhnHpLE7jK", "tcUePH0Ml1icsJFA0", "R3tQvUeDGQNAynuC4", "eInvDNPamZGxjhIRb",
    "AIFSfsuE6DevMhIjR", "WTjgB33L08SHbQ2Ch", "qWQWOUbfNocOA0WFN", "cQC7S7Fwlcwj6qbr3",
    "YNoB99BmvHBf5koXj", "JO5CNfR8paLw5YJTZ", "pvapWDhBDahmj7ySD", "urgJqpNzs7tlvKbrn",
    "hWqjc4FShhSx8lCAp", "X1aIpvppioDP2yoEV", "yW9fwMFpsde1mFS9j", "hfEOFiCT4BqvCcZcy",
    "ABC07KlPuk3fZmg5Z", "teJtuIpBz2QJZHbME", "Da46UyfaKIUtjFYlS", "fxYwuUYzWSfPN40aP",
    "NnC7O3lHMvXb4fe4e", "FsTeLw1gUtx2VFYks", "E6GOZ1f9FgrKFVTan", "9PElGjiWyLdAQISxs",
    "kDHFY4YcuisCKpOaK", "gbm0seli7NFIbaiLZ", "andQe1Vq8DB9d5Nj7", "O4FlfCJhPIyc8aGsv",
    "5e42Zm9AHnA68KLmF", "dIwO7HHZCkK9Mw67s", "nYYEUI0aMKDgn2vsl", "iVgpgYNKKmjQ21Le5",
    "2HmDBpSxN2z2B5Nck", "Zoeaou4X50cjv9rbQ", "gqjwi4BJIglcjfokb", "ci5Tk9DvjVfnODVrJ",
    "c29t8s8Y98MQMw456", "62gpL9WGYfoDtrlXd", "UQNZ5dVtwojC4PTM3", "JFlc3WdfQULJzn83B",
    "hXyr0NpYlO1QoH0OF", "SfoNv2kOEGrTb3fcb", "QA0tcNCpxmY2cqHxK", "7bCprsyeTcpDOedPN",
    "Nr7Xd7KDViebiKYaW", "W80opEdtGI862z1Zl", "e0IP6cDqBVMIIG5AT", "qrqpeUiW1dDTDXZyD",
    "gBhh4NZ47MCC8p4ao"
)

$body = @{
    run_ids = $runIds
    platform = "facebook"
    analyze_after = $true   # analizar sentimiento tras importar para que se vean en el dashboard
}
if ($ProfileId -gt 0) {
    $body["profile_id"] = $ProfileId
}
$bodyJson = $body | ConvertTo-Json

Write-Host "Importando comentarios de $($runIds.Count) corridas..." -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/api/import-apify-comments-runs" `
        -Method Post `
        -ContentType "application/json" `
        -Body $bodyJson
    Write-Host "OK: $($response.message)" -ForegroundColor Green
    Write-Host "Corridas OK: $($response.runs_ok) / $($runIds.Count)"
    Write-Host "Corridas fallidas: $($response.runs_failed)"
    Write-Host "Total comentarios importados: $($response.total_comments_imported)"
    if ($null -ne $response.analyzed_after_import -and $response.analyzed_after_import -gt 0) {
        Write-Host "Comentarios analizados para el dashboard: $($response.analyzed_after_import)" -ForegroundColor Green
    }
    if ($response.failed -and $response.failed.Count -gt 0) {
        Write-Host "Primeros errores:" -ForegroundColor Yellow
        $response.failed | ForEach-Object { Write-Host "  $($_.run_id): $($_.error)" }
    }
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}
