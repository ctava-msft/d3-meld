# Batch Trajectory Extraction Script
# Extracts multiple replicas to DCD files

$pythonExe = "C:\Users\christava\AppData\Local\miniforge3\python.exe"
$scriptPath = "extract_from_netcdf.py"

# Define replicas to extract (adjust as needed)
# Note: Only 30 replicas exist (0-29)
$replicas = @(
    @{Index=0; Output="trajectory.00.dcd"},
    @{Index=5; Output="trajectory.05.dcd"},
    @{Index=10; Output="trajectory.10.dcd"},
    @{Index=15; Output="trajectory.15.dcd"},
    @{Index=20; Output="trajectory.20.dcd"},
    @{Index=25; Output="trajectory.25.dcd"},
    @{Index=29; Output="trajectory.29.dcd"}
)

Write-Host "🚀 Starting batch trajectory extraction..." -ForegroundColor Cyan
Write-Host "Total replicas to extract: $($replicas.Count)" -ForegroundColor Cyan
Write-Host ""

$successCount = 0
$failCount = 0

foreach ($replica in $replicas) {
    $index = $replica.Index
    $output = $replica.Output
    
    Write-Host "📊 Extracting replica $index -> $output" -ForegroundColor Yellow
    
    $startTime = Get-Date
    
    try {
        & $pythonExe $scriptPath --replica $index --output $output
        
        if ($LASTEXITCODE -eq 0) {
            $endTime = Get-Date
            $duration = ($endTime - $startTime).TotalSeconds
            
            if (Test-Path $output) {
                $fileSize = (Get-Item $output).Length / 1MB
                Write-Host "✅ Success! Created $output ($([math]::Round($fileSize, 2)) MB) in $([math]::Round($duration, 1))s" -ForegroundColor Green
                $successCount++
            } else {
                Write-Host "❌ Failed: File not created" -ForegroundColor Red
                $failCount++
            }
        } else {
            Write-Host "❌ Failed with exit code $LASTEXITCODE" -ForegroundColor Red
            $failCount++
        }
    } catch {
        Write-Host "❌ Error: $_" -ForegroundColor Red
        $failCount++
    }
    
    Write-Host ""
}

Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "📈 Extraction Summary:" -ForegroundColor Cyan
Write-Host "  ✅ Successful: $successCount" -ForegroundColor Green
Write-Host "  ❌ Failed: $failCount" -ForegroundColor Red
Write-Host "  📁 Total files: $($replicas.Count)" -ForegroundColor Cyan

if ($failCount -eq 0) {
    Write-Host "`n🎉 All extractions completed successfully!" -ForegroundColor Green
} else {
    Write-Host "`n⚠️  Some extractions failed. Check the output above." -ForegroundColor Yellow
}

# List all DCD files
Write-Host "`n📋 Created DCD files:" -ForegroundColor Cyan
Get-ChildItem -Filter "trajectory.*.dcd" | Format-Table Name, @{Name="Size (MB)";Expression={[math]::Round($_.Length/1MB,2)}}, LastWriteTime -AutoSize
