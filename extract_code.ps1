$sourcePath = Get-Location
$outputFile = "$sourcePath\combined_code.txt"
$fileExtension = "*.py"  # Change this to your actual extension

# Clear the output file if it exists
if (Test-Path $outputFile) {
    Remove-Item $outputFile
}

Get-ChildItem -Path $sourcePath -Recurse -Filter $fileExtension | ForEach-Object {
    $header = "`n### FILE: $($_.FullName) ###`n"
    Add-Content -Path $outputFile -Value $header
    Get-Content $_.FullName | Add-Content -Path $outputFile
}