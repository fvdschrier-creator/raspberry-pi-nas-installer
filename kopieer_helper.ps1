param(
    [string]$NasMap,
    [string]$Downloads,
    [string]$OldMap
)

$gekopieerd = 0

Get-ChildItem $NasMap -File | ForEach-Object {
    $naam = $_.BaseName
    $ext = $_.Extension
    $doel = $_.FullName

    # Zoek alle versies in Downloads: exact + genummerd
    $versies = Get-ChildItem $Downloads -File | Where-Object {
        ($_.BaseName -eq $naam -or $_.BaseName -match ('^' + [regex]::Escape($naam) + ' \(\d+\)$')) -and $_.Extension -eq $ext
    }

    if ($versies) {
        $gesorteerd = $versies | Sort-Object LastWriteTime -Descending
        $nieuwste = $gesorteerd[0]

        # Hernoem nieuwste naar correcte naam als het genummerd is
        $correctNaam = Join-Path $Downloads ($naam + $ext)
        if ($nieuwste.FullName -ne $correctNaam) {
            Copy-Item $nieuwste.FullName $correctNaam -Force
            Write-Host "  HERNOEMD: $($nieuwste.Name) -> $naam$ext"
        }

        # Verplaats alle genummerde versies naar Download Old NAS
        $gesorteerd | Where-Object { $_.BaseName -match ('^' + [regex]::Escape($naam) + ' \(\d+\)$') } | ForEach-Object {
            Move-Item $_.FullName $OldMap -Force
            Write-Host "  ARCHIEF:  $($_.Name)"
        }

        # Kopieer altijd naar NAS-map (overschrijft bestaande)
        $bron = Get-Item $correctNaam -ErrorAction SilentlyContinue
        if ($bron) {
            Copy-Item $bron.FullName $doel -Force
            Write-Host "  GEKOPIEERD: $naam$ext"
            $gekopieerd++
        }
    }
}

Write-Host ""
Write-Host "  $gekopieerd bestand(en) bijgewerkt."
exit $gekopieerd
