import pdfplumber
import re
import io


def extraire_infos_facture(chemin_pdf_facture: str) -> dict:
    """
    Extrait le Nom, le Prénom et la Référence d'un fichier PDF de facture
    en se basant sur un format spécifique.
    """
    infos = {"nom": None, "prenom": None, "reference": None}
    try:
        # CORRECTION DÉFINITIVE : Lire le fichier en mémoire pour le libérer immédiatement du disque
        with open(chemin_pdf_facture, 'rb') as f:
            pdf_bytes = f.read()

        # Travailler sur la copie en mémoire (io.BytesIO) pour ne pas verrouiller le fichier original
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not pdf.pages:
                print("Avertissement: Le PDF ne contient aucune page.")
                return infos

            page = pdf.pages[0]
            texte_complet = page.extract_text()

            if not texte_complet:
                print("Avertissement: Aucun texte n'a pu être extrait du PDF.")
                return infos

            lignes = texte_complet.split('\n')

            # 1. Extraction de la Référence
            for ligne in lignes:
                match_reference = re.search(r"Référence:\s*(25[\s\d]+)", ligne, re.IGNORECASE)
                if match_reference:
                    ref_brute = match_reference.group(1).strip()
                    if ref_brute.startswith("25 ") and len(ref_brute) > 3:
                        infos["reference"] = "25" + ref_brute[3:].replace(" ", "")
                    elif ref_brute.startswith("25") and " " not in ref_brute and len(ref_brute) > 2:
                        infos["reference"] = ref_brute
                    else:
                        parts_ref = ref_brute.split(" ", 1)
                        if len(parts_ref) == 2 and parts_ref[0] == "25":
                            infos["reference"] = "25" + parts_ref[1].replace(" ", "")
                        else:
                            infos["reference"] = ref_brute.replace(" ", "")
                    break

            if not infos["reference"]:
                match_ref_simple = re.search(r"\b(25\s?\d{3,})\b", texte_complet)
                if match_ref_simple:
                    infos["reference"] = match_ref_simple.group(1).replace(" ", "")

            # 2. Extraction Nom et Prénom
            if not infos["nom"]:
                for i, ligne_brute in enumerate(lignes):
                    ligne_nettoyee_pour_assure = ligne_brute.strip()
                    match_nom_prenom_assure = re.match(
                        r"^\s*([A-ZÀ-Ÿ'-]+)\s+([A-ZÀ-Ÿ'-]+(?:\s[A-ZÀ-Ÿ'-]+)*)\s+ASSURE\b",
                        ligne_nettoyee_pour_assure, re.IGNORECASE)
                    if match_nom_prenom_assure:
                        infos["nom"] = match_nom_prenom_assure.group(1)
                        infos["prenom"] = match_nom_prenom_assure.group(2)
                        break

            if not infos["nom"]:
                for i, ligne_brute in enumerate(lignes):
                    ligne_nettoyee = ligne_brute.strip()
                    match_nom_prenom_seul = re.match(r"^\s*([A-ZÀ-Ÿ'-]+)\s+([A-ZÀ-Ÿ'-]+(?:\s[A-ZÀ-Ÿ'-]+)*)\s*$",
                                                     ligne_nettoyee)

                    if match_nom_prenom_seul:
                        potentiel_nom = match_nom_prenom_seul.group(1)
                        potentiel_prenom = match_nom_prenom_seul.group(2)
                        mots_hopital_a_eviter = ["HOPITAL", "PRIVE", "NATECIA", "AVENUE", "ROCKFELLER", "LYON", "TEL",
                                                 "SIRET", "FINESS", "REFERENCE", "PERIODE", "SERVICE", "SORTIE",
                                                 "PRESTATIONS", "TOTAL", "FAIT A", "CPAM", "MUTUELLE"]
                        nom_est_valide = potentiel_nom.upper() not in mots_hopital_a_eviter
                        prenom_est_valide = True
                        for mot_prenom in potentiel_prenom.upper().split():
                            if mot_prenom in mots_hopital_a_eviter:
                                prenom_est_valide = False
                                break

                        if nom_est_valide and prenom_est_valide:
                            if i + 1 < len(lignes):
                                ligne_suiv_nettoyee = lignes[i + 1].strip()
                                if re.search(r"^\d+.*(?:AVENUE|RUE|BOULEVARD|CHEMIN|PLACE|ALLÉE|BD|AV)\b",
                                             ligne_suiv_nettoyee, re.IGNORECASE) or \
                                        re.search(r"^\d{5}\s+[A-ZÀ-Ÿ'-]+", ligne_suiv_nettoyee):
                                    infos["nom"] = potentiel_nom
                                    infos["prenom"] = potentiel_prenom
                                    break

    except Exception as e:
        print(f"Erreur lors de l'extraction PDF ({chemin_pdf_facture}): {e}")

    print(f"Infos extraites du PDF: {infos}")
    return infos