param (
    [switch]$f,
    [switch]$d,
    [string]$Path = (Get-Location)
)

if ($f -and $d) {
    Write-Error "You can specify either -f (file) or -d (directory), but not both."
    exit
}

# Define the file extensions to look for
$fileExtensions = @('.html')#@('.txt', '.md', '.py', '.js', '.css')

if ($f) {
    # Check if the specified path is a file
    if (-not (Test-Path -Path $Path -PathType Leaf)) {
        Write-Error "The specified path is not a valid file."
        exit
    }

    $files = @([PSCustomObject]@{ FullName = $Path })
} elseif ($d) {
    # Check if the specified path is a directory
    if (-not (Test-Path -Path $Path -PathType Container)) {
        Write-Error "The specified path is not a valid directory."
        exit
    }

    # Get the list of all files in the specified directory and subdirectories, filtering by the specified extensions
    $files = Get-ChildItem -Path $Path -Recurse -File | Where-Object {
        $fileExtensions -contains $_.Extension
    }
} else {
    Write-Error "You must specify either -f (file) or -d (directory)."
    exit
}

# Loop through each file
foreach ($file in $files) {
    # Read the content of the file
    $content = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue -Encoding UTF8
    
    # Split the content into individual lines
    $lines = $content -split "`n"
    
    # Search for lines with Cyrillic characters and print them to the terminal
    for ($i = 0; $i -lt $lines.Length; $i++) {
        $line = $lines[$i]
        if ($line -match '[\u0400-\u04FF]') {
            $occurrences = [regex]::Matches($line, '[\u0400-\u04FF]').Count
            Write-Output "Found in '$($file.FullName)' - Line $($i + 1) (Occurrences: $occurrences): $line"
        }
    }
}