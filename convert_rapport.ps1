# ===================================
# CONVERSION RAPPORT DE STAGE
# Extension Markdown PDF (yzane)
# ===================================

Write-Host "🔄 Verification de l'extension Markdown PDF..." -ForegroundColor Yellow

# Verification de l'extension
$extensions = code --list-extensions
if ($extensions -notcontains "yzane.markdown-pdf") {
    Write-Host "❌ ERREUR: Extension Markdown PDF non trouvee" -ForegroundColor Red
    Write-Host "💡 Installation: code --install-extension yzane.markdown-pdf" -ForegroundColor Cyan
    Read-Host "Appuyez sur Entree pour continuer"
    exit 1
}

Write-Host "✅ Extension trouvee !" -ForegroundColor Green
Write-Host ""

Write-Host "📄 Configuration:" -ForegroundColor Blue
Write-Host "- Fichier source: rapport_stage_maxence_bonnet.md"
Write-Host "- Style: style.css"
Write-Host "- Destination: output/"
Write-Host ""

Write-Host "🎯 INSTRUCTIONS DE CONVERSION:" -ForegroundColor Magenta
Write-Host "1. Ouvrir 'rapport_stage_maxence_bonnet.md' dans VS Code"
Write-Host "2. Appuyer sur F1 ou Ctrl+Shift+P"
Write-Host "3. Taper: 'markdown-pdf: Export (pdf)'"
Write-Host "4. Ou clic droit > 'markdown-pdf: Export (pdf)'"
Write-Host ""

Write-Host "📋 Formats disponibles:" -ForegroundColor Green
Write-Host "• PDF: Pour impression et partage final"
Write-Host "• HTML: Pour conversion vers Word (.docx)"
Write-Host "• PNG/JPEG: Pour aperçus"
Write-Host ""

Write-Host "⚙️  Configuration automatique appliquee:" -ForegroundColor Cyan
Write-Host "• Marges: 20mm"
Write-Host "• Format: A4 Portrait"
Write-Host "• Headers/Footers: Professionnels avec pagination"
Write-Host "• Sauts de page: Automatiques pour chaque section"
Write-Host "• Qualite: 100% (optimale)"
Write-Host ""

Write-Host "🔧 Pour conversion vers Word:" -ForegroundColor Yellow
Write-Host "1. Exporter en HTML"
Write-Host "2. Ouvrir le fichier HTML dans Word"
Write-Host "3. Enregistrer au format .docx"
Write-Host ""

Write-Host "📚 Guide complet: README_CONVERSION.md" -ForegroundColor Blue

Read-Host "Appuyez sur Entree pour fermer"
