# Test Google API configuration
$headers = @{
    "Content-Type" = "application/json"
}

$body = @{
    provider = "google"
    model_id = "gemini-pro"
    api_key = $env:GOOGLE_API_KEY
    temperature = 0.3
    max_tokens = 100
} | ConvertTo-Json

Write-Host "Testing Google API configuration..."
Write-Host "Endpoint: http://localhost:8001/api/models/test"
Write-Host "Payload: $body"

try {
    $response = Invoke-RestMethod -Uri "http://localhost:8001/api/models/test" -Method POST -Headers $headers -Body $body
    Write-Host "✅ SUCCESS!" -ForegroundColor Green
    Write-Host "Response:" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "❌ FAILED!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    if ($_.Exception.Response) {
        $errorDetails = $_.Exception.Response.Content.ReadAsStringAsync().Result
        Write-Host "Error Details: $errorDetails" -ForegroundColor Red
    }
}