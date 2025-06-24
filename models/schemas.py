from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import datetime

from config.settings import (
    STATUT_CREEE, STATUT_REFUSEE_CONSTAT_TP, STATUT_TROP_PERCU_CONSTATE,
    STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO, STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE
)


class HistoriqueStatut(BaseModel):
    historique_id: Optional[int] = None
    statut: str
    date: datetime.datetime
    par_utilisateur: Optional[str] = None
    commentaire: Optional[str] = ""
    class Config:
        from_attributes = True


class Remboursement(BaseModel):
    id_demande: str
    nom: Optional[str] = None
    prenom: Optional[str] = None
    reference_facture: str
    reference_facture_dossier: str
    description: str
    montant_demande: float
    chemins_factures_stockees: List[str] = Field(default_factory=list)
    chemins_rib_stockes: List[str] = Field(default_factory=list)
    chemins_trop_percu_stockees: List[str] = Field(default_factory=list)
    statut: str
    cree_par: Optional[str] = None
    date_creation: datetime.datetime
    derniere_modification_par: Optional[str] = None
    date_derniere_modification: datetime.datetime
    historique_statuts: List[HistoriqueStatut] = Field(default_factory=list)
    date_paiement_effectue: Optional[datetime.datetime] = None
    is_archived: bool = False

    class Config:
        str_strip_whitespace = True
        from_attributes = True

    def is_active_for(self, user_roles: list, user_name: str) -> bool:
        """ Détermine si la demande requiert une action de la part de l'utilisateur donné. """
        is_admin = "admin" in user_roles

        # L'admin peut agir sur la plupart des statuts actifs.
        if is_admin:
            active_statuses_for_admin = [
                STATUT_CREEE, STATUT_REFUSEE_CONSTAT_TP, STATUT_TROP_PERCU_CONSTATE,
                STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO
            ]
            if self.statut in active_statuses_for_admin:
                return True

        # Cas pour le comptable trésorerie (m.lupo)
        if "comptable_tresorerie" in user_roles and (
                self.statut == STATUT_CREEE or self.statut == STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO):
            return True

        # Cas pour le demandeur (p.neri) - CORRIGÉ
        if "demandeur" in user_roles and self.statut == STATUT_REFUSEE_CONSTAT_TP:
            return True

        # Cas pour le validateur chef (j.durousset)
        if "validateur_chef" in user_roles and self.statut == STATUT_TROP_PERCU_CONSTATE:
            return True

        # Cas pour le comptable fournisseur (p.diop)
        if "comptable_fournisseur" in user_roles and self.statut == STATUT_VALIDEE:
            return True

        return False


class Utilisateur(BaseModel):
    login: str
    hashed_password: str
    email: Optional[EmailStr] = None
    roles: List[str] = Field(default_factory=list)
    theme_color: Optional[str] = "blue"
    default_filter: Optional[str] = "Toutes les demandes"
    profile_picture_path: Optional[str] = None
    class Config:
        from_attributes = True


class UtilisateurUpdate(BaseModel):
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    roles: Optional[List[str]] = None
    theme_color: Optional[str] = None
    default_filter: Optional[str] = None
    profile_picture_path: Optional[str] = None