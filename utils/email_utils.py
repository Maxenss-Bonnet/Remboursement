# utils/email_utils.py
import smtplib
import ssl
from email.message import EmailMessage
from config.settings import SMTP_CONFIG

def envoyer_email_reset(destinataire_email: str, nom_utilisateur: str, code_reset: str) -> bool:
    """Envoie un email avec le code de réinitialisation."""
    if not SMTP_CONFIG:
        print("Erreur: Configuration SMTP non chargée. Impossible d'envoyer l'email.")
        return False
    if not SMTP_CONFIG.get('email_sender') or not SMTP_CONFIG.get('password'):
        print("Erreur: Email expéditeur ou mot de passe manquant dans la configuration SMTP.")
        return False

    sujet = "Votre code de réinitialisation de mot de passe"
    corps_html = f"""
    <p>Bonjour {nom_utilisateur},</p>
    <p>Vous avez demandé une réinitialisation de votre mot de passe pour l'application de gestion des remboursements.</p>
    <p>Votre code de réinitialisation à usage unique est : <strong>{code_reset}</strong></p>
    <p>Ce code expirera dans 5 minutes.</p>
    <p>Si vous n'avez pas demandé cette réinitialisation, veuillez ignorer cet email.</p>
    <p>Cordialement,<br>L'Application de Gestion des Remboursements</p>
    """

    msg = EmailMessage()
    msg['Subject'] = sujet
    msg['From'] = SMTP_CONFIG['email_sender']
    msg['To'] = destinataire_email
    msg.set_content(
        f"Bonjour {nom_utilisateur},\n\nVotre code de réinitialisation est : {code_reset}\nCe code expirera dans 5 minutes.\n\nSi vous n'avez pas demandé cette réinitialisation, veuillez ignorer cet email.")
    msg.add_alternative(corps_html, subtype='html')

    try:
        context = ssl.create_default_context()
        server = None
        if SMTP_CONFIG.get('use_ssl', False):
            server = smtplib.SMTP_SSL(SMTP_CONFIG['server'], SMTP_CONFIG['port'], context=context)
        else:
            server = smtplib.SMTP(SMTP_CONFIG['server'], SMTP_CONFIG['port'])
            if SMTP_CONFIG.get('use_tls', True):
                 server.starttls(context=context)

        server.login(SMTP_CONFIG['email_sender'], SMTP_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        print(f"Email de réinitialisation envoyé avec succès à {destinataire_email}.")
        return True
    except smtplib.SMTPAuthenticationError:
        print("Erreur d'authentification SMTP. Vérifiez votre email et mot de passe d'application.")
        return False
    except smtplib.SMTPServerDisconnected:
        print("Déconnecté du serveur SMTP. Réessayez plus tard.")
        return False
    except smtplib.SMTPConnectError:
        print(f"Impossible de se connecter au serveur SMTP : {SMTP_CONFIG['server']}:{SMTP_CONFIG['port']}")
        return False
    except ConnectionRefusedError:
        print(f"Connexion refusée par le serveur SMTP : {SMTP_CONFIG['server']}:{SMTP_CONFIG['port']}")
        return False
    except Exception as e:
        print(f"Une erreur générale est survenue lors de l'envoi de l'email : {e}")
        return False

def _build_html_table_from_data(demandes_details: list[dict]) -> str:
    """Construit une table HTML à partir d'une liste de dictionnaires de demandes."""
    if not demandes_details:
        return ""
    
    table_header = """
<table style="width: 100%; border-collapse: collapse; margin-top: 20px; margin-bottom: 20px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
    <thead style="background-color: #0078D4; color: white;">
        <tr>
            <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Réf. Demande</th>
            <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Date Création</th>
            <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Patient</th>
            <th style="border: 1px solid #ddd; padding: 12px; text-align: right;">Montant</th>
        </tr>
    </thead>
    <tbody>
"""
    
    table_rows = ""
    for i, demande in enumerate(demandes_details):
        bg_color = "#f9f9f9" if i % 2 == 0 else "#ffffff"
        table_rows += f"""
        <tr style="background-color: {bg_color};">
            <td style="border: 1px solid #ddd; padding: 12px;">{demande.get('id', 'N/A')}</td>
            <td style="border: 1px solid #ddd; padding: 12px;">{demande.get('date', 'N/A')}</td>
            <td style="border: 1px solid #ddd; padding: 12px;">{demande.get('patient', 'N/A')}</td>
            <td style="border: 1px solid #ddd; padding: 12px; text-align: right; font-weight: bold;">{demande.get('montant', 'N/A')}</td>
        </tr>
"""
    
    table_footer = "    </tbody>\n</table>"
    return table_header + table_rows + table_footer

def envoyer_rappel_remboursement(destinataire_email: str, nom_destinataire: str, message: str, demandes_details: list[dict]) -> tuple[bool, str]:
    """Envoie un email de rappel pour les demandes de remboursement en attente."""
    if not SMTP_CONFIG:
        return False, "Configuration SMTP non chargée. Impossible d'envoyer l'email."
    if not SMTP_CONFIG.get('email_sender') or not SMTP_CONFIG.get('password'):
        return False, "Email expéditeur ou mot de passe manquant dans la configuration SMTP."
    
    sujet = "Rappel : Demandes de remboursement en attente"
    
    # Construire la table HTML à partir des données structurées
    html_table = _build_html_table_from_data(demandes_details)

    # Remplacer la version texte du tableau dans le message par la version HTML.
    # On utilise un placeholder simple que l'on va remplacer.
    placeholder = "Voici le détail des demandes en attente :"
    
    # Version texte brut (pour les clients mail qui n'affichent pas le HTML)
    text_body = message

    # Version HTML
    html_body_text = text_body.replace('\n', '<br>')
    # Insérer la table HTML à la place du placeholder
    if html_table:
        html_body_with_table = html_body_text.replace(placeholder, f"<p>{placeholder}</p>{html_table}")
    else:
        html_body_with_table = html_body_text.replace(placeholder, f"<p>{placeholder}</p><p><i>(Aucune demande spécifique à afficher)</i></p>")


    corps_html = f"""
<html>
<body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 14px; line-height: 1.6; color: #333; background-color: #f5f5f5; padding: 20px;">
    <div style="max-width: 700px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
        {html_body_with_table}
    </div>
</body>
</html>
"""
    
    msg = EmailMessage()
    msg['Subject'] = sujet
    msg['From'] = f"Application Remboursements <{SMTP_CONFIG['email_sender']}>"
    msg['To'] = destinataire_email
    msg.set_content(text_body)  # Version texte brut
    msg.add_alternative(corps_html, subtype='html')  # Version HTML
    
    try:
        context = ssl.create_default_context()
        server = None
        if SMTP_CONFIG.get('use_ssl', False):
            server = smtplib.SMTP_SSL(SMTP_CONFIG['server'], SMTP_CONFIG['port'], context=context)
        else:
            server = smtplib.SMTP(SMTP_CONFIG['server'], SMTP_CONFIG['port'])
            if SMTP_CONFIG.get('use_tls', True):
                server.starttls(context=context)
        
        server.login(SMTP_CONFIG['email_sender'], SMTP_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        print(f"Email de rappel envoyé avec succès à {destinataire_email}.")
        return True, "Email envoyé avec succès."
    except smtplib.SMTPAuthenticationError:
        return False, "Erreur d'authentification SMTP. Vérifiez votre email et mot de passe d'application."
    except smtplib.SMTPServerDisconnected:
        return False, "Déconnecté du serveur SMTP. Réessayez plus tard."
    except smtplib.SMTPConnectError:
        return False, f"Impossible de se connecter au serveur SMTP : {SMTP_CONFIG['server']}:{SMTP_CONFIG['port']}"
    except ConnectionRefusedError:
        return False, f"Connexion refusée par le serveur SMTP : {SMTP_CONFIG['server']}:{SMTP_CONFIG['port']}"
    except Exception as e:
        return False, f"Une erreur est survenue lors de l'envoi de l'email : {e}"