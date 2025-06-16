from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import datetime

class HistoriqueStatut(BaseModel):
    statut: str
    date: datetime.datetime
    par_utilisateur: Optional[str] = None
    commentaire: Optional[str] = ""

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
    cree_par: str
    date_creation: datetime.datetime
    derniere_modification_par: str
    date_derniere_modification: datetime.datetime
    historique_statuts: List[HistoriqueStatut] = Field(default_factory=list)
    date_paiement_effectue: Optional[datetime.datetime] = None
    is_archived: bool = False

    class Config:
        str_strip_whitespace = True
        from_attributes = True

class Utilisateur(BaseModel):
    login: str
    hashed_password: str
    email: Optional[EmailStr] = None
    roles: List[str] = Field(default_factory=list)
    theme_color: Optional[str] = "blue"
    default_filter: Optional[str] = "Toutes les demandes"
    profile_picture_path: Optional[str] = None

class UtilisateurUpdate(BaseModel):
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    roles: Optional[List[str]] = None
    theme_color: Optional[str] = None
    default_filter: Optional[str] = None
    profile_picture_path: Optional[str] = None