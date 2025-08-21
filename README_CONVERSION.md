# Guide de Conversion PDF/Word - Rapport de Stage

Ce document explique comment utiliser l'extension **Markdown PDF** (yzane) pour convertir le rapport de stage en PDF ou HTML, avec optimisations pour la compatibilité Word.

## 🔧 Configuration

### Extension Requise
- **Markdown PDF** (yzane.markdown-pdf) v1.5.0+
- Installation via VS Code : `Ctrl+P` puis `ext install yzane.markdown-pdf`

### Fichiers de Configuration
- `.vscode/settings.json` : Configuration optimisée pour l'extension
- `style.css` : Feuille de style professionnelle compatible Word/PDF

## 📄 Conversion PDF

### Méthode 1: Command Palette
1. Ouvrir `rapport_stage_maxence_bonnet.md`
2. Appuyer sur `F1` ou `Ctrl+Shift+P`
3. Taper `markdown-pdf: Export (pdf)`
4. Le PDF sera généré dans le dossier `output/`

### Méthode 2: Clic Droit
1. Clic droit sur le fichier markdown
2. Sélectionner `markdown-pdf: Export (pdf)`

### Méthode 3: Auto-conversion
Pour activer la conversion automatique à chaque sauvegarde :
```json
"markdown-pdf.convertOnSave": true
```

## 📝 Conversion HTML (Compatible Word)

### Export HTML
1. Utiliser `markdown-pdf: Export (html)` 
2. Ouvrir le fichier HTML dans Word
3. Enregistrer au format .docx

### Avantages HTML → Word
- ✅ Conservation de la mise en forme
- ✅ Préservation des images et figures
- ✅ Maintien de la structure des titres
- ✅ Conservation des couleurs et styles

## 🎨 Optimisations Incluses

### Pour PDF
- Sauts de page automatiques pour chaque section principale
- Sommaire compact sur une page
- Figures et schémas agrandis et lisibles
- Headers/footers professionnels
- Gestion des couleurs d'impression

### Pour Word (via HTML)
- Préservation des styles CSS
- Conservation de la hiérarchie des titres
- Maintien des listes à puces et numérotées
- Images redimensionnées automatiquement
- Code syntax highlighting préservé

## 📐 Personnalisation

### Modifier les Marges
```json
"markdown-pdf.margin.top": "20mm",
"markdown-pdf.margin.bottom": "22mm",
"markdown-pdf.margin.right": "20mm",
"markdown-pdf.margin.left": "20mm"
```

### Changer les Headers/Footers
```json
"markdown-pdf.headerTemplate": "<div style=\"font-size: 9px;\">Votre en-tête</div>",
"markdown-pdf.footerTemplate": "<div style=\"font-size: 9px;\">Votre pied de page</div>"
```

### Désactiver les Styles par Défaut
```json
"markdown-pdf.includeDefaultStyles": false
```

## 🔍 Résolution des Problèmes

### Images Manquantes
- Vérifier que les chemins d'images sont relatifs
- S'assurer que les fichiers existent dans `./captures/` et `./diagrams-out/`

### Sauts de Page
- Utiliser `<div class="page-break"></div>` pour forcer un saut
- Les H2 créent automatiquement des sauts de page

### Qualité des Diagrammes
- Les SVG sont automatiquement optimisés
- Pour de meilleurs résultats, utiliser des images haute résolution

## 📊 Formats de Sortie Supportés

| Format | Extension | Usage Recommandé |
|--------|-----------|------------------|
| PDF    | `.pdf`    | Impression, partage final |
| HTML   | `.html`   | Conversion vers Word |
| PNG    | `.png`    | Images, aperçus |
| JPEG   | `.jpeg`   | Compression optimisée |

## ⚡ Raccourcis Utiles

- `Ctrl+Shift+P` → `markdown-pdf` : Accès rapide aux commandes
- `F1` → Export : Menu de conversion
- `Ctrl+S` : Sauvegarde + conversion auto (si activée)

## 📋 Checklist Avant Export

- [ ] Toutes les images sont présentes
- [ ] Les liens internes fonctionnent
- [ ] Le sommaire est à jour
- [ ] Les diagrammes sont générés (dossier `diagrams-out/`)
- [ ] La configuration est correcte dans `settings.json`

---

*Ce guide est optimisé pour la configuration actuelle du projet. Les styles CSS sont spécialement conçus pour l'extension Markdown PDF (yzane) version 1.5.0+.*
