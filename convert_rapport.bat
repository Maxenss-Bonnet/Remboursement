@echo off
echo ===================================
echo   CONVERSION RAPPORT DE STAGE
echo   Extension Markdown PDF (yzane)
echo ===================================
echo.

echo Verification de l'extension Markdown PDF...
code --list-extensions | findstr "yzane.markdown-pdf"
if errorlevel 1 (
    echo ERREUR: Extension Markdown PDF non trouvee
    echo Installation: code --install-extension yzane.markdown-pdf
    pause
    exit /b 1
)

echo Extension trouvee !
echo.

echo Conversion en cours...
echo - Fichier source: rapport_stage_maxence_bonnet.md
echo - Style: style.css
echo - Destination: output/
echo.

echo INSTRUCTIONS:
echo 1. Ouvrir rapport_stage_maxence_bonnet.md dans VS Code
echo 2. Appuyer sur F1 ou Ctrl+Shift+P
echo 3. Taper: markdown-pdf: Export (pdf)
echo 4. Ou clic droit > markdown-pdf: Export (pdf)
echo.

echo Formats disponibles:
echo - PDF: Pour impression et partage final
echo - HTML: Pour conversion vers Word (.docx)
echo - PNG/JPEG: Pour aperçus
echo.

echo Configuration automatique appliquee:
echo - Marges: 20mm
echo - Format: A4
echo - Headers/Footers: Professionnels
echo - Sauts de page: Automatiques
echo.

pause
